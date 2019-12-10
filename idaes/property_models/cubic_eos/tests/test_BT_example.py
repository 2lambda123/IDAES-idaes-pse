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
import pytest

from idaes.core import FlowsheetBlock, ControlVolume0DBlock
from idaes.property_models.cubic_eos.cubic_prop_pack import \
    cubic_roots_available
from idaes.property_models.cubic_eos import BT_PR

from pyomo.environ import (ConcreteModel,
                           Objective,
                           SolverFactory,
                           TerminationCondition,
                           value)


# Set module level pyest marker
pytestmark = pytest.mark.cubic_root
prop_available = cubic_roots_available()


@pytest.mark.skipif(not prop_available,
                    reason="Cubic root finder not available")
class TestBTExample(object):
    def test_CV_integration(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(default={'dynamic': False})

        m.fs.params = BT_PR.BTParameterBlock(
                default={'valid_phase': ('Vap', 'Liq')})

        m.fs.cv = ControlVolume0DBlock(default={
                "property_package": m.fs.params})

        m.fs.cv.add_geometry()

        m.fs.cv.add_state_blocks(has_phase_equilibrium=True)

        m.fs.cv.add_material_balances(has_phase_equilibrium=True)

        m.fs.cv.add_energy_balances()

        m.fs.cv.add_momentum_balances()

    def test_T_sweep(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(default={'dynamic': False})

        m.fs.props = BT_PR.BTParameterBlock(
                default={'valid_phase': ('Vap', 'Liq')})

        m.fs.state = m.fs.props.state_block_class(
                default={'parameters': m.fs.props,
                         'defined_state': True})

        m.fs.obj = Objective(expr=(m.fs.state.temperature - 510)**2)

        for logP in range(8, 13, 1):
            m.fs.obj.deactivate()

            m.fs.state.flow_mol.fix(100)
            m.fs.state.mole_frac_comp["benzene"].fix(0.5)
            m.fs.state.mole_frac_comp["toluene"].fix(0.5)
            m.fs.state.temperature.fix(300)
            m.fs.state.pressure.fix(10**(0.5*logP))

            m.fs.state.initialize(outlvl=0)

            m.fs.state.temperature.unfix()
            m.fs.obj.activate()

            solver = SolverFactory('ipopt')
            results = solver.solve(m, tee=True)

            assert results.solver.termination_condition == \
                TerminationCondition.optimal
            assert m.fs.state.flow_mol_phase["Liq"].value <= 1e-5

    def test_P_sweep(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(default={'dynamic': False})

        m.fs.props = BT_PR.BTParameterBlock(
                default={'valid_phase': ('Vap', 'Liq')})

        m.fs.state = m.fs.props.state_block_class(
                default={'parameters': m.fs.props,
                         'defined_state': True})

        for T in range(370, 500, 25):
            m.fs.state.flow_mol.fix(100)
            m.fs.state.mole_frac_comp["benzene"].fix(0.5)
            m.fs.state.mole_frac_comp["toluene"].fix(0.5)
            m.fs.state.temperature.fix(T)
            m.fs.state.pressure.fix(1e5)

            m.fs.state.initialize(outlvl=0)

            solver = SolverFactory('ipopt')
            results = solver.solve(m)

            assert results.solver.termination_condition == \
                TerminationCondition.optimal

            while m.fs.state.pressure.value <= 1e6:
                m.fs.state.pressure.value = m.fs.state.pressure.value + 1e5
                solver = SolverFactory('ipopt')
                results = solver.solve(m)
                assert results.solver.termination_condition == \
                    TerminationCondition.optimal
                print(T, m.fs.state.pressure.value)

    def test_T350_P1_x5(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(default={'dynamic': False})

        m.fs.props = BT_PR.BTParameterBlock(
                default={'valid_phase': ('Vap', 'Liq')})

        m.fs.state = m.fs.props.state_block_class(
                default={'parameters': m.fs.props,
                         'defined_state': True})

        m.fs.state.flow_mol.fix(100)
        m.fs.state.mole_frac_comp["benzene"].fix(0.5)
        m.fs.state.mole_frac_comp["toluene"].fix(0.5)
        m.fs.state.temperature.fix(350)
        m.fs.state.pressure.fix(1e5)

        # Trigger build of enthalpy and entropy
        m.fs.state.enth_mol_phase
        m.fs.state.entr_mol_phase

        m.fs.state.initialize(outlvl=0)

        solver = SolverFactory('ipopt')
        solver.solve(m)

        assert pytest.approx(value(m.fs.state._teq), abs=1e-1) == 365
        assert 0.0035346 == pytest.approx(
                value(m.fs.state.compress_fact_phase["Liq"]), 1e-5)
        assert 0.966749 == pytest.approx(
                value(m.fs.state.compress_fact_phase["Vap"]), 1e-5)
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "benzene"]),
                1e-5) == 0.894676
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "toluene"]),
                1e-5) == 0.347566
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "benzene"]),
                1e-5) == 0.971072
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "toluene"]),
                1e-5) == 0.959791

        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "benzene"]),
                1e-5) == 0.5
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "toluene"]),
                1e-5) == 0.5
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "benzene"]),
                1e-5) == 0.70584
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "toluene"]),
                1e-5) == 0.29416

        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Liq"]), 1e-5) == 38942.8
        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Vap"]), 1e-5) == 78048.7
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Liq"]), 1e-5) == -367.558
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Vap"]), 1e-5) == -269.0553

    def test_T350_P5_x5(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(default={'dynamic': False})

        m.fs.props = BT_PR.BTParameterBlock(
                default={'valid_phase': ('Vap', 'Liq')})

        m.fs.state = m.fs.props.state_block_class(
                default={'parameters': m.fs.props,
                         'defined_state': True})

        m.fs.state.flow_mol.fix(100)
        m.fs.state.mole_frac_comp["benzene"].fix(0.5)
        m.fs.state.mole_frac_comp["toluene"].fix(0.5)
        m.fs.state.temperature.fix(350)
        m.fs.state.pressure.fix(5e5)

        # Trigger build of enthalpy and entropy
        m.fs.state.enth_mol_phase
        m.fs.state.entr_mol_phase

        m.fs.state.initialize(outlvl=0)

        solver = SolverFactory('ipopt')
        solver.solve(m)

        assert pytest.approx(value(m.fs.state._teq), 1e-5) == 431.47
        assert pytest.approx(
                value(m.fs.state.compress_fact_phase["Liq"]), 1e-5) == 0.01766
        assert pytest.approx(
                value(m.fs.state.compress_fact_phase["Vap"]), 1e-5) == 0.80245
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "benzene"]),
                1e-5) == 0.181229
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "toluene"]),
                1e-5) == 0.070601
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "benzene"]),
                1e-5) == 0.856523
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "toluene"]),
                1e-5) == 0.799237

        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "benzene"]),
                1e-5) == 0.5
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "toluene"]),
                1e-5) == 0.5
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "benzene"]),
                1e-5) == 0.65415
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "toluene"]),
                1e-5) == 0.34585

        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Liq"]), 1e-5) == 38966.9
        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Vap"]), 1e-5) == 75150.7
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Liq"]), 1e-5) == -367.6064
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Vap"]), 1e-5) == -287.3318

    def test_T450_P1_x5(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(default={'dynamic': False})

        m.fs.props = BT_PR.BTParameterBlock(
                default={'valid_phase': ('Vap', 'Liq')})

        m.fs.state = m.fs.props.state_block_class(
                default={'parameters': m.fs.props,
                         'defined_state': True})

        m.fs.state.flow_mol.fix(100)
        m.fs.state.mole_frac_comp["benzene"].fix(0.5)
        m.fs.state.mole_frac_comp["toluene"].fix(0.5)
        m.fs.state.temperature.fix(450)
        m.fs.state.pressure.fix(1e5)

        # Trigger build of enthalpy and entropy
        m.fs.state.enth_mol_phase
        m.fs.state.entr_mol_phase

        m.fs.state.initialize(outlvl=0)

        solver = SolverFactory('ipopt')
        solver.solve(m)

        assert pytest.approx(value(m.fs.state._teq), 1e-5) == 371.4
        assert 0.0033583 == pytest.approx(
                value(m.fs.state.compress_fact_phase["Liq"]), 1e-5)
        assert 0.9821368 == pytest.approx(
                value(m.fs.state.compress_fact_phase["Vap"]), 1e-5)
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "benzene"]),
                1e-5) == 8.069323
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "toluene"]),
                1e-5) == 4.304955
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "benzene"]),
                1e-5) == 0.985365
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "toluene"]),
                1e-5) == 0.979457

        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "benzene"]),
                1e-5) == 0.29861
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "toluene"]),
                1e-5) == 0.70139
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "benzene"]),
                1e-5) == 0.5
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "toluene"]),
                1e-5) == 0.5

        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Liq"]), 1e-5) == 49441.2
        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Vap"]), 1e-5) == 84175.1
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Liq"]), 1e-5) == -333.836
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Vap"]), 1e-5) == -247.385

    def test_T450_P5_x5(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(default={'dynamic': False})

        m.fs.props = BT_PR.BTParameterBlock(
                default={'valid_phase': ('Vap', 'Liq')})

        m.fs.state = m.fs.props.state_block_class(
                default={'parameters': m.fs.props,
                         'defined_state': True})

        m.fs.state.flow_mol.fix(100)
        m.fs.state.mole_frac_comp["benzene"].fix(0.5)
        m.fs.state.mole_frac_comp["toluene"].fix(0.5)
        m.fs.state.temperature.fix(450)
        m.fs.state.pressure.fix(5e5)

        # Trigger build of enthalpy and entropy
        m.fs.state.enth_mol_phase
        m.fs.state.entr_mol_phase

        m.fs.state.initialize(outlvl=0)

        solver = SolverFactory('ipopt')
        solver.solve(m)

        assert pytest.approx(value(m.fs.state._teq), 1e-5) == 436.93
        assert 0.0166181 == pytest.approx(
                value(m.fs.state.compress_fact_phase["Liq"]), 1e-5)
        assert 0.9053766 == pytest.approx(
                value(m.fs.state.compress_fact_phase["Vap"]), 1e-5)
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "benzene"]),
                1e-5) == 1.63308
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "toluene"]),
                1e-5) == 0.873213
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "benzene"]),
                1e-5) == 0.927534
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "toluene"]),
                1e-5) == 0.898324

        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "benzene"]),
                1e-5) == 0.3488737
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "toluene"]),
                1e-5) == 0.6511263
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "benzene"]),
                1e-5) == 0.5
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "toluene"]),
                1e-5) == 0.5

        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Liq"]), 1e-5) == 51095.2
        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Vap"]), 1e-5) == 83362.3
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Liq"]), 1e-5) == -331.676
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Vap"]), 1e-5) == -261.961

    def test_T368_P1_x5(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(default={'dynamic': False})

        m.fs.props = BT_PR.BTParameterBlock(
                default={'valid_phase': ('Vap', 'Liq')})

        m.fs.state = m.fs.props.state_block_class(
                default={'parameters': m.fs.props,
                         'defined_state': True})

        m.fs.state.flow_mol.fix(100)
        m.fs.state.mole_frac_comp["benzene"].fix(0.5)
        m.fs.state.mole_frac_comp["toluene"].fix(0.5)
        m.fs.state.temperature.fix(368)
        m.fs.state.pressure.fix(1e5)

        # Trigger build of enthalpy and entropy
        m.fs.state.enth_mol_phase
        m.fs.state.entr_mol_phase

        m.fs.state.initialize(outlvl=0)

        solver = SolverFactory('ipopt')
        solver.solve(m)

        assert pytest.approx(value(m.fs.state._teq), 1e-5) == 368
        assert 0.003504 == pytest.approx(
                value(m.fs.state.compress_fact_phase["Liq"]), 1e-5)
        assert 0.97 == pytest.approx(
                value(m.fs.state.compress_fact_phase["Vap"]), 1e-5)
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "benzene"]),
                1e-5) == 1.492049
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "toluene"]),
                1e-5) == 0.621563
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "benzene"]),
                1e-5) == 0.97469
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "toluene"]),
                1e-5) == 0.964642

        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "benzene"]),
                1e-5) == 0.4012128
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "toluene"]),
                1e-5) == 0.5987872
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "benzene"]),
                1e-5) == 0.6141738
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "toluene"]),
                1e-5) == 0.3858262

        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Liq"]), 1e-5) == 38235.1
        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Vap"]), 1e-5) == 77155.4
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Liq"]), 1e-5) == -364.856
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Vap"]), 1e-5) == -267.892

    def test_T376_P1_x2(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(default={'dynamic': False})

        m.fs.props = BT_PR.BTParameterBlock(
                default={'valid_phase': ('Vap', 'Liq')})

        m.fs.state = m.fs.props.state_block_class(
                default={'parameters': m.fs.props,
                         'defined_state': True})

        m.fs.state.flow_mol.fix(100)
        m.fs.state.mole_frac_comp["benzene"].fix(0.2)
        m.fs.state.mole_frac_comp["toluene"].fix(0.8)
        m.fs.state.temperature.fix(376)
        m.fs.state.pressure.fix(1e5)

        # Trigger build of enthalpy and entropy
        m.fs.state.enth_mol_phase
        m.fs.state.entr_mol_phase

        m.fs.state.initialize(outlvl=0)

        solver = SolverFactory('ipopt')
        solver.solve(m)

        assert pytest.approx(value(m.fs.state._teq), 1e-5) == 376
        assert 0.00361333 == pytest.approx(
                value(m.fs.state.compress_fact_phase["Liq"]), 1e-5)
        assert 0.968749 == pytest.approx(
                value(m.fs.state.compress_fact_phase["Vap"]), 1e-5)
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "benzene"]),
                1e-5) == 1.8394188
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Liq", "toluene"]),
                1e-5) == 0.7871415
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "benzene"]),
                1e-5) == 0.9763608
        assert pytest.approx(
                value(m.fs.state.fug_coeff_phase_comp["Vap", "toluene"]),
                1e-5) == 0.9663611

        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "benzene"]),
                1e-5) == 0.17342
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Liq", "toluene"]),
                1e-5) == 0.82658
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "benzene"]),
                1e-5) == 0.3267155
        assert pytest.approx(
                value(m.fs.state.mole_frac_phase_comp["Vap", "toluene"]),
                1e-5) == 0.6732845

        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Liq"]), 1e-5) == 31535.8
        assert pytest.approx(
                value(m.fs.state.enth_mol_phase["Vap"]), 1e-5) == 69175.3
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Liq"]), 1e-5) == -372.869
        assert pytest.approx(
                value(m.fs.state.entr_mol_phase["Vap"]), 1e-5) == -278.766
