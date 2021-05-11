import default
import logging


def verify_region_record(regions):
    # Verify region record
    for region_id, region in regions.items():
        # print(f'{region_id} net interchange record {region.net_interchange_record} calculate {region.net_interchange_record_temp}')
        if abs(region.dispatchable_generation_record - region.dispatchable_generation_temp) > 1:
            logging.warning(
                f'Region {region_id} dispatchable generation record {region.dispatchable_generation_record} but sum of total cleared {region.dispatchable_generation_temp}')
        if abs(region.dispatchable_load_record - region.dispatchable_load_temp) > 1:
            logging.warning(
                f'Region {region_id} dispatchable load record {region.dispatchable_load_record} but sum of total cleared {region.dispatchable_load_temp}')
        if abs(region.available_generation_record - region.available_generation) > 1:
            logging.warning(
                f'Region {region_id} available generation record {region.available_generation_record} but our calculation {region.available_generation}')
        if abs(region.available_load_record - region.available_load) > 1:
            logging.warning(
                f'Region {region_id} available load record {region.available_load_record} but our calculation {region.available_load}')
        for bid_type, record in region.fcas_local_dispatch_record.items():
            # print(f'{region_id} {bid_type} record {record} sum {region.fcas_local_dispatch_record_temp[bid_type]}')
            if abs(record - region.fcas_local_dispatch_record_temp[bid_type]) > 1:
                logging.warning(
                    f'Region {region_id} {bid_type} record {record} but sum of target {region.fcas_local_dispatch_record_temp[bid_type]}')


def verify_binding_constr(model, constraints):
    for constr in model.getConstrs():
        if constr.slack is not None and constr.slack != 0 and constr.constrName in constraints and constraints[
            constr.constrName].bind_flag:
            logging.warning(f'Constraint {constr.constrName} is not binding but record is')
        elif constr.slack is not None and constr.slack == 0 and constr.constrName in constraints and not constraints[constr.constrName].bind_flag:
            logging.warning(f'Constraint {constr.constrName} is binding but record not.')
        elif constr.slack is not None and constr.slack == 0 and constr.constrName in constraints and constraints[constr.constrName].bind_flag:
            continue
            print('yes')


def debug_infeasible_model(model):
    print('Infeasible model!!!')
    logging.debug('The model is infeasible; computing IIS')
    model.computeIIS()
    logging.debug('\nThe following constraint(s) cannot be satisfied:')
    for c in model.getConstrs():
        if c.IISConstr:
            logging.debug(f'Constraint name: {c.constrName}')
            logging.debug(f'Constraint sense: {c.sense}')
            logging.debug(f'Constraint rhs: {c.rhs}')


def check_violation(model, regions, slack_variables, generic_slack_variables):
    # Check slack variables for soft constraints
    for region_id, region in regions.items():
        logging.debug('{} Deficit: {}'.format(region_id, region.deficit_gen.x))
        logging.debug('{} Surplus: {}'.format(region_id, region.surplus_gen.x))
    logging.debug('Slack variables:')
    for name in slack_variables:
        var = model.getVarByName(name)
        if var is not None and var.x != 0:
            logging.debug('{}'.format(var))
    logging.debug('Slack variables for generic constraints:')
    for name in generic_slack_variables:
        var = model.getVarByName(name)
        if var.x != 0:
            logging.debug('{}'.format(var))


def compare_total_cleared_and_fcas(units):
    # Compare total cleared and FCAS value with AEMO record
    for duid, unit in units.items():
        if unit.total_cleared_record is not None and abs(unit.total_cleared_record - (0 if type(unit.total_cleared) == float else unit.total_cleared.x)) > 1:
            logging.debug(f'ENERGY {unit.region_id} {duid} {unit.total_cleared.x} record {unit.total_cleared_record}')
        if unit.fcas_bids != {}:
            for bid_type, fcas in unit.fcas_bids.items():
                if abs(unit.target_record[bid_type] - (0 if type(fcas.value) == float else fcas.value.x)) > 1:
                    logging.debug(f'{bid_type} {unit.region_id} {duid} {0 if type(fcas.value) == float else fcas.value.x} record {unit.target_record[bid_type]}')


def print_energy_bands(energy_bands):
    for d in energy_bands.values():
        for dd in d.values():
            for p, l in dd.items():
                if len(l) > 1:
                    print(p)
                    print(l)


def check_binding_generic_fcas_constraints(regions, constraints):
    for region_id, region in regions.items():
        for bid_type, fcas_constraints in region.fcas_constraints.items():
            for constr_name in fcas_constraints:
                constr = constraints[constr_name]
                if constr.bind_flag and constr.constr.pi != 0:
                    logging.debug(f'{region_id} {bid_type} {constr.constr.pi}')
