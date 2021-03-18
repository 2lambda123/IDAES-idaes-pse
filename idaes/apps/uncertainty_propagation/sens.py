# ______________________________________________________________________________
#
# Pyomo: Python Optimization Modeling Objects
# Copyright 2017 National Technology and Engineering Solutions of Sandia, LLC
# Under the terms of Contract DE-NA0003525 with National Technology and
# Engineering Solutions of Sandia, LLC, the U.S. Government retains certain
# rights in this software.
# This software is distributed under the 3-clause BSD License
# ______________________________________________________________________________

# Pyomo PR 1613: https://github.com/pyomo/pyomo/pull/1613/

from pyomo.environ import (
        Param,
        Var,
        Block,
        ComponentMap,
        Objective,
        Constraint,
        ConstraintList,
        Suffix,
        value,
        ComponentUID,
        )

from pyomo.core.base.misc import sorted_robust
from pyomo.core.expr.current import ExpressionReplacementVisitor

from pyomo.common.modeling import unique_component_name
from pyomo.common.deprecation import deprecated
from pyomo.opt import SolverFactory
import logging
import os
import shutil
logger = logging.getLogger('pyomo.contrib.sensitivity_toolbox')

@deprecated("The sipopt function has been deprecated. Use the sensitivity_calculation() "
            "function with method='sipopt' to access this functionality.",
            logger='pyomo.contrib.sensitivity_toolbox',
            version='TBD')
def sipopt(instance, paramSubList, perturbList,
           cloneModel=True, tee=False, keepfiles=False):    
    m = sensitivity_calculation('sipopt', instance, paramSubList, perturbList,
         cloneModel, tee, keepfiles, solver_options=None)

    return m

@deprecated("The kaug function has been deprecated. Use the sensitivity_calculation() "
            "function with method='kaug' to access this functionality.", 
            logger='pyomo.contrib.sensitivity_toolbox',
            version='TBD')
def kaug(instance, paramSubList, perturbList,
         cloneModel=True, tee=False, keepfiles=False, solver_options=None):
    m = sensitivity_calculation('kaug', instance, paramSubList, perturbList,
         cloneModel, tee, keepfiles, solver_options)

    return m

_SIPOPT_SUFFIXES = {
        'sens_state_0': Suffix.EXPORT,
        # ^ Not sure what this suffix does -RBP
        'sens_state_1': Suffix.EXPORT,
        'sens_state_value_1': Suffix.EXPORT,
        'sens_init_constr': Suffix.EXPORT,

        'sens_sol_state_1': Suffix.IMPORT,
        'sens_sol_state_1_z_L': Suffix.IMPORT,
        'sens_sol_state_1_z_U': Suffix.IMPORT,
        }

_K_AUG_SUFFIXES = {
        'ipopt_zL_out': Suffix.IMPORT,
        'ipopt_zU_out': Suffix.IMPORT,
        'ipopt_zL_in': Suffix.EXPORT,
        'ipopt_zU_in': Suffix.EXPORT,
        'dual': Suffix.IMPORT_EXPORT,
        'dcdp': Suffix.EXPORT,
        'DeltaP': Suffix.EXPORT,
        }

def _add_sensitivity_suffixes(block):
    suffix_dict = {}
    suffix_dict.update(_SIPOPT_SUFFIXES)
    suffix_dict.update(_K_AUG_SUFFIXES)
    for name, direction in suffix_dict.items():
        if block.component(name) is None:
            # Only add suffix if it doesn't already exist.
            # If something of this name does already exist, just
            # assume it is the proper suffix and move on.
            block.add_component(name, Suffix(direction=direction))

class _NotAnIndex(object):
    pass

def _generate_component_items(components):
    if type(components) not in {list, tuple}:
        components = (components,)
    for comp in components:
        if comp.is_indexed():
            for idx in sorted_robust(comp):
                yield idx, comp[idx]
        else:
            yield _NotAnIndex, comp

def sensitivity_calculation(method, instance, paramList, perturbList,
         cloneModel=True, tee=False, keepfiles=False, solver_options=None):
    sens = SensitivityInterface(instance, cloneModel=cloneModel)
    sens.setup_sensitivity(paramList)

    m = sens.model_instance

    if method == 'kaug':
        kaug = SolverFactory('k_aug', solver_io='nl')
        dotsens = SolverFactory('dot_sens', solver_io='nl')
        ipopt = SolverFactory('ipopt', solver_io='nl')

        ipopt.solve(m, tee=tee)
        m.ipopt_zL_in.update(m.ipopt_zL_out)  #: important!
        m.ipopt_zU_in.update(m.ipopt_zU_out)  #: important!    

        kaug.options['dsdp_mode'] = ""  #: sensitivity mode!
        kaug.solve(m, tee=tee)
        m.write('col_row.nl', format='nl', io_options={'symbolic_solver_labels':True})
    sens.perturb_parameters(perturbList)

    if method == 'sipopt':
        ipopt_sens = SolverFactory('ipopt_sens', solver_io='nl')
        ipopt_sens.options['run_sens'] = 'yes'

        # Send the model to the ipopt_sens and collect the solution
        results = ipopt_sens.solve(m, keepfiles=keepfiles, tee=tee)

    elif method == 'kaug':
        dotsens.options["dsdp_mode"] = ""
        dotsens.solve(m, tee=tee) 
        try:
            os.makedirs("dsdp")
        except FileExistsError:
            # directory already exists
            pass
        try:
            shutil.move("dsdp_in_.in","./dsdp/")
            shutil.move("col_row.nl","./dsdp/")
            shutil.move("col_row.col","./dsdp/")
            shutil.move("col_row.row","./dsdp/")
            shutil.move("conorder.txt","./dsdp/")
            shutil.move("delta_p.out","./dsdp/")
            shutil.move("dot_out.out","./dsdp/")
            shutil.move("timings_dot_driver_dsdp.txt", "./dsdp/")
            shutil.move("timings_k_aug_dsdp.txt", "./dsdp/")
        except OSError:
            pass
    return m

class SensitivityInterface(object):

    def __init__(self, instance, cloneModel=True):
        """
        """
        self._original_model = instance

        if cloneModel:
            # Note that we are not "cloning" the user's parameters
            # or perturbations.
            self.model_instance = instance.clone()
        else:
            self.model_instance = instance

    def get_default_block_name(self):
        return '_SENSITIVITY_TOOLBOX_DATA'

    def get_default_var_name(self, name):
        #return '_'.join(('sens_var', name))
        return name

    def get_default_param_name(self, name):
        #return '_'.join(('sens_param', name))
        return name

    def setup_sensitivity(self, paramList):
        """
        """
        # We need to translate the components in paramList into
        # components in our possibly cloned model.
        orig = self._original_model
        instance = self.model_instance
        if orig is not instance:
            paramList = list(
                ComponentUID(param, context=orig).find_component_on(instance)
                for param in paramList
                )

        # If a sensitivity block already exists, and we have not done
        # any expression replacement, we delete the old block, re-fix the
        # sensitivity variables, and start again.
        existing_block = instance.component(self.get_default_block_name())
        if existing_block is not None:
            if (hasattr(existing_block, 'has_replaced_expressions') and
                    not existing_block.has_replaced_expressions):
                for var, _, _, _ in existing_block._sens_data_list:
                    # Re-fix variables that the previous block was
                    # treating as parameters.
                    var.fix()
                instance.del_component(existing_block)
            else:
                msg = ("Re-using sensitivity interface is not supported "
                        "when calculating sensitivity for mutable parameters. "
                        "Used fixed vars instead if you want to do this."
                        )
                raise RuntimeError(msg)

        block = Block()
        instance.add_component(self.get_default_block_name(), block)
        self.block = block
        block._has_replaced_expressions = False
        block._sens_data_list = []
        block._paramList = paramList

        sens_data_list = block._sens_data_list
        # This is a list of (vardata, paramdata, list_idx, comp_idx) tuples.
        # Its purpose is to match corresponding vars and params and
        # to map these to a component or value in the user-provided
        # lists.
        for i, comp in enumerate(paramList):
            if comp.ctype is Param:
                if not comp.mutable:
                    raise ValueError(
                            "Parameters within paramList must be mutable. "
                            "Got %s, which is not mutable." % comp.name
                            )
                # Add a param:
                if comp.is_indexed():
                    d = {k: value(comp[k]) for k in comp.index_set()}
                    var = Var(comp.index_set(), initialize=d)
                else:
                    d = value(comp)
                    var = Var(initialize=d)
                name = self.get_default_var_name(comp.local_name)
                name = unique_component_name(block, name)
                block.add_component(name, var)

                if comp.is_indexed():
                    sens_data_list.extend(
                            (var[idx], param, i, idx)
                            for idx, param in _generate_component_items(comp)
                            )
                else:
                    sens_data_list.append((var, comp, i, _NotAnIndex))

            elif comp.ctype is Var:
                for _, data in _generate_component_items(comp):
                    if not data.fixed:
                        raise ValueError(
                                "Specified \"parameter\" variables must be "
                                "fixed. Got %s, which is not fixed."
                                % comp.name
                                )
                # Add a var:
                if comp.is_indexed():
                    d = {k: value(comp[k]) for k in comp.index_set()}
                    param = Param(comp.index_set(), mutable=True, initialize=d)
                else:
                    d = value(comp)
                    param = Param(mutable=True, initialize=d)
                name = self.get_default_param_name(comp.local_name)
                name = unique_component_name(block, name)
                block.add_component(name, param)

                if comp.is_indexed():
                    sens_data_list.extend(
                            (var, param[idx], i, idx)
                            for idx, var in _generate_component_items(comp)
                            )
                else:
                    sens_data_list.append((comp, param, i, _NotAnIndex))

        for var, _, _, _ in sens_data_list:
            # This unfixes all variables, not just those the user added.
            var.unfix()

        # Map used to replace user-provided parameters.
        variableSubMap = dict((id(param), var)
                for var, param, list_idx, _ in sens_data_list
                if paramList[list_idx].ctype is Param)

        if variableSubMap:
            # We now replace the provided parameters in the user's
            # expressions. Only do this if we have to, i.e. the
            # user provided some parameters rather than all vars.

            # Visitor that we will use to replace user-provided parameters
            # in the objective and the constraints.
            param_replacer = ExpressionReplacementVisitor(
                    substitute=variableSubMap,
                    remove_named_expressions=True,
                    )
            # TODO: Flag to ExpressionReplacementVisitor to only replace
            # named expressions if a node has been replaced within that
            # expression.

            # clone Objective, add to Block, and update any Expressions
            for obj in list(instance.component_data_objects(Objective,
                                                    active=True,
                                                    descend_into=True)):
                tempName = unique_component_name(block, obj.local_name)
                new_expr = param_replacer.dfs_postorder_stack(obj.expr)
                block.add_component(tempName, Objective(expr=new_expr))
                obj.deactivate()

            # clone Constraints, add to Block, and update any Expressions
            #
            # Unfortunate that this deactivates and replaces constraints
            # even if they don't contain the parameters.
            # In fact it will do this even if the user only specified fixed
            # variables.
            # 
            block.constList = ConstraintList()
            for con in list(instance.component_data_objects(Constraint, 
                                           active=True,
                                           descend_into=True)):
                if con.equality:
                    new_expr = param_replacer.dfs_postorder_stack(con.expr)
                    block.constList.add(expr=new_expr)
                else:
                    if con.lower is None or con.upper is None:
                        new_expr = param_replacer.dfs_postorder_stack(con.expr)
                        block.constList.add(expr=new_expr)
                    else:
                        # Constraint must be a ranged inequality, break into
                        # separate constraints
                        new_body = param_replacer.dfs_postorder_stack(con.body)
                        new_lower = param_replacer.dfs_postorder_stack(con.lower)
                        new_upper = param_replacer.dfs_postorder_stack(con.upper)

                        # Add constraint for lower bound
                        block.constList.add(expr=(new_lower <= new_upper))

                        # Add constraint for upper bound
                        block.constList.add(expr=(new_upper >= new_body))
                con.deactivate()

            # Assume that we just replaced some params
            block._has_replaced_expressions = True

        block.paramConst = ConstraintList()
        for var, param, _, _ in sens_data_list:
            #block.paramConst.add(param - var == 0)
            block.paramConst.add(var - param == 0)

        # Declare Suffixes
        _add_sensitivity_suffixes(instance)
        
        for i, (var, _, _, _) in enumerate(sens_data_list):
            idx = i + 1
            con = block.paramConst[idx]

            # sipopt
            instance.sens_state_0[var] = idx
            instance.sens_state_1[var] = idx
            instance.sens_init_constr[con] = idx

            # k_aug
            instance.dcdp[con] = idx


    def perturb_parameters(self, perturbList): 
        """
        """
        # Note that entries of perturbList need not be components
        # of the cloned model. All we need are the values.
        instance = self.model_instance
        sens_data_list = self.block._sens_data_list
        paramConst = self.block.paramConst

        if len(self.block._paramList) != len(perturbList):
            raise ValueError(
                    "Length of paramList argument does not equal "
                    "length of perturbList")

        for i, (var, param, list_idx, comp_idx) in enumerate(sens_data_list):
            con = paramConst[i+1]
            if comp_idx is _NotAnIndex:
                ptb = value(perturbList[list_idx])
            else:
                try:
                    ptb = value(perturbList[list_idx][comp_idx])
                except TypeError:
                    # If the user provided a scalar value to perturb
                    # an indexed component.
                    ptb = value(perturbList[list_idx])

            # sipopt
            instance.sens_state_value_1[var] = ptb

            # k_aug
            #instance.DeltaP[con] = value(ptb - var)
            instance.DeltaP[con] = value(var - ptb)
            # FIXME: ^ This is incorrect. DeltaP should be (ptb - current).
            # But at least one test doesn't pass unless I use (current - ptb).
