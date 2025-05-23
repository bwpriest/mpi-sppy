###############################################################################
# mpi-sppy: MPI-based Stochastic Programming in PYthon
#
# Copyright (c) 2024, Lawrence Livermore National Security, LLC, Alliance for
# Sustainable Energy, LLC, The Regents of the University of California, et al.
# All rights reserved. Please see the files COPYRIGHT.md and LICENSE.md for
# full copyright and license information.
###############################################################################
import mpisppy.cylinders.spoke
import mpisppy.utils.sputils as sputils

class _LagrangianMixin:

    def lagrangian_prep(self):
        # Split up PH_Prep? Prox option is important for APH.
        # Seems like we shouldn't need the Lagrangian stuff, so attach_prox=False
        # Scenarios are created here
        self.opt.PH_Prep(attach_prox=False)
        self.opt._reenable_W()
        self.opt._create_solvers()

    def lagrangian(self, need_solution=True, warmstart=sputils.WarmstartStatus.PRIOR_SOLUTION):
        # update the nonant bounds, if possible, for a tighter relaxation
        self.receive_nonant_bounds()
        verbose = self.opt.options['verbose']
        # This is sort of a hack, but might help folks:
        if "ipopt" in self.opt.options["solver_name"]:
            print("\n WARNING: An ipopt solver will not give outer bounds\n")
        teeme = False
        if "tee-rank0-solves" in self.opt.options:
            teeme = self.opt.options['tee-rank0-solves']

        self.opt.solve_loop(
            solver_options=self.opt.current_solver_options,
            dtiming=False,
            gripe=True,
            tee=teeme,
            verbose=verbose,
            need_solution=need_solution,
            warmstart=warmstart,
        )
        ''' DTM (dlw edits): This is where PHBase Iter0 checks for scenario
            probabilities that don't sum to one and infeasibility and
            will send a kill signal if needed. For now we are relying
            on the fact that the OPT thread is solving the same
            models, and hence would detect both of those things on its
            own--the Lagrangian spoke doesn't need to check again.  '''
        return self.opt.Ebound(verbose)

    def finalize(self):
        self.final_bound = self.bound
        if self.opt.extensions is not None and \
            hasattr(self.opt.extobject, 'post_everything'):
            self.opt.extobject.post_everything()
        return self.final_bound

class LagrangianOuterBound(_LagrangianMixin, mpisppy.cylinders.spoke.OuterBoundWSpoke):

    converger_spoke_char = 'L'

    def _set_weights_and_solve(self, need_solution, warmstart=sputils.WarmstartStatus.PRIOR_SOLUTION):
        self.opt.W_from_flat_list(self.localWs) # Sets the weights
        return self.lagrangian(need_solution=need_solution, warmstart=warmstart)

    def do_while_waiting_for_new_Ws(self, need_solution, warmstart=sputils.WarmstartStatus.PRIOR_SOLUTION):
        if self.opt.options.get("subgradient_while_waiting", False):
            # compute a subgradient step
            self.opt.Compute_Xbar(self.verbose)
            self.opt.Update_W(self.verbose)
            bound = self.lagrangian(need_solution=need_solution, warmstart=warmstart)
            if bound is not None:
                self.send_bound(bound)

    def main(self, need_solution=False):
        self.verbose = self.opt.options['verbose']
        extensions = self.opt.extensions is not None

        self.lagrangian_prep()

        if extensions:
            self.opt.extobject.pre_iter0()

        # setting this for PH extensions used by this Spoke
        self.opt._PHIter = 0
        self.trivial_bound = self.lagrangian(need_solution=need_solution, warmstart=sputils.WarmstartStatus.USER_SOLUTION)

        if extensions:
            self.opt.extobject.post_iter0()
        self.opt._PHIter += 1

        self.opt.current_solver_options = self.opt.iterk_solver_options

        self.send_bound(self.trivial_bound)
        if extensions:
            self.opt.extobject.post_iter0_after_sync()

        while not self.got_kill_signal():
            if self.update_Ws():
                if extensions:
                    self.opt.extobject.miditer()
                bound = self._set_weights_and_solve(need_solution=need_solution, warmstart=sputils.WarmstartStatus.PRIOR_SOLUTION)
                if extensions:
                    self.opt.extobject.enditer()
                if bound is not None:
                    self.send_bound(bound)
                if extensions:
                    self.opt.extobject.enditer_after_sync()
                self.opt._PHIter += 1
            else:
                self.do_while_waiting_for_new_Ws(need_solution=need_solution, warmstart=sputils.WarmstartStatus.PRIOR_SOLUTION)
