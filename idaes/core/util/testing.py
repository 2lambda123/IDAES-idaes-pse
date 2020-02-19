##############################################################################
# Institute for the Design of Advanced Energy Systems Process Systems
# Engineering Framework (IDAES PSE Framework) Copyright (c) 2018-2019, by the
# software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia
# University Research Corporation, et al. All rights reserved.
#
# Please see the files COPYRIGHT.txt and LICENSE.txt for full copyright and
# license information, respectively. Both files are also available online
# at the URL "https://github.com/IDAES/idaes-pse".
##############################################################################

"""
This module contains utility functions for use in testing IDAES models.
"""

__author__ = "Andrew Lee"


from pyomo.environ import Set, SolverFactory, Var, Reals, Constraint, Param
from pyomo.common.config import ConfigBlock

from idaes.core import (declare_process_block_class,
                        PhysicalParameterBlock,
                        StateBlock,
                        StateBlockData,
                        ReactionParameterBlock,
                        ReactionBlockBase,
                        ReactionBlockDataBase,
                        MaterialFlowBasis,
                        MaterialBalanceType,
                        EnergyBalanceType,
                        MomentumBalanceType)


def get_default_solver():
    """
    Tries to set-up the default solver for testing, and returns None if not
    available
    """
    if SolverFactory('ipopt').available(exception_flag=False):
        solver = SolverFactory('ipopt')
        solver.options = {'tol': 1e-6,
                          'linear_solver': 'ma27'}
    else:
        solver = None

    return solver


# -----------------------------------------------------------------------------
# Define some generic PhysicalBlock and ReactionBlock classes for testing
@declare_process_block_class("PhysicalParameterTestBlock")
class _PhysicalParameterBlock(PhysicalParameterBlock):
    def build(self):
        super(_PhysicalParameterBlock, self).build()

        self.phase_list = Set(initialize=["p1", "p2"])
        self.component_list = Set(initialize=["c1", "c2"])
        self.phase_equilibrium_idx = Set(initialize=["e1", "e2"])
        self.element_list = Set(initialize=["H", "He", "Li"])
        self.element_comp = {"c1": {"H": 1, "He": 2, "Li": 3},
                             "c2": {"H": 4, "He": 5, "Li": 6}}

        self.phase_equilibrium_list = \
            {"e1": ["c1", ("p1", "p2")],
             "e2": ["c2", ("p1", "p2")]}

        # Attribute to switch flow basis for testing
        self.basis_switch = 1
        self.default_balance_switch = 1

        self.state_block_class = TestStateBlock

    @classmethod
    def define_metadata(cls, obj):
        obj.add_default_units({'time': 's',
                               'length': 'm',
                               'mass': 'g',
                               'amount': 'mol',
                               'temperature': 'K',
                               'energy': 'J',
                               'holdup': 'mol'})


class SBlockBase(StateBlock):
    def initialize(blk, outlvl=0, optarg=None, solver=None,
                   hold_state=False, **state_args):
        for k in blk.keys():
            blk[k].init_test = True
            blk[k].hold_state = hold_state

    def release_state(blk, flags=None, outlvl=0):
        for k in blk.keys():
            blk[k].hold_state = not blk[k].hold_state


@declare_process_block_class("TestStateBlock", block_class=SBlockBase)
class StateTestBlockData(StateBlockData):
    CONFIG = ConfigBlock(implicit=True)

    def build(self):
        super(StateTestBlockData, self).build()

        self.flow_vol = Var(initialize=20)
        self.flow_mol_phase_comp = Var(self._params.phase_list,
                                       self._params.component_list,
                                       initialize=2)
        self.test_var = Var(initialize=1)
        self.pressure = Var(initialize=1e5)
        self.temperature = Var(initialize=300)

        self.enth_mol = Var(initialize=10000)

        self.gibbs_mol_phase_comp = Var(self._params.phase_list,
                                        self._params.component_list,
                                        initialize=50)
        self.entr_mol = Var(initialize=1000)

    def get_material_flow_terms(b, p, j):
        return b.test_var

    def get_material_density_terms(b, p, j):
        return b.test_var

    def get_enthalpy_flow_terms(b, p):
        return b.test_var

    def get_energy_density_terms(b, p):
        return b.test_var

    def model_check(self):
        self.check = True

    def get_material_flow_basis(b):
        if b.config.parameters.basis_switch == 1:
            return MaterialFlowBasis.molar
        elif b.config.parameters.basis_switch == 2:
            return MaterialFlowBasis.mass
        else:
            return MaterialFlowBasis.other

    def default_material_balance_type(self):
        if self._params.default_balance_switch == 1:
            return MaterialBalanceType.componentPhase
        else:
            raise NotImplementedError

    def default_energy_balance_type(self):
        if self._params.default_balance_switch == 1:
            return EnergyBalanceType.enthalpyTotal
        else:
            raise NotImplementedError

    def define_state_vars(self):
        return {"component_flow_phase": self.flow_mol_phase_comp,
                "temperature": self.temperature,
                "pressure": self.pressure}


@declare_process_block_class("ReactionParameterTestBlock")
class _ReactionParameterBlock(ReactionParameterBlock):
    def build(self):
        super(_ReactionParameterBlock, self).build()

        self.phase_list = Set(initialize=["p1", "p2"])
        self.component_list = Set(initialize=["c1", "c2"])
        self.rate_reaction_idx = Set(initialize=["r1", "r2"])
        self.equilibrium_reaction_idx = Set(initialize=["e1", "e2"])

        self.rate_reaction_stoichiometry = {("r1", "p1", "c1"): 1,
                                            ("r1", "p1", "c2"): 1,
                                            ("r1", "p2", "c1"): 1,
                                            ("r1", "p2", "c2"): 1,
                                            ("r2", "p1", "c1"): 1,
                                            ("r2", "p1", "c2"): 1,
                                            ("r2", "p2", "c1"): 1,
                                            ("r2", "p2", "c2"): 1}
        self.equilibrium_reaction_stoichiometry = {
                                            ("e1", "p1", "c1"): 1,
                                            ("e1", "p1", "c2"): 1,
                                            ("e1", "p2", "c1"): 1,
                                            ("e1", "p2", "c2"): 1,
                                            ("e2", "p1", "c1"): 1,
                                            ("e2", "p1", "c2"): 1,
                                            ("e2", "p2", "c1"): 1,
                                            ("e2", "p2", "c2"): 1}

        self.reaction_block_class = ReactionBlock

        # Attribute to switch flow basis for testing
        self.basis_switch = 1

    @classmethod
    def define_metadata(cls, obj):
        obj.add_default_units({'time': 's',
                               'length': 'm',
                               'mass': 'g',
                               'amount': 'mol',
                               'temperature': 'K',
                               'energy': 'J',
                               'holdup': 'mol'})
        
    @classmethod
    def get_required_properties(self):
        return {}


class RBlockBase(ReactionBlockBase):
    def initialize(blk, outlvl=0, optarg=None,
                   solver=None, state_vars_fixed=False):
        for k in blk.keys():
            blk[k].init_test = True


@declare_process_block_class("ReactionBlock", block_class=RBlockBase)
class ReactionBlockData(ReactionBlockDataBase):
    CONFIG = ConfigBlock(implicit=True)

    def build(self):
        super(ReactionBlockData, self).build()

        self.reaction_rate = Var(["r1", "r2"])

        self.dh_rxn = {"r1": 10,
                       "r2": 20,
                       "e1": 30,
                       "e2": 40}

    def model_check(self):
        self.check = True

    def get_reaction_rate_basis(b):
        if b.config.parameters.basis_switch == 1:
            return MaterialFlowBasis.molar
        elif b.config.parameters.basis_switch == 2:
            return MaterialFlowBasis.mass
        else:
            return MaterialFlowBasis.other

# Need a ProcessBlockData for this...
@declare_process_block_class("AqueousEnzymeParameterBlock")
class ParameterData(PhysicalParameterBlock):
    def build(self):
        super(ParameterData, self).build()

        # all components are in the aqueous phase
        self.phase_list = Set(initialize=['aq'])
        self.component_list = Set(initialize=['S', 'E', 'C', 'P'])

        self.state_block_class = AqueousEnzymeStateBlock

    @classmethod
    def define_metadata(cls, obj):
        obj.add_default_units({'time': 's',
                               'length': 'm',
                               'mass': 'g',
                               'amount': 'mol',
                               'temperature': 'K',
                               'energy': 'J',
                               'holdup': 'mol'})


class _AqueousEnzymeStateBlock(StateBlock):
    def initialize(blk):
        for key in blk.keys():
            # Isothermal
            # Probably not the place for this
            blk[key].temperature.fix()
        pass

@declare_process_block_class("AqueousEnzymeStateBlock",
                             block_class=_AqueousEnzymeStateBlock)
class AqueousEnzymeStateBlockData(StateBlockData):
    def build(self):
        super(AqueousEnzymeStateBlockData, self).build()

        self.conc_mol = Var(self._params.component_list,
                             domain=Reals)
        self.flow_mol_comp = Var(self._params.component_list,
                                 domain=Reals)
        self.temperature = Var(initialize=303,
                               domain=Reals)

    def get_material_density_terms(b, p, j):
        return b.conc_mol[j]

    def get_material_flow_terms(b, p, j):
        return b.flow_mol_comp[j]

    def get_material_flow_basis(b):
        return MaterialFlowBasis.molar

    def define_state_vars(b):
        return {'conc_mol': b.conc_mol,
                'flow_mol_comp': b.flow_mol_comp,
                'temperature': b.temperature}

@declare_process_block_class('EnzymeReactionParameterBlock')
class ReactionData(ReactionParameterBlock):
    '''
    Enzyme reaction:
    S + E <-> C -> P + E
    '''
    def build(self):
        super(ReactionData, self).build()

        self.rate_reaction_idx = Set(initialize=['R1', 'R2', 'R3'])
        self.rate_reaction_stoichiometry = {('R1', 'aq', 'S'): -1,
                                            ('R1', 'aq', 'E'): -1,
                                            ('R1', 'aq', 'C'): 1,
                                            ('R1', 'aq', 'P'): 0,
                                            ('R2', 'aq', 'S'): 1,
                                            ('R2', 'aq', 'E'): 1,
                                            ('R2', 'aq', 'C'): -1,
                                            ('R2', 'aq', 'P'): 0,
                                            ('R3', 'aq', 'S'): 0,
                                            ('R3', 'aq', 'E'): 1,
                                            ('R3', 'aq', 'C'): -1,
                                            ('R3', 'aq', 'P'): 1}

        self.reaction_block_class = ReactionBlock

    @classmethod
    def define_metadata(cls, obj):
        obj.add_default_units({})        
        pass

class _ReactionBlock(ReactionBlockBase):
    def initialize(blk):
        # initialize for reaction rates for each data object
        pass

@declare_process_block_class('ReactionBlock',
                             block_class=_ReactionBlock)
class ReactionBlockData(ReactionBlockDataBase):
    def build(self):
        super(ReactionBlockData, self).build()

        self.k_rxn = Var(self._params.rate_reaction_idx,
                         domain=Reals)
        self.reaction_rate = Var(self._params.rate_reaction_idx,
                                 domain=Reals)
    
    def get_reaction_rate_basis(b):
        return MaterialFlowBasis.molar


