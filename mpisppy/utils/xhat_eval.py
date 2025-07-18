###############################################################################
# mpi-sppy: MPI-based Stochastic Programming in PYthon
#
# Copyright (c) 2024, Lawrence Livermore National Security, LLC, Alliance for
# Sustainable Energy, LLC, The Regents of the University of California, et al.
# All rights reserved. Please see the files COPYRIGHT.md and LICENSE.md for
# full copyright and license information.
###############################################################################
# Code to evaluate a given x-hat, but given as a nonant-cache
# To test: python xhat_eval.py --num-scens=3 --EF-solver-name=cplex

import inspect
import pyomo.environ as pyo
import logging
import numpy as np

import mpisppy.log
from mpisppy import MPI
import mpisppy.utils.sputils as sputils
import mpisppy.spopt

    
fullcomm = MPI.COMM_WORLD
global_rank = fullcomm.Get_rank()

# Could also pass, e.g., sys.stdout instead of a filename
mpisppy.log.setup_logger("mpisppy.utils.xhat_eval",
                         "xhateval.log",
                         level=logging.CRITICAL)                         
logger = logging.getLogger("mpisppy.utils.xhat_eval")

############################################################################
class Xhat_Eval(mpisppy.spopt.SPOpt):
    """ See SPOpt for list of args. """
    
    def __init__(
        self,
        options,
        all_scenario_names,
        scenario_creator,
        scenario_denouement=None,
        all_nodenames=None,
        mpicomm=None,
        scenario_creator_kwargs=None,
        variable_probability=None,
        extensions=None,
        extension_kwargs=None,
        ):
        
        super().__init__(
            options,
            all_scenario_names,
            scenario_creator,
            scenario_denouement=scenario_denouement,
            all_nodenames=all_nodenames,
            extensions=extensions,
            extension_kwargs=extension_kwargs,
            mpicomm=mpicomm,
            scenario_creator_kwargs=scenario_creator_kwargs,
            variable_probability=variable_probability,
        )
        
        self.verbose = self.options['verbose']
        self._subproblems_solvers_created = False
        self.Ag = options.get("Ag", None)


    def _lazy_create_solvers(self):
        if self._subproblems_solvers_created:
            return
        self._create_solvers(presolve=False)
        self._subproblems_solvers_created = True


    #======================================================================
    def solve_one(self, solver_options, k, s,
                  dtiming=False,
                  gripe=False,
                  tee=False,
                  verbose=False,
                  disable_pyomo_signal_handling=False,
                  update_objective=True,
                  compute_val_at_nonant=False,
                  warmstart=False):

        self._lazy_create_solvers()
        pyomo_solve_time = super().solve_one(solver_options, k, s,
                                             dtiming=dtiming,
                                             gripe=gripe,
                                             tee=tee,
                                             verbose=verbose,
                                             disable_pyomo_signal_handling=disable_pyomo_signal_handling,
                                             update_objective=update_objective,
                                             warmstart=warmstart,
                                             need_solution=compute_val_at_nonant,)

        if compute_val_at_nonant:
            objfct = self.saved_objectives[k]
            if self.verbose:
                print ("caller", inspect.stack()[1][3])
                print ("E_Obj Scenario {}, prob={}, Obj={}, ObjExpr={}"\
                       .format(k, s._mpisppy_probability, pyo.value(objfct), objfct.expr))
            self.objs_dict[k] = pyo.value(objfct)

        return(pyomo_solve_time)


    def solve_loop(self, solver_options=None,
                   use_scenarios_not_subproblems=False,
                   dtiming=False,
                   gripe=False,
                   disable_pyomo_signal_handling=False,
                   tee=False,
                   verbose=False,
                   compute_val_at_nonant=False,
                   warmstart=False,
                   need_solution=False,):
        """ Loop over self.local_subproblems and solve them in a manner 
            dicated by the arguments. In addition to changing the Var
            values in the scenarios, update _PySP_feas_indictor for each.

        ASSUMES:
            Every scenario already has a _solver_plugin attached.

        Args:
            solver_options (dict or None): the scenario solver options
            use_scenarios_not_subproblems (boolean): for use by bounds
            dtiming (boolean): indicates that timing should be reported
            gripe (boolean): output a message if a solve fails
            disable_pyomo_signal_handling (boolean): set to true for asynch, 
                                                     ignored for persistent solvers.
            tee (boolean): show solver output to screen if possible
            verbose (boolean): indicates verbose output
            compute_val_at_nonant (boolean): indicate that self.objs_dict should
                                            be created and computed.
                                            
            warmstart (boolean): indicates a warmstart

        NOTE: I am not sure what happens with solver_options None for
              a persistent solver. Do options persist?

        NOTE: set_objective takes care of W and prox changes.
        """
        self._lazy_create_solvers()
        def _vb(msg): 
            if verbose and self.cylinder_rank == 0:
                print ("(rank0) " + msg)
        logger.debug("  early solve_loop for rank={}".format(self.cylinder_rank))

        # note that when there is no bundling, scenarios are subproblems
        if use_scenarios_not_subproblems:
            s_source = self.local_scenarios
        else:
            s_source = self.local_subproblems
            
        if compute_val_at_nonant:
            self.objs_dict={}
        
        for k,s in s_source.items():
            if tee:
                print(f"Tee solve for {k} on global rank {self.global_rank}")
            logger.debug("  in loop solve_loop k={}, rank={}".format(k, self.cylinder_rank))

            pyomo_solve_time = self.solve_one(solver_options, k, s,
                                              dtiming=dtiming,
                                              verbose=verbose,
                                              tee=tee,
                                              gripe=gripe,
                disable_pyomo_signal_handling=disable_pyomo_signal_handling,
                compute_val_at_nonant=compute_val_at_nonant,
                                              warmstart=warmstart,
                                              )

        if dtiming:
            all_pyomo_solve_times = self.mpicomm.gather(pyomo_solve_time, root=0)
            if self.cylinder_rank == 0:
                print("Pyomo solve times (seconds):")
                print("\tmin=%4.2f mean=%4.2f max=%4.2f" %
                      (np.min(all_pyomo_solve_times),
                      np.mean(all_pyomo_solve_times),
                      np.max(all_pyomo_solve_times)))
                
    #======================================================================   
    def Eobjective(self, verbose=False, fct=None):
        """ Compute the expected value of the composition of the objective function 
            and a given function fct across all scenarios.

        Note: 
            Assumes the optimization is done beforehand,
            therefore DOES NOT CHECK FEASIBILITY or NON-ANTICIPATIVITY!
            This method uses whatever the current value of the objective
            function is.

        Args:
            verbose (boolean, optional):
                If True, displays verbose output. Default False.
            
            fct (function, optional):
                A function R-->R^p, such as x|-->(x,x^2,x^3). Default is None
                If fct is None, Eobjective returns the exepected value.
                

        Returns:
            float or numpy.array:
                The expected objective function value. 
                If fct is R-->R, returns a float.
                If fct is R-->R^p with p>1, returns a np.array of length p
        """
        self._lazy_create_solvers()
        if fct is None:
            return super().Eobjective(verbose=verbose)
        
        if not hasattr(self, "objs_dict"):
            raise RuntimeError("Values of the objective functions for each scenario"+
                               " at xhat have to be computed before running Eobjective")
        

        local_Eobjs = []
        for k,s in self.local_scenarios.items():
            if k not in self.objs_dict:
                raise RuntimeError(f"No value has been calculated for the scenario {k}")
            local_Eobjs.append(s._mpisppy_probability * fct(self.objs_dict[k]))
        local_Eobjs = np.array(local_Eobjs)
        local_Eobj = np.array([np.sum(local_Eobjs,axis=0)])
        global_Eobj = np.zeros(len(local_Eobj))
        self.mpicomm.Allreduce(local_Eobj, global_Eobj, op=MPI.SUM)
        if len(global_Eobj)==1:
            global_Eobj = global_Eobj[0]
        return global_Eobj
    
    
    #==============
    def evaluate_one(self, nonant_cache,scenario_name,s):
        """ Evaluate xhat for one scenario.

        Args:
            nonant_cache(numpy vector): special numpy vector with nonant values (see spopt)
            scenario_name(str): TODO
        

        Returns:
            Eobj (float or None): Expected value (or None if infeasible)

        """
        self._lazy_create_solvers()
        self._fix_nonants(nonant_cache)
        if not hasattr(self, "objs_dict"):
            self.objs_dict = {}
        

        solver_options = self.options["solver_options"] if "solver_options" in self.options else None
        k = scenario_name
        self.solve_one(solver_options,k, s,
                                          dtiming=False,
                                          verbose=self.verbose,
                                          tee=False,
                                          gripe=True,
                                          compute_val_at_nonant=True
                                          )
        
        obj = self.objs_dict[k]
        
        return obj
    
    def evaluate(self, nonant_cache, fct=None):
        """ Do the optimization and compute the expected value of the composition of the objective function 
            and a given function fct across all scenarios.

        Args:
            nonant_cache(ndn dict of numpy vector): special numpy vector with nonant values (see spopt)
            fct (function, optional):
                A function R-->R^p, such as x|-->(x,x^2,x^3). Default is None
                If fct is None, evaluate returns the exepected value.

        Returns:
            Eobj (float or numpy.array): Expected value

        """
        self._lazy_create_solvers()
        self._fix_nonants(nonant_cache)

        solver_options = self.options["solver_options"] if "solver_options" in self.options else None
        
        self.solve_loop(solver_options=solver_options,
                        use_scenarios_not_subproblems=True,
                        gripe=True, 
                        tee=False,
                        verbose=self.verbose,
                        compute_val_at_nonant=True
                        )
        
        Eobj = self.Eobjective(self.verbose,fct=fct)

        return Eobj
    
    
    
    def fix_nonants_upto_stage(self,t,cache):
        """ Fix the Vars subject to non-anticipativity at given values for stages 1 to t.
            Loop over the scenarios to restore, but loop over subproblems
            to alert persistent solvers.
        Args:
            cache (ndn dict of list or numpy vector): values at which to fix
        WARNING: 
            We are counting on Pyomo indices not to change order between
            when the cache_list is created and used.
        NOTE:
            You probably want to call _save_nonants right before calling this
        """
        self._lazy_create_solvers()
        rounding_bias = self.options.get("rounding_bias", 0.0)
        for k,s in self.local_scenarios.items():

            persistent_solver = None
            if (sputils.is_persistent(s._solver_plugin)):
                persistent_solver = s._solver_plugin

            nlens = s._mpisppy_data.nlens
            for node in s._mpisppy_node_list:
                if node.stage<=t:
                    ndn = node.name
                    if ndn not in cache:
                        raise RuntimeError("Could not find {} in {}"\
                                           .format(ndn, cache))
                    if cache[ndn] is None:
                        raise RuntimeError("Empty cache for scen={}, node={}".format(k, ndn))
                    if len(cache[ndn]) != nlens[ndn]:
                        raise RuntimeError("Needed {} nonant Vars for {}, got {}"\
                                           .format(nlens[ndn], ndn, len(cache[ndn])))
                    for i in range(nlens[ndn]): 
                        this_vardata = node.nonant_vardata_list[i]
                        if this_vardata in node.surrogate_vardatas:
                            continue
                        if this_vardata.is_binary() or this_vardata.is_integer():
                            this_vardata._value = round(cache[ndn][i] + rounding_bias)
                        else:
                            this_vardata._value = cache[ndn][i]
                        this_vardata.fix()
                        if persistent_solver is not None:
                            persistent_solver.update_var(this_vardata)
        
    
    
        
    #======================================================================
    def _fix_nonants_at_value(self):
        """ Fix the Vars subject to non-anticipativity at their current values.
            Loop over the scenarios to restore, but loop over subproblems
            to alert persistent solvers.
        """
        rounding_bias = self.options.get("rounding_bias", 0.0)
        for k,s in self.local_scenarios.items():

            persistent_solver = None
            if not self.bundling:
                if (sputils.is_persistent(s._solver_plugin)):
                    persistent_solver = s._solver_plugin

            for var in s._mpisppy_data.nonant_indices.values():
                if var in s._mpisppy_data.all_surrogate_nonants:
                    continue
                if var.is_binary() or var.is_integer():
                    var._value = round(var._value + rounding_bias)
                var.fix()
                if not self.bundling and persistent_solver is not None:
                    persistent_solver.update_var(var)

        if self.bundling:  # we might need to update persistent solvers
            rank_local = self.cylinder_rank
            for k,s in self.local_subproblems.items():
                if (sputils.is_persistent(s._solver_plugin)):
                    persistent_solver = s._solver_plugin
                else:
                    break  # all solvers should be the same

                # the bundle number is the last number in the name
                bunnum = sputils.extract_num(k)
                # for the scenarios in this bundle, update Vars
                for sname, scen in self.local_scenarios.items():
                    if sname not in self.names_in_bundles[rank_local][bunnum]:
                        break
                    for var in scen._mpisppy_data.nonant_indices.values():
                        if var in scen._mpisppy_data.all_surrogate_nonants:
                            continue
                        persistent_solver.update_var(var)

    def calculate_incumbent(self, fix_nonants=True, verbose=False):
        """
        Calculates the current incumbent

        Args:
            solver_options (dict): passed through to the solver
            verbose (boolean): controls debugging output
        Returns:
            xhatobjective (float or None): the objective function
                or None if one could not be obtained.
        """
        self._lazy_create_solvers()

        if fix_nonants:
            self._fix_nonants_at_value()

        self.solve_loop(solver_options=self.current_solver_options, 
                        verbose=verbose)

        infeasP = self.infeas_prob()
        if infeasP != 0.:
            return None
        else:
            if verbose and self.cylinder_rank == 0:
                print("  Feasible xhat found")
            return self.Eobjective(verbose=verbose)
    



if __name__ == "__main__":
    print("For an example of the use of Xhat_Eval see, e.g., zhat4xhat.py, "
          "which is in the confidence_intervals directory.")
