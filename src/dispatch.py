import constrain
import datetime
import debug
import default
import gurobipy as gp
import helpers
import interconnect
import logging
import offer
import parse
import result


def add_regional_energy_demand_supply_balance_constr(model, region, region_id, debug_flag, penalty, voll, cvp):
    # Regional energy demand supply balance constraint
    region.deficit_gen = model.addVar(name=f'Deficit_Gen_{region_id}')  # Item20
    penalty += region.deficit_gen * cvp['Region_Load_Shedding'] * voll
    region.surplus_gen = model.addVar(name=f'Surplus_Gen_{region_id}')  # Item21
    penalty += region.surplus_gen * cvp['Excess_Generation'] * voll
    region.rrp_constr = model.addLConstr(
        region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen,
        sense=gp.GRB.EQUAL, rhs=region.total_demand + region.dispatchable_load + region.losses,
        name=f'REGION_BALANCE_{region_id}')
    if debug_flag:
        if abs(region.dispatchable_generation_record + region.net_mw_flow_record - region.total_demand - region.dispatchable_load_record - region.losses_record) > 0.01:
            logging.warning(f'Region {region_id} imbalance lhs = {region.dispatchable_generation_record + region.net_mw_flow_record} rhs = {region.total_demand + region.dispatchable_load_record + region.losses_record}')
    return penalty


def prepare(current):
    cvp = helpers.read_cvp()
    voll, market_price_floor = constrain.get_market_price(current)
    return cvp, voll, market_price_floor


def dispatch(start, interval, process, cvp=helpers.read_cvp(), voll=None, market_price_floor=None, iteration=0,
             custom_unit=None, path_to_out=default.OUT_DIR, dispatchload_flag=True, hard_flag=False, fcas_flag=True,
             constr_flag=True, losses_flag=True, link_flag=True, dual_flag=True, fixed_interflow_flag=False,
             fixed_total_cleared_flag=False, fixed_fcas_value_flag=False, fixed_local_fcas_flag=False,
             ic_record_flag=False, debug_flag=False):
    """

    Args:
        start (datetime.datetime): Start datetime
        interval (int): Interval number
        process (str): 'dispatch', 'p5min', or 'predispatch'
        cvp (dict): A pre-define dictionary of Constraint Violation Penalty
        iteration (int): Price-taker iteration number
        custom_unit (offer.Unit): Custom unit
        path_to_out (Path): Out file path
        dispatchload_flag (bool): True if use our DISPATCHLOAD; False if use AEMO'S DISPATCHLOAD record
        debug_flag (bool): Whether apply hard constraints or not
        fcas_flag (bool): Whether calculate FCAS or not
        constr_flag (bool): Whether apply generic constraints or not
        losses_flag (bool): Whether calculate interconnectors losses or not
        link_flag (bool): Whether calculate links or not
        dual_flag (bool): Calculate dual var as price or increase regional demand by 1
        fixed_interflow_flag (bool): Whether fix interflow or not
        fixed_total_cleared_flag (bool): Whether fix generator target or not
        fixed_fcas_value_flag (bool): Wheter fix FCAS target for each unit or not
        fixed_local_fcas_flag (bool): Whether fix regional fcas target or not
        ic_record_flag (bool): Whether apply interconnector import/export limit record or not
        debug_flag (bool): Whether to write debugging information into log file

    Returns:
        A dictionary of regions and prices
    """
    try:
        total_obj = 0
        intervals = 30 if process == 'predispatch' else 5  # Length of the dispatch interval in minutes
        current = start + interval * datetime.timedelta(minutes=intervals)  # Current interval datetime
        if process == 'predispatch':
            predispatch_current = current
            current -= default.TWENTYFIVE_MIN
        else:
            predispatch_current = None
        logging.info('----------------------------------------------------------------------------------')
        logging.info(f'Current interval is {current} (No. {interval} starting at {start}) for {process}')
        with gp.Env() as env, gp.Model(env=env, name=f'{process}{default.get_case_datetime(current)}{interval}{iteration}') as model:
            model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
            # Initiate cost and penalty of objective function
            cost, penalty = 0, 0
            # Get market price cap (MPC) and floor
            if voll is None or market_price_floor is None:
                voll, market_price_floor = constrain.get_market_price(current)
            # Get regions, interconnectors, and case solution
            regions, interconnectors, solution, links = interconnect.get_regions_and_interconnectors(current, start, interval, process, fcas_flag, link_flag)
            # Get units and connection points
            units, connection_points = offer.get_units(current, start, interval, process, fcas_flag=fcas_flag, dispatchload_flag=dispatchload_flag, predispatch_t=predispatch_current, k=iteration, path_to_out=path_to_out)
            # Add cutom unit
            if custom_unit is not None:
                units[custom_unit.duid] = custom_unit
            # Add NEM SPD outputs
            violation_prices = parse.add_nemspdoutputs(current, units, links, link_flag, process)
            for ic_id, ic in interconnectors.items():
                # Define interconnector MW flow
                ic.mw_flow = model.addVar(lb=-gp.GRB.INFINITY, name=f'Mw_Flow_{ic_id}')
                # Add interconnector capacity constraint
                penalty = constrain.add_interconnector_capacity_constr(model, ic, ic_id, debug_flag, penalty, voll, cvp)
                # Add interconnector export/import limit constraint
                if ic_record_flag:
                    constrain.add_interconnector_limit_constr(model, ic, ic_id)
                # Allocate inter-flow to regions
                if not link_flag or (link_flag and ic_id != 'T-V-MNSP1'):
                    regions[ic.region_to].net_mw_flow_record += ic.mw_flow_record
                    regions[ic.region_from].net_mw_flow_record -= ic.mw_flow_record
                    regions[ic.region_to].net_mw_flow += ic.mw_flow
                    regions[ic.region_from].net_mw_flow -= ic.mw_flow
                    regions[ic.region_to].net_interchange_record_temp -= ic.mw_flow_record
                    regions[ic.region_from].net_interchange_record_temp += ic.mw_flow_record
                # Fix inter-flow (custom flag for debugging)
                if fixed_interflow_flag:
                    model.addLConstr(ic.mw_flow, sense=gp.GRB.EQUAL, rhs=ic.mw_flow_record, name=f'FIXED_INTERFLOW_{ic_id}')
                    # model.addLConstr(ic.mw_losses, sense=gp.GRB.EQUAL, rhs=ic.mw_losses_record, name=f'FIXED_INTERLOSSES_{ic_id}')
            if link_flag:
                for link_id, link in links.items():
                    # Avail at each price band
                    link.offers = [model.addVar(ub=avail, name=f'Target{no}_{link_id}') for no, avail in enumerate(link.band_avail)]
                    # Link flow
                    link.mw_flow = model.addVar(name=f'Link_Flow_{link_id}')
                    # Add MNSPInterconnector ramp rate constraint
                    penalty = constrain.add_mnsp_ramp_constr(model, intervals, link, link_id, debug_flag, penalty, voll, cvp)
                    # Add total band MW offer constraint - MNSP only
                    penalty = constrain.add_mnsp_total_band_constr(model, link, link_id, debug_flag, penalty, voll, cvp)
                    # MNSP Max Capacity
                    if link.max_capacity is not None:
                        if link.mw_flow_record is not None and link.mw_flow_record > link.max_capacity:
                            logging.warning(f'Link {link_id} mw flow record {link.mw_flow_record} above max capacity {link.max_capacity}')
                    # Add MNSP availability constraint
                    penalty = constrain.add_mnsp_avail_constr(model, link, link_id, debug_flag, penalty, voll, cvp)

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

                model.addLConstr(interconnectors['T-V-MNSP1'].mw_flow, sense=gp.GRB.EQUAL, rhs=links['BLNKTAS'].mw_flow - links['BLNKVIC'].mw_flow, name='BASSLINK_CONSTR')
                if fixed_total_cleared_flag or fixed_interflow_flag or dual_flag:
                    # TODO: New method to avoid use SOS2 for Basslink
                    # Run twice and choose the lower objective value.
                    if links['BLNKTAS'].mw_flow_record == 0:
                        model.addLConstr(links['BLNKTAS'].mw_flow, sense=gp.GRB.EQUAL, rhs=0, name='BASSLINK_BLNKTAS')
                    else:
                        model.addLConstr(links['BLNKVIC'].mw_flow, sense=gp.GRB.EQUAL, rhs=0, name='BASSLINK_BLNKVIC')
                else:
                    model.addSOS(gp.GRB.SOS_TYPE1, [links['BLNKTAS'].mw_flow, links['BLNKVIC'].mw_flow])
            # Calculate inter-region losses
            if losses_flag:
                if fixed_total_cleared_flag or dual_flag or fixed_interflow_flag:
                    interconnect.calculate_interconnector_losses(model, regions, interconnectors)
                else:
                    interconnect.sos_calculate_interconnector_losses(model, regions, interconnectors)
            # Add XML FCAS information
            if process == 'dispatch':
                parse.add_nemspdoutputs_fcas(current, units, parse.add_fcas)
                # parse.add_nemspdoutputs_fcas(current, units, parse.verify_fcas)
            for unit in units.values():
                # Unit participates in the energy market
                # Normally-on loads have already been included as a component of the metered demand calculation
                if unit.energy is not None and unit.normally_on_flag != 'Y':
                    # Dispatch target at each price band
                    for no, avail in enumerate(unit.energy.band_avail):
                        bid_offer = model.addVar(name=f'Energy_Avail{no}_{unit.duid}')
                        unit.offers.append(bid_offer)
                        model.addLConstr(bid_offer <= avail, name=f'ENERGY_AVAIL{no}_{unit.duid}')
                    # Total dispatch total_cleared
                    unit.total_cleared = model.addVar(name=f'Total_Cleared_{unit.duid}')
                    # TODO: Unit max cap (not included yet)
                    if unit.max_capacity is not None:
                        # model.addLConstr(unit.total_cleared <= unit.max_capacity, name='MAX_CAPACITY_{}'.format(unit.duid))
                        if unit.total_cleared_record is not None and unit.total_cleared_record > unit.max_capacity:
                            logging.warning(f'{unit.dispatch_type} {unit.duid} total cleared record {unit.total_cleared_record} above max capacity {unit.max_capacity}')
                    # Add Unit MaxAvail constraint
                    if unit.energy.max_avail is not None:
                        penalty = constrain.add_max_avail_constr(model, unit, debug_flag, penalty, voll, cvp)
                    # Daily Energy Constraint (only for 30min Pre-dispatch)
                    if process == 'predispatch' and unit.energy.daily_energy_limit != 0:
                        penalty = constrain.add_daily_energy_constr(model, unit, debug_flag, penalty, voll, cvp)
                    # Add total band MW offer constraint
                    penalty = constrain.add_total_band_constr(model, unit, debug_flag, penalty, voll, cvp)
                    # Add Unconstrained Intermittent Generation Forecasts (UIGF) constraint
                    if process != 'predispatch':
                        penalty = constrain.add_uigf_constr(model, unit, debug_flag, penalty, voll, cvp)
                    elif process == 'predispatch' and unit.total_cleared_record is not None and unit.forecast_poe50 is not None:
                        model.addLConstr(unit.total_cleared <= unit.total_cleared_record)
                        # print(f'{unit.duid} record {unit.total_cleared_record} forecast {unit.forecast_poe50} capacity {unit.max_capacity} avail {unit.energy.max_avail} sum {sum(unit.energy.band_avail)}')
                    # Add on-line dispatch fast start inflexibility profile constraint
                    if process == 'dispatch':
                        penalty = constrain.add_fast_start_inflexibility_profile_constr(model, unit, debug_flag, penalty, voll, cvp)
                    # Add unit ramp rate constraint
                    # If the total MW value of its bid/offer bands is zero or the unit is a fast start unit and it is
                    # targeted to be in mode 0, 1, or 2, its ramp rate constraints will be ignored.
                    if sum(unit.energy.band_avail) > 0 and (process != 'dispatch' or unit.start_type != 'FAST' or unit.dispatch_mode > 2):
                        penalty = constrain.add_unit_ramp_constr(process, model, intervals, unit, debug_flag, penalty, voll, cvp)
                    # Add fixed loading constraint
                    penalty = constrain.add_fixed_loading_constr(model, unit, debug_flag, penalty, voll, cvp)
                    # Marginal loss factor
                    if unit.transmission_loss_factor is None:
                        logging.error(f'{unit.dispatch_type} {unit.duid} has no MLF.')
                        unit.transmission_loss_factor = 1.0
                    # Calculate cost
                    cost = constrain.add_cost(unit, regions, cost, process)
                    # TODO: Add Tie-Break constraint
                    # constrain.add_tie_break_constr(model, unit, energy_bands[unit.dispatch_type][unit.region_id], penalty, voll, cvp)
                    # Fix unit dispatch target (custom flag for debugging)
                    if fixed_total_cleared_flag:
                        model.addLConstr(unit.total_cleared == unit.total_cleared_record, name=f'ENERGY_FIXED_{unit.duid}')
                # Unit is registered for FCAS only
                else:
                    unit.total_cleared = 0.0
                # Unit participates in FCAS markets
                if unit.fcas_bids != {} and fcas_flag:
                    # Bid for energy and FCAS
                    if unit.energy is not None:
                        # Preprocess
                        constrain.preprocess_fcas(unit, process, interval, intervals, debug_flag)
                        # Co-optimise energy and FCAS
                        for bid_type, fcas in unit.fcas_bids.items():
                            regions[unit.region_id].fcas_local_dispatch_record_temp[bid_type] += 0 if not unit.target_record else unit.target_record[bid_type]  # Add FCAS record to region
                            if fcas.enablement_status == 1:
                                cost, penalty = constrain.process_fcas_bid(model, unit, fcas, bid_type, debug_flag, penalty, voll, cvp, cost, regions)

                                if bid_type == 'RAISEREG' or bid_type == 'LOWERREG':
                                    # Add joint ramping constraint
                                    if helpers.condition2(process, interval):
                                        penalty = constrain.add_joint_ramping_constr(model, intervals, unit, fcas, bid_type, debug_flag, penalty, voll, cvp)
                                    # TODO: Add energy and regulating FCAS capacity constraint
                                    constrain.add_energy_and_fcas_capacity_constr(model, unit, fcas, bid_type, debug_flag, penalty, voll, cvp)
                                else:
                                    penalty = constrain.add_joint_capacity_constr_test(model, unit, fcas, bid_type, debug_flag, penalty, voll, cvp)
                                    # Add FCAS EnablementMin constr
                                    penalty = constrain.add_enablement_min_constr(model, unit, fcas, bid_type, debug_flag, penalty, voll, cvp)
                                    # Add FCAS EnablementMax constr
                                    penalty = constrain.add_enablement_max_constr(model, unit, fcas, bid_type, debug_flag, penalty, voll, cvp)
                            else:
                                if debug_flag and unit.target_record and unit.target_record[bid_type] != 0:
                                    logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} is not enable but record {unit.target_record[bid_type]}')
                    # Only bid for FCAS
                    else:
                        for bid_type, fcas in unit.fcas_bids.items():
                            cost, penalty = constrain.process_fcas_bid(model, unit, fcas, bid_type, debug_flag, penalty, voll, cvp, cost, regions)
                            regions[unit.region_id].fcas_local_dispatch_record_temp[bid_type] += 0 if not unit.target_record else unit.target_record[bid_type]  # Add FCAS record to region
                    # Fix unit FCAS target (custom flag for debugging)
                    if fixed_fcas_value_flag and fcas_flag and unit.fcas_bids != {}:
                        for bid_type, fcas in unit.fcas_bids.items():
                            model.addLConstr(fcas.value == unit.target_record[bid_type], name=f'{bid_type}_FIXED_{unit.duid}')
            # Print the collected energy bands (for debugging)
            # if debug_flag:
            #   debug.print_energy_bands(energy_bands)

            # Region FCAS local dispatch
            if fcas_flag:
                for region_id, region in regions.items():
                    for bid_type, target in region.fcas_local_dispatch_temp.items():
                        region.fcas_local_dispatch[bid_type] = model.addVar(name=f'Local_Dispatch_{bid_type}_{region_id}')
                        # Used to calculate FCAS RRP
                        region.local_fcas_constr[bid_type] = model.addLConstr(region.fcas_local_dispatch[bid_type], sense=gp.GRB.EQUAL, rhs=target, name=f'LOCAL_DISPATCH_SUM_{bid_type}_{region_id}')
                        # model.addLConstr(region.fcas_local_dispatch[bid_type], sense=gp.GRB.EQUAL, rhs=target, name=f'LOCAL_DISPATCH_SUM_{bid_type}_{region_id}')
                        # Fix local FCAS dispatch for each region (custom flag for debugging)
                        if fixed_local_fcas_flag:
                            model.addLConstr(region.fcas_local_dispatch[bid_type] <= region.fcas_local_dispatch_record[bid_type], name=f'LOCAL_DISPATCH_{bid_type}_FIXED_{region_id}')
            # Generic constraints
            generic_slack_variables = set()
            if constr_flag:
                # constraints = constrain.get_constraints(process, current, units, connection_points, interconnectors, regions, start, fcas_flag)
                constraints = parse.add_xml_constr(current, start, predispatch_current, process, units, regions, interconnectors)
                for constr in constraints.values():
                    # TODO: Figure out what's going on the above and below commented code
                    # if helpers.condition3(process, constr.dispatch, constr.predispatch, constr.rhs) and constr.connection_point_flag:
                    if constr.bind_flag or process == 'dispatch':
                        if constr.violation_price is None:
                            constr.violation_price = constr.generic_constraint_weight * voll
                        if constr.constraint_type == '<=':
                            constr.surplus = model.addVar(name=f'Surplus_{constr.gen_con_id}')
                            generic_slack_variables.add(f'Surplus_{constr.gen_con_id}')
                            penalty += constr.surplus * constr.violation_price
                            constr.constr = model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs - constr.surplus <= constr.rhs, name=constr.gen_con_id)
                            if debug_flag:
                                if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record > constr.rhs and abs(constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record - constr.rhs) > 1:
                                    logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} is violated')
                                    logging.debug(f'lhs = {constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record} > rhs = {constr.rhs}')
                        elif constr.constraint_type == '=':
                            constr.deficit = model.addVar(name=f'Deficit_{constr.gen_con_id}')
                            generic_slack_variables.add(f'Deficit_{constr.gen_con_id}')
                            constr.surplus = model.addVar(name=f'Surplus_{constr.gen_con_id}')
                            generic_slack_variables.add(f'Surplus_{constr.gen_con_id}')
                            penalty += (constr.deficit + constr.surplus) * constr.violation_price
                            constr.constr = model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs - constr.surplus + constr.deficit, sense=gp.GRB.EQUAL, rhs=constr.rhs, name=constr.gen_con_id)
                            if debug_flag:
                                if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record != constr.rhs and abs(constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record - constr.rhs) > 1:
                                    logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} is violated')
                                    logging.debug(f'lhs = {constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record} != rhs = {constr.rhs}')
                        elif constr.constraint_type == '>=':
                            constr.deficit = model.addVar(name=f'Deficit_{constr.gen_con_id}')
                            generic_slack_variables.add(f'Deficit_{constr.gen_con_id}')
                            penalty += constr.deficit * constr.violation_price
                            constr.constr = model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs + constr.deficit >= constr.rhs, name=constr.gen_con_id)
                            if debug_flag:
                                if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record < constr.rhs and abs(constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record - constr.rhs) > 1:
                                    logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} is violated')
                                    logging.debug(f'lhs = {constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record} < rhs = {constr.rhs}')
                        elif debug_flag:
                            logging.error(f'Constraint {constr.gen_con_id} has invalid constraint type')
                        # Verify LHS value
                        lhs = constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record
                        if debug_flag and constr.lhs is not None and abs(lhs - constr.lhs) > 1:
                            logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} LHS record {constr.lhs} but {lhs}')
                            if len(constr.connection_points) > 1 or len(constr.interconnectors) > 1 or len(constr.regions) > 1:
                                logging.debug(constr.connection_points)
                                logging.debug(constr.interconnectors)
                                logging.debug(constr.regions)
                        # # Force lhs to equal lhs record
                        # model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs, sense=gp.GRB.EQUAL, rhs=constr.lhs, name=constr.gen_con_id)
            # Verify region record
            if debug_flag:
                debug.verify_region_record(regions)
            # Calculate marginal read_prices
            prices = {'NSW1': None, 'VIC1': None, 'SA1': None, 'TAS1': None, 'QLD1': None}
            # Calculate dual variable as marginal price
            if dual_flag or fixed_total_cleared_flag:
                for region_id, region in regions.items():
                    penalty = add_regional_energy_demand_supply_balance_constr(model, region, region_id, debug_flag, penalty, voll, cvp)
                # Set objective
                if hard_flag:
                    model.addLConstr(penalty, sense=gp.GRB.EQUAL, rhs=0, name='PENALTY_CONSTR')
                model.setObjective(cost + penalty, gp.GRB.MINIMIZE)
                # Optimize model
                model.optimize()
                # Write model for debugging
                # path_to_model = default.MODEL_DIR / f'{process}_{preprocess.get_case_datetime(start)}_{interval}.lp'
                # model.write(str(path_to_model))

                if model.status == gp.GRB.Status.INFEASIBLE or model.status == gp.GRB.Status.INF_OR_UNBD:
                    debug.debug_infeasible_model(model)
                    return None
                elif model.status == gp.GRB.Status.OPTIMAL:
                    # Model Debugging
                    if debug_flag:
                        # Verify if AEMO binding constraints are also binding in our model and vice versa
                        # debug.verify_binding_constr(model, constraints)
                        # Compare with total cleared record
                        # debug.compare_total_cleared_and_fcas(units)
                        # Check binding generic FCAS constraints to find the way to calculate FCAS RRP
                        # debug.check_binding_generic_fcas_constraints(regions, constraints)
                        # Check all the violated constraints
                        # if penalty.getValue() > 0:
                        #     print(f'Total violation is {penalty.getValue()}')
                        #     debug.check_violation(model, regions, slack_variables, generic_slack_variables)

                        # TODO: Debug for objective value
                        total_energy, total_fcas, total_link = 0, 0, 0
                        # for index in range(cost.size()):
                        #     coeff = cost.getCoeff(index)
                        #     var = cost.getVar(index)
                        #     if var.x != 0:
                        #         if 'Energy' in var.varName:
                        #             total_energy += var.x * coeff
                        #         elif 'BLNK' in var.varName:
                        #             total_link += var.x * coeff
                        #         else:
                        #             total_fcas += var.x * coeff
                        # print(f'energy {total_energy}')
                        # print(f'fcas {total_fcas}')
                        # print(f'link {total_link}')
                        # print(f'total {total_energy + total_fcas + total_link}')

                        # total_gen, total_load, total_fcas = 0, 0, 0
                        # for region_id, region in regions.items():
                        #     total_gen += region.dispatchable_generation_record * region.rrp_record
                        #     total_load += region.dispatchable_load_record * region.rrp_record
                        #     for bid_type, fcas_dispatch in region.fcas_local_dispatch_record.items():
                        #         total_fcas += fcas_dispatch * region.fcas_rrp_record[bid_type]
                        # print(f'gen {total_gen}')
                        # print(f'load {total_load}')
                        # print(f'fcas {total_fcas}')

                    # Get dual total_cleared of regional energy balance constraint
                    for region in regions.values():
                        prices[region.region_id] = region.rrp_constr.pi
                        region.rrp = region.rrp_constr.pi
                        for fcas_type, fcas_constr in region.local_fcas_constr.items():
                            region.fcas_rrp[fcas_type] = - fcas_constr.pi
                    # Generate result csv
                    result.write_dispatchload(units, predispatch_current if process == 'predispatch' else current, start, process, k=iteration, path_to_out=path_to_out)
                    result.write_result_csv(process, start, predispatch_current if process == 'predispatch' else current, model.objVal, solution, penalty.getValue(),
                                            interconnectors, regions, units, fcas_flag, k=iteration, path_to_out=path_to_out)
            # Calculate difference of objectives by increasing demand by 1 as marginal price
            else:
                for region_name in [None, 'NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']:
                    for region_id, region in regions.items():
                        if region_name is None:
                            penalty = add_regional_energy_demand_supply_balance_constr(model, region, region_id, debug_flag, penalty, voll, cvp)
                        else:
                            model.remove(region.rrp_constr)
                            increase = 1 if region_id == region_name else 0
                            region.rrp_constr = model.addLConstr(
                                region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen == region.total_demand + increase + region.dispatchable_load + region.losses,
                                name=f'REGION_BALANCE_{region_id}')
                    # Set objective
                    if debug_flag:
                        model.addLConstr(penalty, sense=gp.GRB.EQUAL, rhs=0, name='PENALTY_CONSTR')
                    model.setObjective(cost + penalty, gp.GRB.MINIMIZE)
                    model.optimize()
                    if model.status == gp.GRB.Status.INFEASIBLE or model.status == gp.GRB.Status.INF_OR_UNBD:
                        debug.debug_infeasible_model(model)
                        return None
                    elif region_name is None:
                        # debug.verify_binding_constr(model, constraints)
                        base = cost.getValue()
                        # Generate result csv
                        result.write_dispatchload(units, predispatch_current if process == 'predispatch' else current, start, process, k=iteration, path_to_out=path_to_out)
                        result.write_result_csv(process, start, predispatch_current if process == 'predispatch' else current, model.objVal, solution, penalty.getValue(),
                                                interconnectors, regions, units, fcas_flag, k=iteration, path_to_out=path_to_out)
                    else:
                        prices[region_name] = cost.getValue() - base
                result.add_prices(process, start, current, prices)
            if process == 'dispatch':
                result.write_dispatchis(start, current, regions, prices, k=iteration, path_to_out=path_to_out)
            elif process == 'predispatch':
                result.write_predispatchis(start, predispatch_current, interval, regions, prices, k=iteration, path_to_out=path_to_out)
            else:
                result.write_p5min(start, current, interval, regions, prices, k=iteration, path_to_out=path_to_out)
            if custom_unit is not None and iteration == 0:
                # print(custom_unit.total_cleared)
                result.record_cutom_unit(current, custom_unit, prices)
            return prices
    except gp.GurobiError as e:
        print(e)
        print(f'start datetime {start} no {interval} current datetime {current}')
    # except AttributeError as e:
    #     print(e)
    #     print(f'start datetime {start} no {interval} current datetime {current}')


def get_all_dispatch(start, process, custom_unit=None, cvp=None, voll=None, market_price_floor=None):
    if cvp is None:
        cvp, voll, market_price_floor = prepare(start)
    total = helpers.get_total_intervals(process, start)
    for i in range(total):
        prices = dispatch(start=start, interval=i, process=process, cvp=cvp, voll=voll,
                          market_price_floor=market_price_floor, custom_unit=custom_unit)
    return prices


if __name__ == '__main__':
    process_type = 'dispatch'
    # process_type = 'p5min'
    # process_type = 'predispatch'
    start_time = datetime.datetime(2020, 9, 1, 4, 5, 0)
    # start_time = datetime.datetime(2020, 9, 1, 4, 30 if process_type == 'predispatch' else 5, 0)
    end_time = datetime.datetime(2020, 9, 2, 4, 0, 0)

    path_to_log = default.LOG_DIR / f'{process_type}_{default.get_case_datetime(start_time)}.log'
    logging.basicConfig(filename=path_to_log, filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)
    total_intervals = helpers.get_total_intervals(process_type, start_time)
    cvp, voll, market_price_floor = prepare(start_time)
    # for interval in range(32, total_intervals, 1):
    # for interval in range(int((end_time-start_time) / default.FIVE_MIN + 1)):
    prices = dispatch(start=start_time, interval=0, process=process_type, cvp=cvp, voll=voll,
                      market_price_floor=market_price_floor, dispatchload_flag=False, debug_flag=True)
    # get_all_dispatch(start_time, process_type)

