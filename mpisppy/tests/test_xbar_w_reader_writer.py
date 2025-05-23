###############################################################################
# mpi-sppy: MPI-based Stochastic Programming in PYthon
#
# Copyright (c) 2024, Lawrence Livermore National Security, LLC, Alliance for
# Sustainable Energy, LLC, The Regents of the University of California, et al.
# All rights reserved. Please see the files COPYRIGHT.md and LICENSE.md for
# full copyright and license information.
###############################################################################
# Author:
"""
IMPORTANT:
  Unless we run to convergence, the solver, and even solver
version matter a lot, so we often just do smoke tests.
"""

import os
import unittest
import csv
from mpisppy.utils import config

import mpisppy.utils.cfg_vanilla as vanilla
import mpisppy.tests.examples.farmer as farmer
from mpisppy.spin_the_wheel import WheelSpinner
from mpisppy.tests.utils import get_solver
import mpisppy.utils.wxbarreader as wxbarreader
import mpisppy.utils.wxbarwriter as wxbarwriter

__version__ = 0.2

solver_available,solver_name, persistent_available, persistent_solver_name= get_solver()

def _create_cfg():
    cfg = config.Config()
    wxbarreader.add_options_to_config(cfg)        
    wxbarwriter.add_options_to_config(cfg)
    cfg.add_branching_factors()
    cfg.num_scens_required()
    cfg.popular_args()
    cfg.two_sided_args()
    cfg.ph_args()
    cfg.solver_name = solver_name
    cfg.default_rho = 1
    return cfg

#*****************************************************************************

class Test_xbar_w_reader_writer_farmer(unittest.TestCase):
    """ Test the gradient code using farmer."""

    def _create_ph_farmer(self, ph_extensions=None, max_iter=100):
        self.w_file_name = './examples/w_test_data/w_file.csv'
        self.temp_w_file_name = './examples/w_test_data/_temp_w_file.csv'
        self.xbar_file_name = './examples/w_test_data/xbar_file.csv'
        self.temp_xbar_file_name = './examples/w_test_data/_temp_xbar_file.csv'
        self.cfg.num_scens = 3
        scenario_creator = farmer.scenario_creator
        scenario_denouement = farmer.scenario_denouement
        all_scenario_names = farmer.scenario_names_creator(self.cfg.num_scens)
        scenario_creator_kwargs = farmer.kw_creator(self.cfg)
        self.cfg.max_iterations = max_iter
        beans = (self.cfg, scenario_creator, scenario_denouement, all_scenario_names)
        hub_dict = vanilla.ph_hub(*beans, scenario_creator_kwargs=scenario_creator_kwargs, ph_extensions=ph_extensions)
        hub_dict['opt_kwargs']['options']['cfg'] = self.cfg
        if ph_extensions==wxbarwriter.WXBarWriter:
            self.cfg.W_and_xbar_writer = True
            self.cfg.W_fname = self.temp_w_file_name
            self.cfg.Xbar_fname = self.temp_xbar_file_name
        if ph_extensions==wxbarreader.WXBarReader:
            self.cfg.W_and_xbar_reader = True
            self.cfg.init_W_fname = self.w_file_name
            self.cfg.init_Xbar_fname = self.xbar_file_name
        list_of_spoke_dict = list()
        wheel = WheelSpinner(hub_dict, list_of_spoke_dict)
        wheel.spin()
        if wheel.strata_rank == 0:
            ph_object = wheel.spcomm.opt
            return ph_object

    def setUp(self):
        self.cfg = _create_cfg()
        self.ph_object = None
    
    def test_wwriter(self):
        self.ph_object = self._create_ph_farmer(ph_extensions=wxbarwriter.WXBarWriter, max_iter=5)
        with open(self.temp_w_file_name, 'r') as f:
            read = csv.reader(f)
            rows = list(read)
            self.assertAlmostEqual(float(rows[1][2]), 70.84705093609978, places=5)
            self.assertAlmostEqual(float(rows[3][2]), -41.104251445950844, places=5)
        os.remove(self.temp_w_file_name)

    def test_xbarwriter(self):
        self.ph_object = self._create_ph_farmer(ph_extensions=wxbarwriter.WXBarWriter, max_iter=5)
        with open(self.temp_xbar_file_name, 'r') as f:
            read = csv.reader(f)
            rows = list(read)
            self.assertAlmostEqual(float(rows[1][1]), 274.2239371483933, places=5)
            self.assertAlmostEqual(float(rows[3][1]), 96.88717449844287, places=5)
        os.remove(self.temp_xbar_file_name)

    def test_wreader(self):
        self.ph_object = self._create_ph_farmer(ph_extensions=wxbarreader.WXBarReader, max_iter=1)
        for sname, scenario in self.ph_object.local_scenarios.items():
            if sname == 'scen0':
                self.assertAlmostEqual(scenario._mpisppy_model.W[("ROOT", 1)]._value, 70.84705093609978)
            if sname == 'scen1':
                self.assertAlmostEqual(scenario._mpisppy_model.W[("ROOT", 0)]._value, -41.104251445950844)

    def test_xbarreader(self):
        self.ph_object = self._create_ph_farmer(ph_extensions=wxbarreader.WXBarReader, max_iter=1)
        for sname, scenario in self.ph_object.local_scenarios.items():
            if sname == 'scen0':
                self.assertAlmostEqual(scenario._mpisppy_model.xbars[("ROOT", 1)]._value, 274.2239371483933)
            if sname == 'scen1':
                self.assertAlmostEqual(scenario._mpisppy_model.xbars[("ROOT", 0)]._value, 96.88717449844287)

if __name__ == '__main__':
    unittest.main()
