Quick Start
===========

If you installed from github, install from source using pip in editable mode from the mpi-sppy repo root directory.

::
   
   pip install -e .

This step is not needed if you installed using pip.
You can also include the extras flags ``mpi`` to install a compliant version
of mpi4py or ``docs`` to install documentation dependencies from pip.


Verify installation
-------------------

Getting started depends on how you intend to use ``mpi-sppy`` but
verifying installation is a common task. If you installed ``mpi-sppy`` from
github, you can verify that you installed it and a solver by starting a
terminal. Then cd to the `mpi-sppy` directory and issue the following
terminal commands:

::

   cd examples
   cd farmer
   python farmer_ef 1 3 solver_name

but replace `solver_name` with the name of the solver you have installed, e.g., if you have installed glpk, use

::
   
   python farmer_ef 1 3 glpk

If you intend to use any parallel features, you should verify that you
have a *proper* installation of MPI and ``mpi4py``; see the section
:ref:`Install mpi4py`. If you are intending only to solve the
extensive form directly without decomposition, then you do not need to
concern yourself with MPI.


Pyomo Users who want to add stochastics
---------------------------------------

Users of ``mpi-sppy`` are viewed as developers, not as
end-users. Consequently, some Python programming is required.  The
first thing is to code a scenario creation function. See
:ref:`scenario_creator` for more information.
If you create a few more helper functions
(see :ref:`helper_functions`),
you can make use of the ``generic_cylinders`` program (see :ref:`generic_cylinders`) to use the hub and spoke system or to solve the the EF directly.
     
Alternatively, once you have the scenario creation function,
you can mimic the code in ``examples.farmer.farmer_ef`` to
solve the extensive form directly. If you want to use the hub
and spoke system to solve your problem via decomposition, you
should proceed to the section on writing :ref:`Drivers`, or to
the :ref:`Examples` section, or to the :ref:`generic_cylinders` section.


PySP Users
----------

If you are already using ``PySP`` for a stochastic program, getting started
with ``mpi-sppy`` is straightforward; however, unlike in ``PySP``, you will
be required to create a Python program. Many of the advanced features
of ``PySP`` are supported by ``mpi-sppy`` but they required creating Python
code to access them. The basic vehicle for a quick-start with ``PySP`` models is
``mpisppy.utils.pysp_model.PySPModel`` but the exact steps depend on
how you represented your model in ``PySP``.

Here are the general steps:

# Construct a ``PySPModel`` object giving its constructor information about your PySP model.

# Create an options dictionary.

# Create a PH or EF ``mpi-sppy`` object.

# Call its main function.

These steps alone will not result in use of the hub-spoke features of
`mpi-sppy`, but they will get your PySP model running in
``mpi-sppy``. See ``examples/farmer/from_pysp`` for some
examples and see :ref:`PySP conversion` for more details.
For an example with the hub-spoke features of `mpi-sppy`,
see ``examples/hydro/hydro_cylinders_pysp.py``.


Researchers who want to compare with mpi-sppy
---------------------------------------------

The quickest thing to do is to run one of the canned examples that
comes with ``mpi-sppy``. They are in subdirectories of
``examples`` and sample commands can be obtained by looking at
the code in ``examples.runall.py``. There is a table in the
mpi-sppy paper that gives references for some of the examples.
