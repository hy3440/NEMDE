# NEMDE simulation model
import gurobipy
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
from preprocess import get_market_price


class Problem:
    def __init__(self, current, process, batteries, debug_flag):
        self.current = current
        self.process = process
        self.problem_id = f'{process}_{default.get_case_datetime(current)}'
        self.units = {}
        self.connection_points = None
        self.regions = interconnect.init_regions(debug_flag)
        self.interconnectors = interconnect.init_interconnectors()
        self.links = interconnect.init_links()
        self.constraints = {}
        self.solution = None
        self.cost = 0.0
        self.penalty = gurobipy.LinExpr(0.0)
        self.batteries = batteries
        # if e is not None:
        #     self.batteries, self.custom_units = helpers.init_batteries(current, e, p, 'DERNEMDE-0', 'Battery')
        # else:
        #     self.batteries, self.custom_units = helpers.init_batteries(None, None, None, 'DERNEMDE', 'Dalrymple')

    def reset_problem(self, current, process, batteries):
        self.current = current
        self.process = process
        self.problem_id = f'{process}_{default.get_case_datetime(current)}'
        self.batteries = batteries


def add_regional_energy_demand_supply_balance_constr(model, region, region_id, prob_id, debug_flag, penalty, cvp):
    # Regional energy demand supply balance constraint
    region.deficit_gen = model.addVar(name=f'Deficit_Gen_{region_id}_{prob_id}')  # Item20
    penalty += region.deficit_gen * cvp['EnergyDeficitPrice']
    region.surplus_gen = model.addVar(name=f'Surplus_Gen_{region_id}_{prob_id}')  # Item21
    penalty += region.surplus_gen * cvp['EnergySurplusPrice']
    region.rrp_constr = model.addLConstr(
        region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen,
        sense=gp.GRB.EQUAL, rhs=region.total_demand + region.dispatchable_load + region.losses,
        name=f'REGION_BALANCE_{region_id}_{prob_id}')
    # region.rrp_constr = model.addLConstr(
    #     region.dispatchable_generation + region.net_mw_flow,
    #     sense=gp.GRB.EQUAL, rhs=region.total_demand + region.dispatchable_load + region.losses,
    #     name=f'REGION_BALANCE_{region_id}_{prob_id}')
    if debug_flag:
        if abs(region.dispatchable_generation_record + region.net_mw_flow_record - region.total_demand - region.dispatchable_load_record - region.losses_record) > 0.01:
            logging.warning(f'Region {region_id} imbalance lhs = {region.dispatchable_generation_record + region.net_mw_flow_record} rhs = {region.total_demand + region.dispatchable_load_record + region.losses_record}')
    return penalty


def prepare(current):
    cvp = helpers.read_cvp()
    voll, market_price_floor = get_market_price(current)
    return cvp, voll, market_price_floor


def dispatch(current, start, predispatch_current, interval, process, model, iteration=0, custom_unit=None,
             path_to_out=default.OUT_DIR, dispatchload_path=None, dispatchload_flag=True, agc_flag=True,
             hard_flag=False, fcas_flag=True, constr_flag=True, losses_flag=True, link_flag=True, dual_flag=True,
             fixed_interflow_flag=False, fixed_total_cleared_flag=False, fixed_fcas_value_flag=False, utility_flag=False,
             fixed_local_fcas_flag=False, ic_record_flag=False, debug_flag=False, der_flag=False, last_prob_id=None,
             intervals=None, batteries=None, daily_energy_flag=False, dispatchload_record=False, prob=None, biunit=None,
             bilevel_flag=False):
    """ Dispatch part of NEMDE formulation.
    Args:
        current (datetime.datetime): Current datetime
        start (datetime.datetime): Start datetime
        predispatch_current (datetime.datetime): Predispatch datetime
        interval (int): Interval number
        process (str): 'dispatch', 'p5min', or 'predispatch'
        model (gurobipy.Model): Model
        iteration (int): Iteration number
        custom_unit (list): Custom unit
        path_to_out (pathlib.Path): Out file path
        dispatchload_path (pathlib.Path): Path to read dispatchload file
        dispatchload_flag (bool): True if use our DISPATCHLOAD; False if  don't use
        agc_flag (bool): Apply AGC signals or not
        hard_flag (bool): Whether apply hard constraints or not
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
        der_flag (bool): Redesign for DER or not
        last_prob_id (str): Problem ID of last interval
        intervals (int): Pre-defined number of intervals
        batteries (dict): Participant battery
        dispatchload_record (bool): Use AEMO's DISPATCHLOAD record
    Returns:
        (Problem, gurobipy.Model, dict)
    """
    try:
        # Initiate problem
        prob = Problem(predispatch_current if process == 'predispatch' else current, process, batteries, debug_flag)
        # Add cutom unit
        if custom_unit is not None:
            if type(custom_unit) == list:
                for unit in custom_unit:
                    prob.units[unit.duid] = unit
            else:
                prob.units[custom_unit.duid] = custom_unit
        # Add batteries' generator and load
        if batteries is not None and not bilevel_flag:
            for battery in batteries.values():
                for unit in [battery.generator, battery.load]:
                    prob.units[unit.duid] = unit
        # Specify the length of interval
        if intervals is None:
            intervals = 30 if process == 'predispatch' else 5  # Length of the dispatch interval in minutes
        # Get regions, interconnectors, and case solution
        interconnect.get_regions_and_interconnectors(current, start, interval, process, prob, fcas_flag, link_flag, dispatchload_record, debug_flag, intervals=intervals)
        # Add NEM SPD outputs
        cvp, voll, market_price_floor = parse.add_nemspdoutputs(current, prob.units, prob.links, link_flag, process)
        # Get market price cap (MPC) and floor
        if voll is None or market_price_floor is None:
            voll, market_price_floor = get_market_price(current)
        # Get units and connection points
        prob.connection_points = offer.get_units(current, start, interval, process, prob.units, prob.links,
                                                 dispatchload_path=dispatchload_path, fcas_flag=fcas_flag,
                                                 dispatchload_flag=dispatchload_flag, agc_flag=agc_flag,
                                                 predispatch_t=predispatch_current, k=iteration, debug_flag=debug_flag,
                                                 path_to_out=path_to_out, daily_energy_flag=daily_energy_flag,
                                                 dispatchload_record=dispatchload_record)
        for ic_id, ic in prob.interconnectors.items():
            # Define interconnector MW flow
            ic.mw_flow = model.addVar(lb=-gp.GRB.INFINITY, name=f'Mw_Flow_{ic_id}_{prob.problem_id}')
            # Add interconnector capacity constraint
            constrain.add_interconnector_capacity_constr(model, ic, ic_id, prob.problem_id, debug_flag, prob.penalty, cvp)
            # Add interconnector export/import limit constraint
            if ic_record_flag:
                constrain.add_interconnector_limit_constr(model, ic, ic_id)
            # Allocate inter-flow to regions
            if not link_flag or (link_flag and ic_id != 'T-V-MNSP1'):
                prob.regions[ic.region_to].net_mw_flow += ic.mw_flow
                prob.regions[ic.region_from].net_mw_flow -= ic.mw_flow
                if debug_flag:
                    prob.regions[ic.region_to].net_mw_flow_record += ic.mw_flow_record
                    prob.regions[ic.region_from].net_mw_flow_record -= ic.mw_flow_record
                    prob.regions[ic.region_to].net_interchange_record_temp -= ic.mw_flow_record
                    prob.regions[ic.region_from].net_interchange_record_temp += ic.mw_flow_record
            # Fix inter-flow (custom flag for debugging)
            if fixed_interflow_flag:
                model.addLConstr(ic.mw_flow, sense=gp.GRB.EQUAL, rhs=ic.mw_flow_record, name=f'FIXED_INTERFLOW_{ic_id}')
        if link_flag:
            for link_id, link in prob.links.items():
                # if der_flag and last_prob_id is not None:
                if last_prob_id is not None:
                    link.metered_mw_flow = model.getVarByName(f'Link_Flow_{link_id}_{last_prob_id}')
                # Avail at each price band
                link.offers = [model.addVar(ub=avail, name=f'Target{no}_{link_id}_{prob.problem_id}') for no, avail in enumerate(link.band_avail)]
                # Link flow
                link.mw_flow = model.addVar(name=f'Link_Flow_{link_id}_{prob.problem_id}')
                # Add MNSPInterconnector ramp rate constraint
                constrain.add_mnsp_ramp_constr(model, intervals, link, link_id, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Add total band MW offer constraint - MNSP only
                constrain.add_mnsp_total_band_constr(model, link, link_id, prob.problem_id, debug_flag, prob.penalty, cvp)
                # MNSP Max Capacity
                if link.max_capacity is not None and not der_flag and debug_flag:
                    if link.mw_flow_record is not None and link.mw_flow_record > link.max_capacity and debug_flag:
                        logging.warning(f'Link {link_id} mw flow record {link.mw_flow_record} above max capacity {link.max_capacity}')
                # Add MNSP availability constraint
                constrain.add_mnsp_avail_constr(model, link, link_id, prob.problem_id, debug_flag, prob.penalty, cvp)

                link.from_cost = sum([o * (p / link.from_region_tlf) for o, p in zip(link.offers, link.price_band)])
                link.to_cost = sum([o * (p / link.to_region_tlf) for o, p in zip(link.offers, link.price_band)])
                # Add cost to objective
                prob.cost -= link.from_cost  # As load for from_region
                prob.cost += link.to_cost  # As generator for to_region

                prob.regions[link.from_region].net_mw_flow -= link.mw_flow * link.from_region_tlf
                prob.regions[link.to_region].net_mw_flow += link.mw_flow * link.to_region_tlf
                if debug_flag:
                    prob.regions[link.from_region].net_mw_flow_record -= link.mw_flow_record * link.from_region_tlf
                    prob.regions[link.to_region].net_mw_flow_record += link.mw_flow_record * link.to_region_tlf
                    prob.regions[link.from_region].net_interchange_record_temp += link.mw_flow_record * link.to_region_tlf
                    prob.regions[link.to_region].net_interchange_record_temp -= link.mw_flow_record * link.to_region_tlf

            model.addLConstr(prob.interconnectors['T-V-MNSP1'].mw_flow, sense=gp.GRB.EQUAL, rhs=prob.links['BLNKTAS'].mw_flow - prob.links['BLNKVIC'].mw_flow, name=f'BASSLINK_CONSTR_{prob.problem_id}')
            if fixed_total_cleared_flag or fixed_interflow_flag:
                # TODO: New method to avoid use SOS2 for Basslink
                # Run twice and choose the lower objective value.
                if prob.links['BLNKTAS'].mw_flow_record == 0:
                    model.addLConstr(prob.links['BLNKTAS'].mw_flow, sense=gp.GRB.EQUAL, rhs=0, name='BASSLINK_BLNKTAS')
                else:
                    model.addLConstr(prob.links['BLNKVIC'].mw_flow, sense=gp.GRB.EQUAL, rhs=0, name='BASSLINK_BLNKVIC')
            elif not dual_flag:
                model.addSOS(gp.GRB.SOS_TYPE1, [prob.links['BLNKTAS'].mw_flow, prob.links['BLNKVIC'].mw_flow])
        # Calculate inter-region losses
        if losses_flag:
            if fixed_total_cleared_flag or dual_flag or fixed_interflow_flag:
                interconnect.calculate_interconnector_losses(model, prob.regions, prob.interconnectors, prob.problem_id, debug_flag)
            else:
                interconnect.sos_calculate_interconnector_losses(model, prob.regions, prob.interconnectors, prob.problem_id, debug_flag)
        # # Add XML FCAS information
        # if process == 'dispatch':
        #     parse.add_nemspdoutputs_fcas(current, prob.units, parse.add_fcas)
            # parse.add_nemspdoutputs_fcas(current, units, parse.verify_fcas)
        energy_bands = {'GENERATOR': {'NSW1': {}, 'QLD1': {}, 'SA1': {}, 'TAS1': {}, 'VIC1':{}}, 'LOAD': {'NSW1': {}, 'QLD1': {}, 'SA1': {}, 'TAS1': {}, 'VIC1':{}}}
        for unit in prob.units.values():
            # if der_flag and last_prob_id is not None:
            if last_prob_id is not None:
                unit.initial_mw = model.getVarByName(f'Total_Cleared_{unit.duid}_{last_prob_id}')
                if unit.initial_mw is None:
                    unit.initial_mw = 0.0
            # Unit participates in the energy market
            # Normally-on loads have already been included as a component of the metered demand calculation
            if unit.energy is not None and unit.normally_on_flag != 'Y':
                # Dispatch target at each price band
                unit.offers = []
                for no, avail in enumerate(unit.energy.band_avail):
                    bid_offer = model.addVar(name=f'Energy_Avail{no}_{unit.duid}_{prob.problem_id}')
                    unit.offers.append(bid_offer)
                    model.addLConstr(bid_offer <= avail, name=f'ENERGY_AVAIL{no}_{unit.duid}_{prob.problem_id}')
                # Total dispatch total_cleared
                unit.total_cleared = model.addVar(name=f'Total_Cleared_{unit.duid}_{prob.problem_id}')
                # TODO: Unit max cap (not included yet)
                if unit.max_capacity is not None:
                    # model.addLConstr(unit.total_cleared <= unit.max_capacity, name='MAX_CAPACITY_{}'.format(unit.duid))
                    if unit.total_cleared_record is not None and unit.total_cleared_record > unit.max_capacity:
                        logging.warning(f'{unit.dispatch_type} {unit.duid} total cleared record {unit.total_cleared_record} above max capacity {unit.max_capacity}')
                # Add Unit MaxAvail constraint
                if unit.energy.max_avail is not None:
                    constrain.add_max_avail_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Daily Energy Constraint (only for 30min Pre-dispatch)
                if process == 'predispatch' and daily_energy_flag and unit.energy.daily_energy_limit != 0 and unit.energy.daily_energy_limit is not None:
                    constrain.add_daily_energy_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Add total band MW offer constraint
                constrain.add_total_band_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Add Unconstrained Intermittent Generation Forecasts (UIGF) constraint (See AEMO2019Dispatch)
                if unit.forecast_poe50 is not None and unit.total_cleared_record <= unit.forecast_poe50:
                    constrain.add_uigf_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # if process != 'predispatch' and unit.forecast_poe50 is not None and unit.total_cleared_record <= unit.forecast_poe50:
                #     constrain.add_uigf_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # elif process == 'predispatch' and unit.total_cleared_record is not None and unit.forecast_poe50 is not None:
                #     model.addLConstr(unit.total_cleared <= unit.total_cleared_record)
                # Add on-line dispatch fast start inflexibility profile constraint (See AEMO2014Fast)
                if process == 'dispatch':
                    constrain.add_fast_start_inflexibility_profile_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Add unit ramp rate constraint
                # If the total MW value of its bid/offer bands is zero or the unit is a fast start unit and it is
                # targeted to be in mode 0, 1, or 2, its ramp rate constraints will be ignored.
                if sum(unit.energy.band_avail) > 0 and (process != 'dispatch' or unit.start_type != 'FAST' or unit.dispatch_mode > 2):
                    constrain.add_unit_ramp_constr(process, model, intervals, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Add fixed loading constraint
                if unit.energy.fixed_load != 0:
                    constrain.add_fixed_loading_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Marginal loss factor
                if unit.transmission_loss_factor is None:
                    logging.error(f'{unit.dispatch_type} {unit.duid} has no MLF.')
                    unit.transmission_loss_factor = 1.0
                # TODO: Add Tie-Break constraint
                # constrain.add_tie_break_constr(model, unit, energy_bands[unit.dispatch_type][unit.region_id], prob.penalty, cvp)
                # Calculate cost
                prob.cost = constrain.add_cost(unit, prob.regions, prob.cost, debug_flag)
                # Fix unit dispatch target (custom flag for debugging)
                if fixed_total_cleared_flag:
                    model.addLConstr(unit.total_cleared, gurobipy.GRB.EQUAL, unit.total_cleared_record, name=f'ENERGY_FIXED_{unit.duid}')
            # Unit is registered for FCAS only
            else:
                unit.total_cleared = 0.0
            # Unit participates in FCAS markets
            if unit.fcas_bids != {} and fcas_flag:
                # Bid for energy and FCAS
                if unit.energy is not None:
                    # Preprocess
                    constrain.preprocess_fcas(unit, process, interval, intervals, debug_flag, agc_flag)
                    # Co-optimise energy and FCAS
                    for bid_type, fcas in unit.fcas_bids.items():
                        prob.regions[unit.region_id].fcas_local_dispatch_record_temp[bid_type] += 0 if not unit.target_record else unit.target_record[bid_type]  # Add FCAS record to region
                        if fcas.enablement_status == 1:
                            prob.cost = constrain.process_fcas_bid(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp, prob.cost, prob.regions)
                            if bid_type == 'RAISEREG' or bid_type == 'LOWERREG':
                                # Add joint ramping constraint
                                if helpers.condition2(process, interval):
                                    constrain.add_joint_ramping_constr(model, intervals, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp)
                                # TODO: Add energy and regulating FCAS capacity constraint
                                constrain.add_energy_and_fcas_capacity_constr(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp)
                            else:
                                constrain.add_joint_capacity_constr(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp)
                                # # Add FCAS EnablementMin constr
                                # constrain.add_enablement_min_constr(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp)
                                # # Add FCAS EnablementMax constr
                                # constrain.add_enablement_max_constr(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp)
                        else:
                            if debug_flag and unit.target_record and unit.target_record[bid_type] != 0:
                                logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} is not enable but record {unit.target_record[bid_type]}')
                # Only bid for FCAS
                else:
                    for bid_type, fcas in unit.fcas_bids.items():
                        prob.cost = constrain.process_fcas_bid(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp, prob.cost, prob.regions)
                        prob.regions[unit.region_id].fcas_local_dispatch_record_temp[bid_type] += 0 if not unit.target_record else unit.target_record[bid_type]  # Add FCAS record to region
                # Fix unit FCAS target (custom flag for debugging)
                if fixed_fcas_value_flag and fcas_flag and unit.fcas_bids != {}:
                    for bid_type, fcas in unit.fcas_bids.items():
                        model.addLConstr(fcas.value == unit.target_record[bid_type], name=f'{bid_type}_FIXED_{unit.duid}')
        if batteries is not None and bilevel_flag:
            for battery in batteries.values():
                for unit in [battery.generator, battery.load]:
                    unit.total_cleared = model.addVar(lb=-gurobipy.GRB.INFINITY, name=f'Total_Cleared_{unit.duid}_{prob.problem_id}')
                    if unit.dispatch_type == 'LOAD':
                        prob.regions[unit.region_id].dispatchable_load += unit.total_cleared
                    else:
                        prob.regions[unit.region_id].dispatchable_generation += unit.total_cleared
                    prob.units[unit.duid] = unit
        # Battery Operation
        M = 16  # Number of segments
        R = 300000  # Replacement cost ($/MWh)
        if der_flag:
            for bat_id, battery in prob.batteries.items():
                if last_prob_id is not None:
                    battery.initial_E = model.getVarByName(f'E_{bat_id}_{last_prob_id}')
                    # battery.initial_E_record = model.getVarByName(f'E_record_{bat_id}_{last_prob_id}')
                    # if battery.initial_E is None:
                    #     battery.initial_E = battery.size * 0.5
                    #     battery.initial_E_record = battery.size * 0.5
                battery.E = model.addVar(name=f'E_{bat_id}_{prob.problem_id}')
                battery.min_avail_constr = model.addLConstr(battery.E >= battery.Emin, name=f'Emin_AVAIL_{bat_id}_{prob.problem_id}')
                battery.max_avail_constr = model.addLConstr(battery.E <= battery.Emax, name=f'Emax_AVAIL_{bat_id}_{prob.problem_id}')
                battery.transition_constr = model.addLConstr(battery.E, gp.GRB.EQUAL, battery.initial_E + intervals * (battery.load.total_cleared * battery.eff - battery.generator.total_cleared / battery.eff) / 60, f'TRANSITION_{bat_id}_{prob.problem_id}')
                # battery.E_record = model.addVar(name=f'E_record_{bat_id}_{prob.problem_id}')
                # model.addLConstr(battery.E_record == battery.initial_E_record + intervals * (battery.load.total_cleared_record * battery.eff - battery.generator.total_cleared_record / battery.eff) / 60, f'E_RECORD_{bat_id}_{prob.problem_id}')
                # Charge or discharge
                battery.sos_constr = model.addSOS(gp.GRB.SOS_TYPE1, [battery.generator.total_cleared, battery.load.total_cleared])
                # Degradation model
                if utility_flag:
                    pgens = [model.addVar(ub=battery.generator.max_capacity, name=f'pgen_segment_{m + 1}_{prob.problem_id}') for m in range(M)]
                    model.addLConstr(battery.generator.total_cleared == sum(pgens), f'PGEN_SEGMENT_{prob.problem_id}')
                    battery.degradation_cost = (intervals / 60) * sum([pgens[m] * helpers.marginal_costs(R, battery.eff, M, m + 1) for m in range(M)])
                    prob.cost += battery.degradation_cost
        # TODO: Custom Battery fo comparison
        # if custom_unit is not None and type(custom_unit) == list:
        #     model.addSOS(gp.GRB.SOS_TYPE1, [unit.total_cleared for unit in custom_unit])
        if biunit is not None:
            if last_prob_id is not None:
                biunit.initial_E = model.getVarByName(f'E_{biunit.duid}_{last_prob_id}')
            biunit.E = model.addVar(name=f'E_{biunit.duid}_{prob.problem_id}')
            biunit.total_cleared = model.addVar(lb=-biunit.capacity, ub=biunit.capacity, name=f'Total_Cleared_{biunit.duid}_{prob.problem_id}')
            model.addLConstr(biunit.E, gp.GRB.EQUAL, biunit.initial_E + intervals * biunit.total_cleared / 60, f'TRANSITION_{biunit.duid}_{prob.problem_id}')
            prob.regions[biunit.region_id].dispatchable_load += biunit.total_cleared
        # Region FCAS local dispatch
        if fcas_flag:
            for region_id, region in prob.regions.items():
                for bid_type, target in region.fcas_local_dispatch_temp.items():
                    region.fcas_local_dispatch[bid_type] = model.addVar(name=f'Local_Dispatch_{bid_type}_{region_id}_{prob.problem_id}')
                    # Used to calculate FCAS RRP
                    region.local_fcas_constr[bid_type] = model.addLConstr(region.fcas_local_dispatch[bid_type], sense=gp.GRB.EQUAL, rhs=target, name=f'LOCAL_DISPATCH_SUM_{bid_type}_{region_id}_{prob.problem_id}')
                    # model.addLConstr(region.fcas_local_dispatch[bid_type], sense=gp.GRB.EQUAL, rhs=target, name=f'LOCAL_DISPATCH_SUM_{bid_type}_{region_id}')
                    # Fix local FCAS dispatch for each region (custom flag for debugging)
                    if fixed_local_fcas_flag:
                        model.addLConstr(region.fcas_local_dispatch[bid_type] <= region.fcas_local_dispatch_record[bid_type], name=f'LOCAL_DISPATCH_{bid_type}_FIXED_{region_id}')
        # Generic constraints
        generic_slack_variables = set()
        if constr_flag:
            # constraints = constrain.get_constraints(process, current, units, connection_points, interconnectors, regions, start, fcas_flag)
            parse.add_xml_constr(current, start, predispatch_current, process, prob.units, prob.regions, prob.interconnectors, prob.constraints, fcas_flag, debug_flag)
            for constr in prob.constraints.values():
                # TODO: Figure out what's going on the above and below commented code
                # if helpers.condition3(process, constr.dispatch, constr.predispatch, constr.rhs) and constr.connection_point_flag:
                if (constr.bind_flag or process == 'dispatch') and (not constr.fcas_flag or fcas_flag):
                    if constr.violation_price is None:
                        constr.violation_price = constr.generic_constraint_weight * voll
                    if constr.constraint_type == '<=':
                        surplus = model.addVar(name=f'Surplus_{constr.gen_con_id}_{prob.problem_id}')
                        generic_slack_variables.add(f'Surplus_{constr.gen_con_id}_{prob.problem_id}')
                        prob.penalty += surplus * constr.violation_price
                        constr.constr = model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs - surplus <= constr.rhs, name=f'{constr.gen_con_id}_{prob.problem_id}')
                        if debug_flag:
                            if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record > constr.rhs and abs(constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record - constr.rhs) > 1:
                                logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} is violated')
                                logging.debug(f'lhs = {constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record} > rhs = {constr.rhs}')
                    elif constr.constraint_type == '=':
                        deficit = model.addVar(name=f'Deficit_{constr.gen_con_id}_{prob.problem_id}')
                        generic_slack_variables.add(f'Deficit_{constr.gen_con_id}_{prob.problem_id}')
                        surplus = model.addVar(name=f'Surplus_{constr.gen_con_id}_{prob.problem_id}')
                        generic_slack_variables.add(f'Surplus_{constr.gen_con_id}_{prob.problem_id}')
                        prob.penalty += (deficit + surplus) * constr.violation_price
                        constr.constr = model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs - surplus + deficit, sense=gp.GRB.EQUAL, rhs=constr.rhs, name=f'{constr.gen_con_id}_{prob.problem_id}')
                        if debug_flag:
                            if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record != constr.rhs and abs(constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record - constr.rhs) > 1:
                                logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} is violated')
                                logging.debug(f'lhs = {constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record} != rhs = {constr.rhs}')
                    elif constr.constraint_type == '>=':
                        deficit = model.addVar(name=f'Deficit_{constr.gen_con_id}_{prob.problem_id}')
                        generic_slack_variables.add(f'Deficit_{constr.gen_con_id}_{prob.problem_id}')
                        prob.penalty += deficit * constr.violation_price
                        constr.constr = model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs + deficit >= constr.rhs, name=f'{constr.gen_con_id}_{prob.problem_id}')
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
                    # TODO: Force lhs to equal lhs record
                    # model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs, sense=gp.GRB.EQUAL, rhs=constr.lhs, name=constr.gen_con_id)
                    # Hard constraints
                    if hard_flag:
                        model.addLConstr(prob.penalty, sense=gp.GRB.EQUAL, rhs=0, name='PENALTY_CONSTR')
        return prob, model, cvp
    except gp.GurobiError as e:
        print(e)
        print(f'start datetime {start} no {interval} current datetime {current} {process}')
    # except AttributeError as e:
    #     print(e)
    #     print(f'start datetime {start} no {interval} current datetime {current}')


def formulate(start, interval, process, iteration=0, custom_unit=None, path_to_out=default.OUT_DIR, batteries=None,
              constr_flag=True, dispatchload_path=None, dispatchload_flag=True, hard_flag=False, fcas_flag=True,
              dual_flag=True, der_flag=False, losses_flag=True, fixed_total_cleared_flag=False, debug_flag=False,
              batt_no=None, dispatchload_record=True, link_flag=True, intervals=None, bilevel_flag = False):
    """Original NEMDE model.

    Args:
        start (datetime.datetime): start datetime
        interval (int): interval number
        process (str): 'dispatch', 'p6min' or 'predispatch'
        iteration (int): iteration number
        custom_unit:
        path_to_out (pathlib.Path): path to the out directory
        dispatchload_path (pathlib.Path): path to dispatchload file
        dispatchload_flag (bool): True if use our DISPATCHLOAD; False if use AEMO'S DISPATCHLOAD record
        hard_flag (bool): Whether apply hard constraints or not
        fcas_flag (bool): Whether calculate FCAS or not
        dual_flag (bool): Calculate dual var as price or increase regional demand by 1
        fixed_total_cleared_flag (bool): Whether fix generator target or not
        debug_flag (bool): Whether to write debugging information into log file
        batt_no (str): battery number (used to debug)

    Returns:
        (pathlib.Path, float, dict): path to DISPATCHLOAD file, RRP, FCAS RRP
    """
    if intervals is None:
        intervals = 30 if process == 'predispatch' or process == 'extension' else 5  # Length of the dispatch interval in minutes
    current = start + interval * datetime.timedelta(minutes=intervals)  # Current interval datetime
    if process == 'extension':
        current -= default.ONE_DAY
        start = current
    print(start, process, current)
    if process == 'predispatch':
        predispatch_current = current
        current -= default.TWENTYFIVE_MIN
    else:
        predispatch_current = None
    logging.info('----------------------------------------------------------------------------------')
    logging.info(f'Current interval is {current} (No. {interval} starting at {start}) for {process}')
    with gp.Env() as env, gp.Model(env=env,
                                   name=f'{process}{default.get_case_datetime(current)}{interval}{iteration}') as model:
        model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
        prob, model, cvp = dispatch(current, start, predispatch_current, interval, process, model, iteration,
                                    custom_unit, path_to_out, dispatchload_path, dispatchload_flag, fcas_flag=fcas_flag,
                                    constr_flag=constr_flag, dual_flag=dual_flag, debug_flag=debug_flag, der_flag=der_flag,
                                    link_flag=link_flag, batteries=batteries, intervals=intervals, losses_flag=losses_flag,
                                    dispatchload_record=dispatchload_record, fixed_total_cleared_flag=fixed_total_cleared_flag)
        # Calculate marginal prices
        prices = {'NSW1': None, 'VIC1': None, 'SA1': None, 'TAS1': None, 'QLD1': None}
        # Calculate dual variable as marginal price
        if dual_flag or fixed_total_cleared_flag:
            for region_id, region in prob.regions.items():
                prob.penalty = add_regional_energy_demand_supply_balance_constr(model, region, region_id, prob.problem_id, debug_flag, prob.penalty, cvp)
            objVal = None
            # Set objective
            if hard_flag:
                model.addLConstr(prob.penalty, sense=gp.GRB.EQUAL, rhs=0, name='PENALTY_CONSTR')
            model.setObjective(prob.cost + prob.penalty, gp.GRB.MINIMIZE)
            if bilevel_flag:
                from bilevel import feasible
                feasible(model, prob.problem_id, prob.units)
            # model.update()
            # random.seed(20)
            # obj = model.getObjective()
            # small_terms = [random.randint(1, 100) for _ in range(obj.size())]
            # added_term = 0
            # for i in range(obj.size()):
            #     added_term += obj.getVar(i) * small_terms[i] / 10000000
            # model.setObjective(prob.cost + prob.penalty + added_term, gp.GRB.MINIMIZE)
            # for unit in custom_unit:
            if link_flag:
                # obj_battery_constr = model.addLConstr(unit.total_cleared, sense=gp.GRB.EQUAL, rhs=0, name=f'Battery_{unit.duid}_{prob.problem_id}')
                for link_id in ['BLNKVIC', 'BLNKTAS']:
                    link = prob.links[link_id]
                    obj_link_constr = model.addLConstr(link.mw_flow, sense=gp.GRB.EQUAL, rhs=0, name=f'BASSLINK_{link_id}_{prob.problem_id}')
                    # Optimize model
                    model.optimize()

                    if bilevel_flag:
                        from bilevel import feasible
                        feasible(model, prob.problem_id, prob.units)

                    if model.status == gp.GRB.Status.INFEASIBLE or model.status == gp.GRB.Status.INF_OR_UNBD:
                        debug.debug_infeasible_model(model)
                        return None
                    elif model.status == gp.GRB.Status.OPTIMAL:
                        if objVal is None:
                            objective = model.getObjective()
                            objVal = model.objVal
                            model.remove(obj_link_constr)
                        else:
                            objVal_temp = model.objVal
                            if objVal <= objVal_temp:
                                model.remove(obj_link_constr)
                                continue
                            else:
                                objVal = objVal_temp
                                objective = model.getObjective()
                                model.remove(obj_link_constr)
                        # Get dual total_cleared of regional energy balance constraint
                        for region in prob.regions.values():
                            prices[region.region_id] = region.rrp_constr.pi
                            region.rrp = region.rrp_constr.pi
                            for fcas_type, fcas_constr in region.local_fcas_constr.items():
                                region.fcas_rrp[fcas_type] = - fcas_constr.pi
                        dispatchload_path = result.write_dispatchload(prob.units, prob.links,
                                                                      predispatch_current if process == 'predispatch' else current,
                                                                      start, process, k=iteration, path_to_out=path_to_out, batt_no=batt_no)
                        # Model Debugging
                        if debug_flag:
                            # # TODO: Debug objective value based on AEMO record

                            # Write binding constraints into file
                            # debug.write_binding_constrs(model.getConstrs(), path_to_out,
                            #                             predispatch_current if process == 'predispatch' else current,
                            #                             batt_no)
                            # # Verify if AEMO binding constraints are also binding in our model and vice versa
                            # debug.verify_binding_constr(model, constraints)
                            # # Verify region record
                            # debug.verify_region_record(regions)
                            # # Compare with total cleared record
                            # debug.compare_total_cleared_and_fcas(units)
                            # # Check binding generic FCAS constraints to find the way to calculate FCAS RRP
                            # # debug.check_binding_generic_fcas_constraints(regions, constraints)
                            # Check all the violated constraints
                            if prob.penalty.getValue() > 0:
                                print(f'Total objective is {model.objVal: e}')
                                print(f'Total violation is {prob.penalty.getValue(): e}')
                                debug.check_violation(model, prob.regions, prob.penalty)
                            # Generate result csv
                            result.write_result_csv(process, start,
                                                    predispatch_current if process == 'predispatch' else current, objVal,
                                                    prob.solution,
                                                    prob.penalty.getValue(),
                                                    prob.interconnectors,
                                                    prob.regions,
                                                    prob.units,
                                                    fcas_flag, k=iteration, path_to_out=path_to_out, batt_no=batt_no)
                            # Write objective into file
                            debug.write_objective(objective, path_to_out,
                                                  predispatch_current if process == 'predispatch' else current, batt_no)
                            # Write model for debugging
                            if batt_no is not None:
                                path_to_model = path_to_out / f'{process}_{default.get_case_datetime(current)}-batt{batt_no}.lp'
                            else:
                                path_to_model = path_to_out / process / f'{process}_{default.get_case_datetime(current)}.lp'
                            model.write(str(path_to_model))
                # model.remove(obj_battery_constr)
            else:
                model.optimize()
                # path_to_model = path_to_out / process / f'{process}_{default.get_case_datetime(current)}.lp'
                # model.write(str(path_to_model))
                for region in prob.regions.values():
                    prices[region.region_id] = region.rrp_constr.pi
                    region.rrp = region.rrp_constr.pi
                    if fcas_flag:
                        for fcas_type, fcas_constr in region.local_fcas_constr.items():
                            region.fcas_rrp[fcas_type] = - fcas_constr.pi
                dispatchload_path = result.write_dispatchload(prob.units, prob.links,
                                                              predispatch_current if process == 'predispatch' else current,
                                                              start, process, k=iteration, path_to_out=path_to_out,
                                                              batt_no=batt_no)
        # Calculate difference of objectives by increasing demand by 1 as marginal price
        else:
            # for region_name in [None, 'NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']:
            for region_name in [None, 'NSW1']:
                for region_id, region in prob.regions.items():
                    if region_name is None:
                        prob.penalty = add_regional_energy_demand_supply_balance_constr(model, region, region_id, prob.problem_id, debug_flag, prob.penalty, cvp)
                    else:
                        model.remove(region.rrp_constr)
                        increase = 1 if region_id == region_name else 0
                        region.rrp_constr = model.addLConstr(
                            region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen == region.total_demand + increase + region.dispatchable_load + region.losses,
                            name=f'REGION_BALANCE_{region_id}_{prob.problem_id}')
                # Set objective
                if hard_flag:
                    model.addLConstr(prob.penalty, sense=gp.GRB.EQUAL, rhs=0, name='PENALTY_CONSTR')
                model.setObjective(prob.cost + prob.penalty, gp.GRB.MINIMIZE)

                model.optimize()
                if model.status == gp.GRB.Status.INFEASIBLE or model.status == gp.GRB.Status.INF_OR_UNBD:
                    debug.debug_infeasible_model(model)
                    return None
                elif region_name is None:
                    fixed = model.fixed()
                    fixed.optimize()
                    bal_constr = fixed.getConstrByName(f'REGION_BALANCE_NSW1_{prob.problem_id}')
                    if debug_flag:
                        path_to_model = path_to_out / process / f'SOS_{default.get_case_datetime(current)}.lp'
                        # model.write(str(path_to_model))
                    # debug.verify_binding_constr(model, constraints)
                    base = prob.cost.getValue()
                    # Generate result csv
                    dispatchload_path = result.write_dispatchload(prob.units, prob.links, predispatch_current if process == 'predispatch' else current, start, process, k=iteration, path_to_out=path_to_out)
                    if batteries is not None:
                        for b in batteries.values():
                             g, l = b.generator.total_cleared.x, b.load.total_cleared.x
                    if debug_flag:
                        result.write_result_csv(process, start,
                                                predispatch_current if process == 'predispatch' else current, model.objVal,
                                                prob.solution, prob.penalty.getValue(),
                                                prob.interconnectors, prob.regions, prob.units, fcas_flag, k=iteration,
                                                path_to_out=path_to_out)
                else:
                    prices[region_name] = prob.cost.getValue() - base
                    prob.regions[region_name].rrp = prices[region_name]
            # result.add_prices(process, start, current, prices)
        # # Calculate dual variables of fixed MIP model
        # else:
        #     for region_id, region in prob.regions.items():
        #         prob.penalty = add_regional_energy_demand_supply_balance_constr(model, region, region_id, prob.problem_id, debug_flag, prob.penalty, cvp)
        #     # Set objective
        #     model.setObjective(prob.cost + prob.penalty, gp.GRB.MINIMIZE)
        #     model.optimize()
        #     fixed = model.fixed()
        #     fixed.optimize()
        #     for region_id, region in prob.regions.items():
        #         c = fixed.getConstrByName(f'REGION_BALANCE_{region_id}_{prob.problem_id}')
        #         prices[region_id] = c.pi
        #         region.rrp = c.pi
        #     dispatchload_path = result.write_dispatchload(prob.units, prob.links,
        #                                                   predispatch_current if process == 'predispatch' else current,
        #                                                   start, process, k=iteration, path_to_out=path_to_out,
        #                                                   batt_no=batt_no)
        if process == 'p5min':
            result.write_p5min(start, current, interval, prob.regions, prices, k=iteration, path_to_out=path_to_out)
        elif process == 'predispatch':
            result.write_predispatchis(start, predispatch_current, interval, prob.regions, prices, k=iteration,
                                       path_to_out=path_to_out)
        else:
            result.write_dispatchis(start, current, prob.regions, prices, k=iteration, path_to_out=path_to_out)
        if der_flag:
            return g, l, prob.regions['NSW1'].rrp
        return dispatchload_path, prob.regions['NSW1'].rrp, prob.regions['NSW1'].fcas_rrp, (None if dual_flag else bal_constr.pi)


def get_all_dispatch(start, process, path_to_out, custom_unit=None):
    total = helpers.get_total_intervals(process, start)
    for i in range(total):
        prices = formulate(start=start, interval=i, process=process, custom_unit=custom_unit, debug_flag=False, path_to_out=path_to_out, dispatchload_flag=False if i == 0 else True)
    return prices


if __name__ == '__main__':
    process_type = 'dispatch'
    # process_type = 'p5min'
    # process_type = 'predispatch'
    start = datetime.datetime(2021, 7, 18, 15, 30)
    # start = datetime.datetime(2020, 9, 1, 4, 30)
    # end = datetime.datetime(2020, 9, 2, 4, 0)
    # max_i = (end - start) / default.THIRTY_MIN

    # path_to_log = default.LOG_DIR / f'{process_type}_{default.get_case_datetime(start)}.log'
    # logging.basicConfig(filename=path_to_log, filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)

    # usage = 'DER Lucky'
    # e = 0
    # times = [start + default.FIVE_MIN * i for i in range(12)]
    # results = [[0, 0] for _ in times]
    # extended_times = [None for _ in times]
    # formulate_sequence(start, e, usage, results, times, extended_times, first_horizon_flag=True, link_flag=False, dual_flag=False)

    # dual_flag = True
    # path_to_out = default.DEBUG_DIR / ('dual' if dual_flag else 'sos')
    path_to_out = default.OUT_DIR / 'non-time-stepped KKT'
    # for i in range(1):
    #     if i == 0:
    #         process_type = 'dispatch'
    #     elif i > max_i:
    #         process_type = 'extension'
    #     else:
    #         process_type = 'predispatch'
    #     dispatchload_path, rrp, fcas_rrp = formulate(start, i, process_type, batteries=None, der_flag=False, intervals=None,
    #                                                  path_to_out=path_to_out, fcas_flag=False, link_flag=True, constr_flag=False,
    #                                                  dual_flag=dual_flag, dispatchload_record=(i == 0), debug_flag=False,
    #                                                  dispatchload_flag=(i != 0), fixed_total_cleared_flag=False, dispatchload_path=None if i == 0 else dispatchload_path)
    #     print(i, rrp)
    #     # print(dispatchload_path)
    #     # g, l, generator_fcas, load_fcas = read_dispatchload(dispatchload_path)
    #     # g, l, rrp = formulate(start, i, 'dispatch', batteries={battery.bat_id: battery}, der_flag=True,
    #     #                       path_to_out=battery.bat_dir, fcas_flag=False, link_flag=False,
    #     #                       dual_flag=False, dispatchload_record=False, debug_flag=False,
    #     #                       dispatchload_flag=(i != 0))
    #     # battery.initial_E += (l * battery.eff - g / battery.eff) * 5 / 60
    #     # Es.append(battery.initial_E)
    #     # prices.append(rrp)
    #     # start += default.FIVE_MIN
    prices, fixed_prices = [], []
    for i in range(1):
        dispatchload_path, rrp, fcas_rrp, fixed_rrp = formulate(start, i, process_type, batteries=None, der_flag=False,
                                                               intervals=60, losses_flag=False,
                                                               path_to_out=path_to_out, fcas_flag=False, link_flag=False,
                                                               constr_flag=False,
                                                               dual_flag=True, dispatchload_record=(i == 0),
                                                               debug_flag=False, bilevel_flag=True,
                                                               dispatchload_flag=(i != 0), fixed_total_cleared_flag=False,
                                                               dispatchload_path=None if i == 0 else dispatchload_path)
        print(i, rrp, fixed_rrp)
        # prices.append(rrp)
        # fixed_prices.append(fixed_rrp)
    # print(prices)
    # print(fixed_prices)