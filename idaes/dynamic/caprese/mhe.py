# -*- coding: UTF-8 -*-
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
Class for performing NMPC simulations of IDAES flowsheets
"""

from pyomo.environ import (Block, Constraint, Var, TerminationCondition,
        SolverFactory, Objective, NonNegativeReals, Reals, 
        TransformationFactory, Reference, value)
from pyomo.core.base.var import _GeneralVarData
from pyomo.core.base.range import remainder
from pyomo.kernel import ComponentSet, ComponentMap
from pyomo.dae import ContinuousSet, DerivativeVar
from pyomo.dae.flatten import flatten_dae_variables
from pyomo.dae.set_utils import is_explicitly_indexed_by, get_index_set_except
from pyomo.opt.solver import SystemCallSolver
from pyutilib.misc.config import ConfigDict, ConfigValue

from idaes.core import FlowsheetBlock
from idaes.core.util.model_statistics import (degrees_of_freedom, 
        activated_equalities_generator)
#from idaes.core.util.dyn_utils import (get_activity_dict, deactivate_model_at,
#        path_from_block, find_comp_in_block, find_comp_in_block_at_time)
from idaes.core.util import dyn_utils
from idaes.core.util.initialization import initialize_by_time_element
from idaes.dynamic.caprese.util import (initialize_by_element_in_range,
        find_slices_in_model, NMPCVarLocator, copy_values_at_time, 
        add_noise_at_time, ElementInitializationInputOption, 
        TimeResolutionOption, ControlInitOption, ControlPenaltyType,
        VariableCategory, validate_list_of_vardata, 
        validate_list_of_vardata_value_tuples, validate_solver,
        NMPCVarGroup, find_point_in_continuousset,
        get_violated_bounds_at_time)
from idaes.dynamic.caprese.base_class import DynamicBase
import idaes.logger as idaeslog

from collections import OrderedDict
import time as timemodule
import enum
import pdb

__author__ = "Robert Parker and David Thierry"


class MHESim(DynamicBase):
    """

    """
    CONFIG = DynamicBase.CONFIG

    @classmethod
    def get_namespace_name(cls):
        return '_MHE_NAMESPACE'

    def __init__(self, plant_model, plant_time_set, controller_model,
            controller_time_set, measurements_at_t0, 
            inputs_at_t0=[], **kwargs):

        self.config = self.CONFIG(kwargs)
        super(MHESim, self).__init__(plant_model, plant_time_set,
                controller_model, controller_time_set, inputs_at_t0)

        # Tag measurement vars in plant appropriately
        namespace = getattr(self.plant, self.get_namespace_name())
        namespace.measurement_vars = []
        for var in measurements_at_t0:
            info = namespace.var_locator[var]
            group = info.group
            loc = info.location
            _slice = group.varlist[loc]
            namespace.measurement_vars.append(_slice)
            for t in plant_time_set:
                namespace.var_locator[_slice[t]].is_measurement = True

        # Find measurement vars in controller and tag them appropriately
        init_controller_measurements = [
                dyn_utils.find_comp_in_block(self.controller, self.plant, comp)
                for comp in measurements_at_t0]
        namespace = getattr(self.controller, self.get_namespace_name())
        namespace.measurement_vars = []
        for var in init_controller_measurements:
            info = namespace.var_locator[var]
            group = info.group
            loc = info.location
            _slice = group.varlist[loc]
            namespace.measurement_vars.append(_slice)
            for t in controller_time_set:
                namespace.var_locator[_slice[t]].is_measurement = True


    def add_namespace_to(self, model, time):
        """
        """
        name = '_MHE_NAMESPACE'
        if hasattr(model, name):
            raise ValueError('%s already exists on model. Please fix this.'
                    % name)
        model.add_component(name, Block())
        super(MHESim, self).add_namespace_to(model, time)

    def validate_time_sets(self):
        """
        Is this necessary, or should it be done in same function as
        validate_sample_time
        """
        # NOTE: What I consider "valid" may need to change significantly
        # when I start allowing more general (concise) plant models
        sample_time = self.config.sample_time

        plant = self.p_mod
        plant_time = self.p_mod_time
        controller = self.c_mod_time

        plant_horizon = plant_time.last() - plant_time.first()
        controller_horizon = controller_time.last() - controller_time.first()

        if controller_horizon > plant_horizon:
            raise ValueError(
                    'Plant model must contain a full measurement horizon')

        # validate sample time

        # controller model: make sure horizon is integer multiple of sample
        # time, and that sample points fall on finite element boundaries.
        # (same as what's done for NMPC)

        # Plant model: make sure at least one measurement horizon, and that
        # each sample point (offset) within the (first) measurement horizon
        # falls on a finite element boundary. Only difference between this and 
        # controller model is that plant could be longer than a measurement
        # horizon, and we don't care what happens beyond this horizon.


    def validate_sample_time(plant):
        """
        """
        pass

        

