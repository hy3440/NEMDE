import constrain
import datetime
import debug
import fcas_constraints
import gurobipy
import helpers
import ic_constraints
import interconnect
import logging
import offer
import result
import xml_parser
import preprocess
import unit_constraints


def add_regional_energy_demand_supply_balance_constr(model, region, region_id, hard_flag, slack_variables, penalty, voll, cvp):
    # Regional energy demand supply balance constraint
    region.deficit_gen = model.addVar(name=f'Deficit_Gen_{region_id}')  # Item20
    slack_variables.add(f'Deficit_Gen_{region_id}')
    penalty += region.deficit_gen * cvp['Region_Load_Shedding'] * voll
    region.surplus_gen = model.addVar(name=f'Surplus_Gen_{region_id}')  # Item21
    slack_variables.add(f'Deficit_Gen_{region_id}')
    penalty += region.surplus_gen * cvp['Excess_Generation'] * voll
    if hard_flag:
        model.addConstr(region.deficit_gen, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'DEFICIT_GEN_{region_id}')
        model.addConstr(region.surplus_gen, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'SURPLUS_GEN_{region_id}')
    region.rrp_constr = model.addConstr(
        region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen,
        sense=gurobipy.GRB.EQUAL, rhs=region.total_demand + region.dispatchable_load + region.losses,
        name=f'REGION_BALANCE_{region_id}')
    if abs(
            region.dispatchable_generation_record + region.net_mw_flow_record - region.total_demand - region.dispatchable_load_record - region.losses_record) > 0.01:
        logging.warning(f'Region {region_id} imbalance lhs = {region.dispatchable_generation_record + region.net_mw_flow_record} rhs = {region.total_demand + region.dispatchable_load_record + region.losses_record}')
    return penalty


def dispatch(cvp, start, interval, process,
             hard_flag=False,  # Apply hard constraints
             fcas_flag=True,  # Calculate FCAS
             constr_flag=True,  # Apply generic constraints
             losses_flag=True,  # Calculate interconnectors losses
             fixed_interflow_flag=False,  # Fix interflow
             fixed_target_flag=False,  # Fix generator target
             link_flag=True,  # Calculate links
             dual_flag=True,  # Calculate dual var as price
             ic_record_flag=False  # Apply interconnector import/export limit record
             ):
    try:
        intervals = 30 if process == 'predispatch' else 5  # Length of the dispatch interval in minutes
        current = start + interval * datetime.timedelta(minutes=intervals)  # Current interval datetime
        logging.info('----------------------------------------------------------------------------------')
        logging.info(f'Current interval is {current} (No. {interval} starting at {start}) for {process}')
        model = gurobipy.Model(f'{preprocess.get_case_datetime(current)}')
        model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
        cost, penalty = 0, 0
        slack_variables = set()

        # Get market price cap (MPC) and floor
        voll, market_price_floor = constrain.get_market_price(current)
        # Get regions, interconnectors, and case solution
        regions, interconnectors, solution, links = interconnect.get_regions_and_interconnectors(current, start, interval, process, fcas_flag, link_flag)
        # Get units and connection points
        units, connection_points = offer.get_units(current, start, interval, process, fcas_flag)
        # Add NEM SPD outputs
        violation_prices = xml_parser.add_nemspdoutputs(current, units, links, link_flag)

        for ic_id, ic in interconnectors.items():
            # Define interconnector MW flow
            ic.mw_flow = model.addVar(lb=-gurobipy.GRB.INFINITY, name=f'Mw_Flow_{ic_id}')
            # Add interconnector capacity constraint
            penalty = ic_constraints.add_interconnector_capacity_constr(model, ic, ic_id, hard_flag, slack_variables, penalty, voll, cvp)
            # Add interconnector export/import limit constraint
            if ic_record_flag:
                ic_constraints.add_interconnector_limit_constr(model, ic, ic_id)
            # Allocate inter-flow to regions
            if not link_flag or (link_flag and ic_id != 'T-V-MNSP1'):
                regions[ic.region_to].net_mw_flow_record += ic.mw_flow_record
                regions[ic.region_from].net_mw_flow_record -= ic.mw_flow_record
                regions[ic.region_to].net_mw_flow += ic.mw_flow
                regions[ic.region_from].net_mw_flow -= ic.mw_flow
                regions[ic.region_to].net_interchange_record_temp -= ic.mw_flow_record
                regions[ic.region_from].net_interchange_record_temp += ic.mw_flow_record
            # Fix inter-flow (custom flag for testing the model)
            if fixed_interflow_flag:
                model.addConstr(ic.mw_flow, sense=gurobipy.GRB.EQUAL, rhs=ic.mw_flow_record, name=f'FIXED_INTERFLOW_{ic_id}')
                # model.addConstr(ic.mw_losses, sense=gurobipy.GRB.EQUAL, rhs=ic.mw_losses_record, name=f'FIXED_INTERLOSSES_{ic_id}')

        if link_flag:
            for link_id, link in links.items():
                # Avail at each price band
                link.offers = [model.addVar(ub=avail, name=f'Target{no}_{link_id}') for no, avail in enumerate(link.band_avail)]
                # Link flow
                link.mw_flow = model.addVar(name=f'Link_Flow_{link_id}')
                # Add MNSPInterconnector ramp rate constraint
                penalty = ic_constraints.add_mnsp_ramp_constr(model, intervals, link, link_id, hard_flag, slack_variables, penalty, voll, cvp)
                # Add total band MW offer constraint - MNSP only
                penalty = ic_constraints.add_mnsp_total_band_constr(model, link, link_id, hard_flag, slack_variables, penalty, voll, cvp)
                # MNSP Max Capacity
                if link.max_capacity is not None:
                    if link.mw_flow_record is not None and link.mw_flow_record > link.max_capacity:
                        logging.warning(f'Link {link_id} mw flow record {link.mw_flow_record} above max capacity {link.max_capacity}')
                # Add MNSP availability constraint
                penalty = ic_constraints.add_mnsp_avail_constr(model, link, link_id, hard_flag, slack_variables, penalty, voll, cvp)

                link.from_cost = sum([o * (p / link.from_region_tlf) for o, p in zip(link.offers, link.price_band)])
                link.to_cost = sum([o * (p / link.to_region_tlf) for o, p in zip(link.offers, link.price_band)])
                # Add cost to objective
                cost -= link.from_cost  # As load for from_region
                cost += link.to_cost  # As generator for to_region

                regions[link.from_region].net_mw_flow -= link.mw_flow * link.from_region_tlf
                regions[link.to_region].net_mw_flow += link.mw_flow * link.to_region_tlf
                regions[link.from_region].net_mw_flow_record -= link.mw_flow_record * link.from_region_tlf
                regions[link.to_region].net_mw_flow_record += link.mw_flow_record * link.to_region_tlf
                regions[link.from_region].net_interchange_record_temp += link.mw_flow_record * link.to_region_tlf
                regions[link.to_region].net_interchange_record_temp -= link.mw_flow_record * link.to_region_tlf

            model.addConstr(interconnectors['T-V-MNSP1'].mw_flow, sense=gurobipy.GRB.EQUAL, rhs=links['BLNKTAS'].mw_flow - links['BLNKVIC'].mw_flow, name='BASSLINK_CONSTR')
            if fixed_target_flag or fixed_interflow_flag or dual_flag:
                if links['BLNKTAS'].mw_flow_record == 0:
                    model.addConstr(links['BLNKTAS'].mw_flow, sense=gurobipy.GRB.EQUAL, rhs=0, name='BASSLINK_BLNKTAS')
                else:
                    model.addConstr(links['BLNKVIC'].mw_flow, sense=gurobipy.GRB.EQUAL, rhs=0, name='BASSLINK_BLNKVIC')
            else:
                model.addSOS(gurobipy.GRB.SOS_TYPE1, [links['BLNKTAS'].mw_flow, links['BLNKVIC'].mw_flow])

        # Calculate inter-region losses
        if losses_flag:
            if fixed_target_flag or dual_flag or fixed_interflow_flag:
                interconnect.calculate_interconnector_losses(model, regions, interconnectors)
            else:
                interconnect.sos_calculate_interconnector_losses(model, regions, interconnectors)

        xml_parser.add_nemspdoutputs_fcas(current, units, xml_parser.add_fcas)
        # xml_parser.add_nemspdoutputs_fcas(current, units, xml_parser.verify_fcas)

        for unit in units.values():
            # Unit participates in the energy market
            if unit.energy is not None:
                # Dispatch target at each price band
                for no, avail in enumerate(unit.energy.band_avail):
                    bid_offer = model.addVar(name=f'Energy_Avail{no}_{unit.duid}')
                    unit.offers.append(bid_offer)
                    model.addConstr(bid_offer <= avail, name=f'ENERGY_AVAIL{no}_{unit.duid}')
                # Total dispatch total_cleared
                unit.total_cleared = model.addVar(name=f'Total_Cleared_{unit.duid}')
                # Unit max cap (not included yet)
                if unit.max_capacity is not None:
                    # model.addConstr(unit.total_cleared <= unit.max_capacity, name='MAX_CAPACITY_{}'.format(unit.duid))
                    if unit.total_cleared_record is not None and unit.total_cleared_record > unit.max_capacity:
                        logging.warning(f'{unit.dispatch_type} {unit.duid} total cleared record {unit.total_cleared_record} above max capacity {unit.max_capacity}')
                # Add Unit MaxAvail constraint (only constr for loads included)
                if unit.energy.max_avail is not None:
                    penalty = unit_constraints.add_max_avail_constr(model, unit, hard_flag, slack_variables, penalty, voll, cvp)
                    if unit.total_cleared_record is not None and unit.total_cleared_record > unit.energy.max_avail:
                        logging.warning(f'{unit.dispatch_type} {unit.duid} total cleared record {unit.total_cleared_record} above max avail {unit.energy.max_avail} (total band {sum(unit.energy.band_avail)})')
                # Add total band MW offer constraint
                penalty = unit_constraints.add_total_band_constr(model, unit, hard_flag, slack_variables, penalty, voll, cvp)
                # Add Unconstrained Intermittent Generation Forecasts (UIGF) constraint
                penalty = unit_constraints.add_uigf_constr(model, unit, regions, hard_flag, slack_variables, penalty, voll, cvp)
                # Add on-line dispatch fast start inflexibility profile constraint
                if process == 'dispatch':
                    penalty = unit_constraints.add_fast_start_inflexibility_profile_constr(model, unit, hard_flag, slack_variables, penalty, voll, cvp)
                # Add unit ramp rate constraint
                # If the total MW value of its bid/offer bands is zero or the unit is a fast start unit and it is
                # targeted to be in mode 0, 1, or 2, its ramp rate constraints will be ignored.
                if sum(unit.energy.band_avail) > 0 and (unit.start_type != 'FAST' or (helpers.condition1(process, interval) and unit.dispatch_mode > 2)):
                    penalty = unit_constraints.add_unit_ramp_constr(model, intervals, unit, hard_flag, slack_variables, penalty, voll, cvp)
                # Add fixed loading constraint
                penalty = unit_constraints.add_fixed_loading_constr(model, unit, hard_flag, slack_variables, penalty, voll, cvp)
                # Marginal loss factor
                if unit.transmission_loss_factor is None:
                    logging.error(f'{unit.dispatch_type} {unit.duid} has no MLF.')
                    unit.transmission_loss_factor = 1.0
                # Calculate cost
                cost = unit_constraints.add_cost(unit, regions, cost)
                # Fix unit dispatch target (custom flag for testing the model)
                # if fixed_target_flag and unit.dispatch_type == 'GENERATOR':
                if fixed_target_flag:
                    model.addConstr(unit.total_cleared, sense=gurobipy.GRB.EQUAL, rhs=unit.total_cleared_record, name=f'ENERGY_FIXED_{unit.duid}')

            # Unit is registered for FCAS only
            else:
                unit.total_cleared = 0.0

            # Unit participates in FCAS markets
            if unit.fcas_bids != {} and fcas_flag:
                # Bid for energy and FCAS
                if unit.energy is not None:
                    # Preprocess
                    fcas_constraints.preprocess_fcas(model, unit, process, interval, intervals)
                    # Co-optimise
                    for bid_type, fcas in unit.fcas_bids.items():
                        if fcas.enablement_status == 1:
                            cost, penalty = fcas_constraints.process_fcas_bid(model, unit, fcas, bid_type, hard_flag, slack_variables, penalty, voll, cvp, cost, regions)
                            # Add FCAS EnablementMin constr
                            penalty = fcas_constraints.add_enablement_min_constr(model, unit, fcas, bid_type, hard_flag, slack_variables, penalty, voll, cvp)
                            # Add FCAS EnablementMax constr
                            penalty = fcas_constraints.add_enablement_max_constr(model, unit, fcas, bid_type, hard_flag, slack_variables, penalty, voll, cvp)
                            if bid_type == 'RAISEREG' or bid_type == 'LOWERREG':
                                # Add joint ramping constraint
                                if helpers.condition2(process, interval):
                                    penalty = fcas_constraints.add_joint_ramping_constr(model, intervals, unit, fcas, bid_type, hard_flag,
                                                                       slack_variables, penalty, voll, cvp)
                                # Add energy and regulating FCAS capacity constraint
                                fcas_constraints.add_energy_and_fcas_capacity_constr(model, unit, fcas, bid_type)
                            else:
                                penalty = fcas_constraints.add_joint_capacity_constr(model, unit, fcas, bid_type, hard_flag, slack_variables,
                                                          penalty, voll, cvp)
                        else:
                            if unit.target_record[bid_type] != 0:
                                logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} is not enable but record {unit.target_record[bid_type]}')
                # Only bid for FCAS
                else:
                    for bid_type, fcas in unit.fcas_bids.items():
                        cost, penalty = fcas_constraints.process_fcas_bid(model, unit, fcas, bid_type, hard_flag, slack_variables, penalty, voll, cvp, cost, regions)
                # # Fix unit dispatch target (custom flag for testing the model)
                # if fixed_target_flag:
                #     if fcas_flag and unit.fcas_bids != {}:
                #         for bid_type, fcas in unit.fcas_bids.items():
                #             model.addConstr(fcas.value, gurobipy.GRB.EQUAL, unit.target_record[bid_type], name=f'{bid_type}_FIXED_{unit.duid}')

        # Region FCAS local dispatch
        if fcas_flag:
            for region_id, region in regions.items():
                for bid_type, target in region.fcas_local_dispatch_temp.items():
                    region.fcas_local_dispatch[bid_type] = model.addVar(name=f'Local_Dispatch_{bid_type}_{region_id}')
                    model.addConstr(region.fcas_local_dispatch[bid_type], sense=gurobipy.GRB.EQUAL, rhs=target, name=f'LOCAL_DISPATCH_SUM_{bid_type}_{region_id}')
                    # model.addConstr(region.fcas_local_dispatch[bid_type], sense=gurobipy.GRB.EQUAL, rhs=region.fcas_local_dispatch_record[bid_type], name=f'LOCAL_DISPATCH_{bid_type}_{region_id}')
                    # model.addConstr(target, sense=gurobipy.GRB.EQUAL, rhs=region.fcas_local_dispatch_record[bid_type], name=f'LOCAL_DISPATCH_{bid_type}_{region_id}')
        generic_slack_variables = set()
        if constr_flag:
            # constraints = constrain.get_constraints(process, current, units, connection_points, interconnectors, regions, start, fcas_flag)
            constraints = xml_parser.add_xml_constr(current, start, process, units, regions, interconnectors)
            for constr in constraints.values():
                # if helpers.condition3(process, constr.dispatch, constr.predispatch, constr.rhs) and constr.connection_point_flag:
                if constr.bind_flag or True:
                    if constr.violation_price is None:
                        constr.violation_price = constr.generic_constraint_weight * voll
                    if constr.constraint_type == '<=':
                        constr.surplus = model.addVar(name=f'Surplus_{constr.gen_con_id}')
                        generic_slack_variables.add(f'Surplus_{constr.gen_con_id}')
                        penalty += constr.surplus * constr.violation_price
                        constr.constr = model.addConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs - constr.surplus <= constr.rhs, name=constr.gen_con_id)
                        if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record > constr.rhs and abs(constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record - constr.rhs) > 1:
                            logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} is violated')
                            logging.debug(f'lhs = {constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record} > rhs = {constr.rhs}')
                    elif constr.constraint_type == '=':
                        constr.deficit = model.addVar(name=f'Deficit_{constr.gen_con_id}')
                        generic_slack_variables.add(f'Deficit_{constr.gen_con_id}')
                        constr.surplus = model.addVar(name=f'Surplus_{constr.gen_con_id}')
                        generic_slack_variables.add(f'Surplus_{constr.gen_con_id}')
                        penalty += (constr.deficit + constr.surplus) * constr.violation_price
                        constr.constr = model.addConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs - constr.surplus + constr.deficit, sense=gurobipy.GRB.EQUAL, rhs=constr.rhs, name=constr.gen_con_id)
                        if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record != constr.rhs and abs(constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record - constr.rhs) > 1:
                            logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} is violated')
                            logging.debug(f'lhs = {constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record} != rhs = {constr.rhs}')
                    elif constr.constraint_type == '>=':
                        constr.deficit = model.addVar(name=f'Deficit_{constr.gen_con_id}')
                        generic_slack_variables.add(f'Deficit_{constr.gen_con_id}')
                        penalty += constr.deficit * constr.violation_price
                        constr.constr = model.addConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs + constr.deficit >= constr.rhs, name=constr.gen_con_id)
                        if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record < constr.rhs and abs(constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record - constr.rhs) > 1:
                            logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} is violated')
                            logging.debug(f'lhs = {constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record} < rhs = {constr.rhs}')
                    else:
                        logging.error(f'Constraint {constr.gen_con_id} has invalid constraint type')
                    # Verify LHS value
                    lhs = constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record
                    if constr.lhs is not None and abs(lhs - constr.lhs) > 0.01:
                        logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} LHS record {constr.lhs} but {lhs}')
                        if len(constr.connection_points) > 1 or len(constr.interconnectors) > 1 or len(constr.regions) > 1:
                            logging.debug(constr.connection_points)
                            logging.debug(constr.interconnectors)
                            logging.debug(constr.regions)

                    # # Force lhs to equal lhs record
                    # model.addConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs, sense=gurobipy.GRB.EQUAL, rhs=constr.lhs, name=constr.gen_con_id)
        # Verify region record
        debug.verify_region_record(regions)
        # Calculate marginal prices
        prices = {'NSW1': None, 'VIC1': None, 'SA1': None, 'TAS1': None, 'QLD1': None}
        if dual_flag or fixed_target_flag:
            for region_id, region in regions.items():
                penalty = add_regional_energy_demand_supply_balance_constr(model, region, region_id, hard_flag, slack_variables, penalty, voll, cvp)
            # Set objective
            if hard_flag:
                model.addConstr(penalty, sense=gurobipy.GRB.EQUAL, rhs=0, name='PENALTY_CONSTR')
            model.setObjective(cost + penalty, gurobipy.GRB.MINIMIZE)
            # Optimize model
            model.optimize()
            # Write model for debugging
            # model.write(f'{process}.lp')

            if model.status == gurobipy.GRB.Status.INFEASIBLE or model.status == gurobipy.GRB.Status.INF_OR_UNBD:
                debug.debug_infeasible_model(model)
                return None
            elif model.status == gurobipy.GRB.Status.OPTIMAL:
                # debug.verify_binding_constr(model, constraints)

                # Get dual total_cleared of regional energy balance constraint
                for region in regions.values():
                    prices[region.region_id] = region.rrp_constr.pi
                    region.rrp = region.rrp_constr.pi

                # Generate result csv
                result.generate_dispatchload(units, current, start, process)
                result.generate_result_csv(process, start, current, model.objVal, solution, penalty.getValue(),
                                           interconnectors, regions, units, fcas_flag)
                # result.add_prices(process, start, current, prices)

                # # Check slack variables for soft constraints
                # if not hard_flag:
                #     for region_id, region in regions.items():
                #         logging.debug('{} Deficit: {}'.format(region_id, region.deficit_gen.x))
                #         logging.debug('{} Surplus: {}'.format(region_id, region.surplus_gen.x))
                #     logging.debug('Slack variables:')
                #     for name in slack_variables:
                #         var = model.getVarByName(name)
                #         if var.x != 0:
                #             logging.debug('{}'.format(var))
                #     logging.debug('Slack variables for generic constraints:')
                #     for name in generic_slack_variables:
                #         var = model.getVarByName(name)
                #         if var.x != 0:
                #             logging.debug('{}'.format(var))

        else:
            for region_name in [None, 'NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']:
                for region_id, region in regions.items():
                    if region_name is None:
                        penalty = add_regional_energy_demand_supply_balance_constr(model, region, region_id, hard_flag, slack_variables, penalty, voll, cvp)
                    else:
                        model.remove(region.rrp_constr)
                        increase = 1 if region_id == region_name else 0
                        region.rrp_constr = model.addConstr(
                            region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen == region.total_demand + increase + region.dispatchable_load + region.losses,
                            name=f'REGION_BALANCE_{region_id}')
                # Set objective
                if hard_flag:
                    model.addConstr(penalty, sense=gurobipy.GRB.EQUAL, rhs=0, name='PENALTY_CONSTR')
                model.setObjective(cost + penalty, gurobipy.GRB.MINIMIZE)
                model.optimize()
                if model.status == gurobipy.GRB.Status.INFEASIBLE or model.status == gurobipy.GRB.Status.INF_OR_UNBD:
                    debug.debug_infeasible_model(model)
                    return None
                elif region_name is None:
                    # debug.verify_binding_constr(model, constraints)
                    base = cost.getValue()
                    # Generate result csv
                    result.generate_dispatchload(units, current, start, process)
                    result.generate_result_csv(process, start, current, model.objVal, solution, penalty.getValue(),
                                               interconnectors, regions, units, fcas_flag)
                else:
                    prices[region_name] = cost.getValue() - base
            result.add_prices(process, start, current, prices)
        if process == 'dispatch':
            result.generate_dispatchis(start, current, regions, prices)
        elif process == 'predispatch':
            result.generate_predispatchis(start, current, interval, regions, prices)
        else:
            result.generate_p5min(start, current, regions, prices)
        return prices

    # except gurobipy.GurobiError as e:
    #     print('Error code ' + str(e.errno) + ": " + str(e))
    except AttributeError as e:
        print('Encountered an attribute error: ' + str(e))


if __name__ == '__main__':
    cvp = helpers.read_cvp()
    start_time = datetime.datetime(2020, 9, 1, 4, 5, 0)
    end_time = datetime.datetime(2020, 9, 2, 4, 0, 0)
    # process_type = 'dispatch'
    # process_type = 'p5min'
    process_type = 'predispatch'
    path_to_log = preprocess.LOG_DIR / f'{process_type}_{preprocess.get_case_datetime(start_time)}.log'
    logging.basicConfig(filename=path_to_log, filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)
    total_intervals = helpers.get_total_intervals(process_type, start_time)
    # for interval in range(int((end_time-start_time) / preprocess.FIVE_MIN + 1)):
    for interval in range(12):
        prices = dispatch(cvp, start_time, interval, process_type)
