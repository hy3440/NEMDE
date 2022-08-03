# NEMDE simulation model
import csv
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
import random
import result
from preprocess import get_market_price
from plot import plot_optimisation_with_bids


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
        self.penalty = 0.0
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
        self.units = {}
        self.constraints = {}
        for region in self.regions.values():
            region.dispatchable_generation = 0.0
            region.dispatchable_generation_temp = 0.0
            region.dispatchable_load = 0.0
            region.dispatchable_load_temp = 0.0
            region.net_mw_flow = 0.0
            region.fcas_local_dispatch = {}  # Used to dispatch generic constraint
            region.fcas_local_dispatch_temp = {
                'RAISEREG': 0,
                'RAISE6SEC': 0,
                'RAISE60SEC': 0,
                'RAISE5MIN': 0,
                'LOWERREG': 0,
                'LOWER6SEC': 0,
                'LOWER60SEC': 0,
                'LOWER5MIN': 0
            }  # Used to calculate the sum of our FCAS value
            region.fcas_local_dispatch_record_temp = {
                'RAISEREG': 0,
                'RAISE6SEC': 0,
                'RAISE60SEC': 0,
                'RAISE5MIN': 0,
                'LOWERREG': 0,
                'LOWER6SEC': 0,
                'LOWER60SEC': 0,
                'LOWER5MIN': 0
            }  # Used to calculate the sum of each FCAS type
            region.fcas_constraints = {
                'RAISEREG': set(),
                'RAISE6SEC': set(),
                'RAISE60SEC': set(),
                'RAISE5MIN': set(),
                'LOWERREG': set(),
                'LOWER6SEC': set(),
                'LOWER60SEC': set(),
                'LOWER5MIN': set()
            }
            region.local_fcas_constr = {}  # required
            region.fcas_rrp = {}  # required
            region.losses = 0.0  # required


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
             fixed_interflow_flag=False, fixed_total_cleared_flag=False, fixed_fcas_value_flag=False,
             fixed_local_fcas_flag=False, ic_record_flag=False, debug_flag=False, der_flag=False, last_prob_id=None,
             intervals=None, batteries=None, daily_energy_flag=False, dispatchload_record=False, prob=None):
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
        if prob is None:
            prob = Problem(predispatch_current if process == 'predispatch' else current, process, batteries, debug_flag)
            # Get regions, interconnectors, and case solution
            interconnect.get_regions_and_interconnectors(current, start, interval, process, prob, fcas_flag, link_flag, dispatchload_record, debug_flag)
        else:
            # prob.reset_problem(predispatch_current if process == 'predispatch' else current, process, batteries)
            prob.current = current
            prob.process = process
            prob.problem_id = f'{process}_{default.get_case_datetime(current)}'
            prob.batteries = batteries
            prob.units = {}
            prob.constraints = {}
            for region in prob.regions.values():
                region.dispatchable_generation = 0.0
                region.dispatchable_generation_temp = 0.0
                region.dispatchable_load = 0.0
                region.dispatchable_load_temp = 0.0
                region.net_mw_flow = 0.0
                region.fcas_local_dispatch = {}  # Used to dispatch generic constraint
                region.fcas_local_dispatch_temp = {
                    'RAISEREG': 0,
                    'RAISE6SEC': 0,
                    'RAISE60SEC': 0,
                    'RAISE5MIN': 0,
                    'LOWERREG': 0,
                    'LOWER6SEC': 0,
                    'LOWER60SEC': 0,
                    'LOWER5MIN': 0
                }  # Used to calculate the sum of our FCAS value
                region.fcas_local_dispatch_record_temp = {
                    'RAISEREG': 0,
                    'RAISE6SEC': 0,
                    'RAISE60SEC': 0,
                    'RAISE5MIN': 0,
                    'LOWERREG': 0,
                    'LOWER6SEC': 0,
                    'LOWER60SEC': 0,
                    'LOWER5MIN': 0
                }  # Used to calculate the sum of each FCAS type
                region.fcas_constraints = {
                    'RAISEREG': set(),
                    'RAISE6SEC': set(),
                    'RAISE60SEC': set(),
                    'RAISE5MIN': set(),
                    'LOWERREG': set(),
                    'LOWER6SEC': set(),
                    'LOWER60SEC': set(),
                    'LOWER5MIN': set()
                }
                region.local_fcas_constr = {}  # required
                region.fcas_rrp = {}  # required
                region.losses = 0.0  # required
            interconnect.add_dispatch_record(current, start, interval, process, prob, fcas_flag, debug_flag)
        # Add cutom unit
        if custom_unit is not None:
            if type(custom_unit) == list:
                for unit in custom_unit:
                    prob.units[unit.duid] = unit
            else:
                prob.units[custom_unit.duid] = custom_unit
        # Add batteries' generator and load
        if batteries is not None:
            for battery in batteries.values():
                for unit in [battery.generator, battery.load]:
                    prob.units[unit.duid] = unit
        # Specify the length of interval
        if intervals is None:
            intervals = 30 if process == 'predispatch' else 5  # Length of the dispatch interval in minutes
        # # Get regions, interconnectors, and case solution
        # interconnect.get_regions_and_interconnectors(current, start, interval, process, prob, fcas_flag, link_flag, dispatchload_record, debug_flag)
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
            prob.penalty = constrain.add_interconnector_capacity_constr(model, ic, ic_id, prob.problem_id, debug_flag, prob.penalty, cvp)
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
                prob.penalty = constrain.add_mnsp_ramp_constr(model, intervals, link, link_id, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Add total band MW offer constraint - MNSP only
                prob.penalty = constrain.add_mnsp_total_band_constr(model, link, link_id, prob.problem_id, debug_flag, prob.penalty, cvp)
                # MNSP Max Capacity
                if link.max_capacity is not None and not der_flag and debug_flag:
                    if link.mw_flow_record is not None and link.mw_flow_record > link.max_capacity and debug_flag:
                        logging.warning(f'Link {link_id} mw flow record {link.mw_flow_record} above max capacity {link.max_capacity}')
                # Add MNSP availability constraint
                prob.penalty = constrain.add_mnsp_avail_constr(model, link, link_id, prob.problem_id, debug_flag, prob.penalty, cvp)

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
                for no, avail in enumerate(unit.energy.band_avail):
                    bid_offer = model.addVar(name=f'Energy_Avail{no}_{unit.duid}_{prob.problem_id}')
                    unit.offers.append(bid_offer)
                    model.addLConstr(bid_offer <= avail, name=f'ENERGY_AVAIL{no}_{unit.duid}_{prob.problem_id}')
                # Total dispatch total_cleared
                unit.total_cleared = model.addVar(name=f'Total_Cleared_{unit.duid}_{prob.problem_id}')

                # if unit.duid == 'LOYYB1':
                #     model.addConstr(unit.total_cleared, gp.GRB.EQUAL, 487.75331844441655, name='DEBUG')

                # TODO: Unit max cap (not included yet)
                if unit.max_capacity is not None:
                    # model.addLConstr(unit.total_cleared <= unit.max_capacity, name='MAX_CAPACITY_{}'.format(unit.duid))
                    if unit.total_cleared_record is not None and unit.total_cleared_record > unit.max_capacity:
                        logging.warning(f'{unit.dispatch_type} {unit.duid} total cleared record {unit.total_cleared_record} above max capacity {unit.max_capacity}')
                # Add Unit MaxAvail constraint
                if unit.energy.max_avail is not None:
                    prob.penalty = constrain.add_max_avail_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Daily Energy Constraint (only for 30min Pre-dispatch)
                if process == 'predispatch' and daily_energy_flag and unit.energy.daily_energy_limit != 0 and unit.energy.daily_energy_limit is not None:
                    prob.penalty = constrain.add_daily_energy_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Add total band MW offer constraint
                prob.penalty = constrain.add_total_band_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Add Unconstrained Intermittent Generation Forecasts (UIGF) constraint (See AEMO2019Dispatch)
                if process != 'predispatch':
                    prob.penalty = constrain.add_uigf_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                elif process == 'predispatch' and unit.total_cleared_record is not None and unit.forecast_poe50 is not None:
                    model.addLConstr(unit.total_cleared <= unit.total_cleared_record)
                    # print(f'{unit.duid} record {unit.total_cleared_record} forecast {unit.forecast_poe50} capacity {unit.max_capacity} avail {unit.energy.max_avail} sum {sum(unit.energy.band_avail)}')
                # Add on-line dispatch fast start inflexibility profile constraint (See AEMO2014Fast)
                if process == 'dispatch':
                    prob.penalty = constrain.add_fast_start_inflexibility_profile_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Add unit ramp rate constraint
                # If the total MW value of its bid/offer bands is zero or the unit is a fast start unit and it is
                # targeted to be in mode 0, 1, or 2, its ramp rate constraints will be ignored.
                if sum(unit.energy.band_avail) > 0 and (process != 'dispatch' or unit.start_type != 'FAST' or unit.dispatch_mode > 2):
                    prob.penalty = constrain.add_unit_ramp_constr(process, model, intervals, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Add fixed loading constraint
                prob.penalty = constrain.add_fixed_loading_constr(model, unit, prob.problem_id, debug_flag, prob.penalty, cvp)
                # Marginal loss factor
                if unit.transmission_loss_factor is None:
                    logging.error(f'{unit.dispatch_type} {unit.duid} has no MLF.')
                    unit.transmission_loss_factor = 1.0
                # TODO: Add Tie-Break constraint
                prob.penalty = constrain.add_tie_break_constr(model, unit, energy_bands[unit.dispatch_type][unit.region_id], prob.penalty, cvp)
                # Calculate cost
                prob.cost = constrain.add_cost(unit, prob.regions, prob.cost, debug_flag)
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
                    constrain.preprocess_fcas(unit, process, interval, intervals, debug_flag, agc_flag)
                    # Co-optimise energy and FCAS
                    for bid_type, fcas in unit.fcas_bids.items():
                        prob.regions[unit.region_id].fcas_local_dispatch_record_temp[bid_type] += 0 if not unit.target_record else unit.target_record[bid_type]  # Add FCAS record to region
                        if fcas.enablement_status == 1:
                            prob.cost, prob.penalty = constrain.process_fcas_bid(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp, prob.cost, prob.regions)
                            if bid_type == 'RAISEREG' or bid_type == 'LOWERREG':
                                # Add joint ramping constraint
                                if helpers.condition2(process, interval):
                                    prob.penalty = constrain.add_joint_ramping_constr(model, intervals, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp)
                                # TODO: Add energy and regulating FCAS capacity constraint
                                constrain.add_energy_and_fcas_capacity_constr(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp)
                            else:
                                prob.penalty = constrain.add_joint_capacity_constr(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp)
                                # # Add FCAS EnablementMin constr
                                # prob.penalty = constrain.add_enablement_min_constr(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp)
                                # # Add FCAS EnablementMax constr
                                # prob.penalty = constrain.add_enablement_max_constr(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp)
                        else:
                            if debug_flag and unit.target_record and unit.target_record[bid_type] != 0:
                                logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} is not enable but record {unit.target_record[bid_type]}')
                # Only bid for FCAS
                else:
                    for bid_type, fcas in unit.fcas_bids.items():
                        prob.cost, prob.penalty = constrain.process_fcas_bid(model, unit, fcas, bid_type, prob.problem_id, debug_flag, prob.penalty, cvp, prob.cost, prob.regions)
                        prob.regions[unit.region_id].fcas_local_dispatch_record_temp[bid_type] += 0 if not unit.target_record else unit.target_record[bid_type]  # Add FCAS record to region
                # Fix unit FCAS target (custom flag for debugging)
                if fixed_fcas_value_flag and fcas_flag and unit.fcas_bids != {}:
                    for bid_type, fcas in unit.fcas_bids.items():
                        model.addLConstr(fcas.value == unit.target_record[bid_type], name=f'{bid_type}_FIXED_{unit.duid}')
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
                if not dual_flag:
                    # Charge or discharge
                    battery.sos_constr = model.addSOS(gp.GRB.SOS_TYPE1, [battery.generator.total_cleared, battery.load.total_cleared])
                    # # Degradation model
                    pgens = [model.addVar(ub=battery.generator.max_capacity, name=f'pgen_segment_{m + 1}_{prob.problem_id}') for m in range(M)]
                    model.addLConstr(battery.generator.total_cleared == sum(pgens), f'PGEN_SEGMENT_{prob.problem_id}')
                    prob.cost += (intervals / 60) * sum([pgens[m] * helpers.marginal_costs(R, battery.eff, M, m + 1) for m in range(M)])
        # TODO: Custom Battery fo comparison
        # if custom_unit is not None and type(custom_unit) == list:
        #     model.addSOS(gp.GRB.SOS_TYPE1, [unit.total_cleared for unit in custom_unit])
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
                        constr.surplus = model.addVar(name=f'Surplus_{constr.gen_con_id}_{prob.problem_id}')
                        generic_slack_variables.add(f'Surplus_{constr.gen_con_id}_{prob.problem_id}')
                        prob.penalty += constr.surplus * constr.violation_price
                        constr.constr = model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs - constr.surplus <= constr.rhs, name=f'{constr.gen_con_id}_{prob.problem_id}')
                        if debug_flag:
                            if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record > constr.rhs and abs(constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record - constr.rhs) > 1:
                                logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} is violated')
                                logging.debug(f'lhs = {constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record} > rhs = {constr.rhs}')
                    elif constr.constraint_type == '=':
                        constr.deficit = model.addVar(name=f'Deficit_{constr.gen_con_id}_{prob.problem_id}')
                        generic_slack_variables.add(f'Deficit_{constr.gen_con_id}_{prob.problem_id}')
                        constr.surplus = model.addVar(name=f'Surplus_{constr.gen_con_id}_{prob.problem_id}')
                        generic_slack_variables.add(f'Surplus_{constr.gen_con_id}_{prob.problem_id}')
                        prob.penalty += (constr.deficit + constr.surplus) * constr.violation_price
                        constr.constr = model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs - constr.surplus + constr.deficit, sense=gp.GRB.EQUAL, rhs=constr.rhs, name=f'{constr.gen_con_id}_{prob.problem_id}')
                        if debug_flag:
                            if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record != constr.rhs and abs(constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record - constr.rhs) > 1:
                                logging.warning(f'{constr.constraint_type} Constraint {constr.gen_con_id} is violated')
                                logging.debug(f'lhs = {constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record} != rhs = {constr.rhs}')
                    elif constr.constraint_type == '>=':
                        constr.deficit = model.addVar(name=f'Deficit_{constr.gen_con_id}_{prob.problem_id}')
                        generic_slack_variables.add(f'Deficit_{constr.gen_con_id}_{prob.problem_id}')
                        prob.penalty += constr.deficit * constr.violation_price
                        constr.constr = model.addLConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs + constr.deficit >= constr.rhs, name=f'{constr.gen_con_id}_{prob.problem_id}')
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
        print(f'start datetime {start} no {interval} current datetime {current}')
        path_to_model = default.MODEL_DIR / 'model.lp'
        model.write(str(path_to_model))
    # except AttributeError as e:
    #     print(e)
    #     print(f'start datetime {start} no {interval} current datetime {current}')


def formulate(start, interval, process, iteration=0, custom_unit=None, path_to_out=default.OUT_DIR,
              dispatchload_path=None, dispatchload_flag=True, hard_flag=False, fcas_flag=True, dual_flag=True,
              fixed_total_cleared_flag=False, debug_flag=False, batt_no=None, dispatchload_record=False, link_flag=True):
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
    intervals = 30 if process == 'predispatch' or process == 'extension' else 5  # Length of the dispatch interval in minutes
    current = start + interval * datetime.timedelta(minutes=intervals)  # Current interval datetime
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
        prob, model, cvp = dispatch(current, start, predispatch_current, interval, process, model, iteration, custom_unit,
                                    path_to_out, dispatchload_path, dispatchload_flag, fcas_flag=fcas_flag, dual_flag=dual_flag,
                                    debug_flag=debug_flag, der_flag=False, dispatchload_record=dispatchload_record, link_flag=link_flag)
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
            # model.update()
            # random.seed(20)
            # obj = model.getObjective()
            # small_terms = [random.randint(1, 100) for _ in range(obj.size())]
            # # print(small_terms)
            # added_term = 0
            # for i in range(obj.size()):
            #     added_term += obj.getVar(i) * small_terms[i] / 10000000
            # model.setObjective(prob.cost + prob.penalty + added_term, gp.GRB.MINIMIZE)
            # for unit in custom_unit:
            if True:
                # obj_battery_constr = model.addLConstr(unit.total_cleared, sense=gp.GRB.EQUAL, rhs=0, name=f'Battery_{unit.duid}_{prob.problem_id}')
                for link_id in ['BLNKVIC', 'BLNKTAS']:
                    link = prob.links[link_id]
                    obj_link_constr = model.addLConstr(link.mw_flow, sense=gp.GRB.EQUAL, rhs=0, name=f'BASSLINK_{link_id}_{prob.problem_id}')
                    # Optimize model
                    model.optimize()
                    if model.status == gp.GRB.Status.INFEASIBLE or model.status == gp.GRB.Status.INF_OR_UNBD:
                        debug.debug_infeasible_model(model)
                        return None
                    elif model.status == gp.GRB.Status.OPTIMAL:
                        # print(model.objVal)
                        # print(custom_unit[0].total_cleared)
                        # print(custom_unit[1].total_cleared)
                        # print(prob.regions['NSW1'].rrp_constr.pi)
                        # for unit in custom_unit:
                        #     print(unit.dispatch_type)
                        #     print('Price Band | Availability | Dispatch Target')
                        #     print('---------- | ------------ | ---------------')
                        #     for b, a, o in zip(unit.energy.price_band, unit.energy.band_avail, unit.offers):
                        #         print(f'{b} | {a} | {o.x}')
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
                            # # Check all the violated constraints
                            # # if penalty.getValue() > 0:
                            # #     print(f'Total violation is {penalty.getValue()}')
                            # #     debug.check_violation(model, regions, slack_variables, generic_slack_variables)
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
                        # path_to_model = default.MODEL_DIR / f'{process}_{default.get_case_datetime(start)}_{interval}.lp'
                        model.write(str(path_to_model))
                # model.remove(obj_battery_constr)
        # Calculate difference of objectives by increasing demand by 1 as marginal price
        else:
            for region_name in [None, 'NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']:
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
                path_to_model = path_to_out / process / f'SOS_{default.get_case_datetime(current)}.lp'
                model.write(str(path_to_model))
                model.optimize()
                if model.status == gp.GRB.Status.INFEASIBLE or model.status == gp.GRB.Status.INF_OR_UNBD:
                    debug.debug_infeasible_model(model)
                    return None
                elif region_name is None:
                    # debug.verify_binding_constr(model, constraints)
                    base = prob.cost.getValue()
                    # Generate result csv
                    dispatchload_path = result.write_dispatchload(prob.units, prob.links, predispatch_current if process == 'predispatch' else current, start, process, k=iteration, path_to_out=path_to_out)
                    if debug_flag:
                        result.write_result_csv(process, start,
                                                predispatch_current if process == 'predispatch' else current, model.objVal,
                                                prob.solution, prob.penalty.getValue(),
                                                prob.interconnectors, prob.regions, prob.units, fcas_flag, k=iteration,
                                                path_to_out=path_to_out)
                else:
                    prices[region_name] = prob.cost.getValue() - base
                    prob.regions[region_name].rrp = prices[region_name]
            result.add_prices(process, start, current, prices)
        if process == 'dispatch':
            result.write_dispatchis(start, current, prob.regions, prices, k=iteration, path_to_out=path_to_out)
        elif process == 'predispatch':
            result.write_predispatchis(start, predispatch_current, interval, prob.regions, prices, k=iteration,
                                       path_to_out=path_to_out)
        else:
            result.write_p5min(start, current, interval, prob.regions, prices, k=iteration, path_to_out=path_to_out)
        return dispatchload_path, prob.regions['NSW1'].rrp, prob.regions['NSW1'].fcas_rrp


def formulate_participation(e):
    # Battery participate in the original NEMDE
    p = int(e / 3 * 2)
    initial = datetime.datetime(2020, 9, 1, 4, 5)
    TOTAL_HORIZONS = 1
    for horizon in range(TOTAL_HORIZONS):
        start = initial + horizon * default.FIVE_MIN
        reminder = horizon % 6
        prices = []
        last_prob_id = None
        for j in range(12):
            current = start + j * default.FIVE_MIN
            batteries, custom_units = helpers.init_batteries(e, p, 'COMPARA')
            battery = batteries['Battery']
            dispatchload_path, p, _ = formulate(start, j, 'p5min', custom_unit=custom_units,
                                                path_to_out=battery.bat_dir,
                                                dispatchload_flag=False if j == 0 else True, fcas_flag=False,
                                                dual_flag=False)
            prices.append(p)
        predispatch_start = default.get_predispatch_time(start)
        end = start + default.ONE_DAY - default.FIVE_MIN
        for j in range(2, helpers.get_total_intervals('predispatch', predispatch_start)):
            predispatch_t = predispatch_start + j * default.THIRTY_MIN
            current = predispatch_t - default.TWENTYFIVE_MIN
            batteries, custom_units = helpers.init_batteries(e, p, 'COMPARA')
            battery = batteries['Battery']
            dispatchload_path, p, _ = formulate(start, j, 'predispatch', custom_unit=custom_units,
                                                path_to_out=battery.bat_dir, dispatchload_path=dispatchload_path,
                                                dispatchload_flag=True, fcas_flag=False, dual_flag=False)
            prices.append(p)


def update_formulation(prob, problems, model, total_costs, total_penalty, cvp):
    for region_id, region in prob.regions.items():
        prob.penalty = add_regional_energy_demand_supply_balance_constr(model, region, region_id, prob.problem_id,
                                                                        False, prob.penalty, cvp)
    problems.append(prob)
    last_prob_id = prob.problem_id
    total_costs += prob.cost
    total_penalty += prob.penalty
    model.update()
    return total_costs, total_penalty, last_prob_id


def add_regional_constr(prob, model, cvp):
    for region_id, region in prob.regions.items():
        prob.penalty = add_regional_energy_demand_supply_balance_constr(model, region, region_id, prob.problem_id,
                                                                        False, prob.penalty, cvp)


def battery_bid(battery, avails):
    if avails is None:
        battery.add_energy_bid([0], [battery.generator.max_capacity], [500], [battery.load.max_capacity])
    else:
        battery.add_energy_bid([0], [avails[0]], [500], [avails[1]])


def formulate_sequence(start, e, usage, results=None, times=None, extended_times=None, first_horizon_flag=False, predefined_battery=None, link_flag=False, dual_flag=True):
    """Improved NEMDE which looks ahead for 24hrs (12 intervals of P5MIN and 46 periods of Predispatch).

    Args:
        start (datetime.datetime): start datetime
        e (float): battery size
        usage (str): battery usage
        results (list): battery optimisation results
        times (list): datetimes

    Returns:
        (pathlib.Path, flaot, dict): path to DISPATCHLOAD file, RRP, FCAS RRP
    """
    # initial = datetime.datetime(2020, 9, 1, 4, 5)
    # TOTAL_HORIZONS = 1
    # for horizon in range(TOTAL_HORIZONS):
    #     # start = initial + horizon * default.FIVE_MIN
    #     reminder = horizon % 6
    # temp_j = 0
    if True:
        # problems = []
        saved_regions, saved_ids = [], []
        last_prob_id = None
        prob = None
        with gp.Env() as env, gp.Model(env=env,
                                       name=f'Integration {default.get_case_datetime(start)}') as model:
            model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
            # Initiate cost and penalty of objective function
            # total_costs, total_penalty = 0, 0

            # for j in range(12):
            #     current = start + j * default.FIVE_MIN
            #     battery = helpers.Battery(e, int(e / 3 * 2), usage=usage)
            #     battery_bid(battery, None if results is None else results[temp_j])
            #     prob, model, cvp = dispatch(current, start, None, j, 'p5min', model, dispatchload_flag=False,
            #                                 fcas_flag=False, der_flag=True, last_prob_id=last_prob_id,
            #                                 batteries={battery.bat_id: battery})
            #     temp_j += 1
            #     total_costs, total_penalty, last_prob_id = update_formulation(prob, problems, model, total_costs, total_penalty, cvp)
            # predispatch_start = default.get_predispatch_time(start)
            # end = start + default.ONE_DAY - default.FIVE_MIN
            # for j in range(2, helpers.get_total_intervals('predispatch', predispatch_start)):
            #     predispatch_t = predispatch_start + j * default.THIRTY_MIN
            #     current = predispatch_t - default.TWENTYFIVE_MIN
            #     battery = helpers.Battery(e, int(e / 3 * 2), usage=usage)
            #     battery_bid(battery, None if results is None else results[temp_j])
            #     # if predispatch_t > end:
            #     #     break
            #     prob, model, cvp = dispatch(current, predispatch_start, predispatch_t, j, 'predispatch', model,
            #                            dispatchload_flag=False, fcas_flag=False, der_flag=True,
            #                            last_prob_id=last_prob_id,
            #                            intervals=(6 - reminder) * 5 if j == 2 else None, batteries={battery.bat_id: battery})
            #     temp_j += 1
            #     total_costs, total_penalty, last_prob_id = update_formulation(prob, problems, model, total_costs, total_penalty, cvp)

            predispatch_start = default.get_predispatch_time(start)
            for j, (t, r, et) in enumerate(zip(times, results, extended_times)):
                constr_flag = False
                if predefined_battery is not None and j == 0:
                    battery = predefined_battery
                else:
                    battery = helpers.Battery(e, int(e / 3 * 2), usage=usage)
                    battery_bid(battery, None if 'None' in usage else r)
                # if j < 12:
                if j < 6:
                    current = t
                    process = 'dispatch' if j == 0 else 'p5min'
                    pre_start = start
                    intervals = None
                    pre_t = None
                    constr_flag = True
                elif et is None:
                    current = t - default.TWENTYFIVE_MIN
                    process = 'predispatch'
                    pre_start = predispatch_start
                    # j = j - 10
                    # intervals = (t - start - default.ONE_HOUR + default.FIVE_MIN) / default.ONE_MIN if j == 2 else None
                    j = j - 5
                    intervals = (t - start - default.THIRTY_MIN + default.FIVE_MIN) / default.ONE_MIN if j == 1 else None
                    pre_t = t
                else:
                    current = et
                    process = 'dispatch'
                    pre_start = et
                    intervals = None
                    pre_t = None
                # print(t, pre_start, j, intervals)
                prob, model, cvp = dispatch(current, pre_start, pre_t, j, process, model, path_to_out=battery.bat_dir,
                                            dispatchload_flag=(j==0 and not first_horizon_flag), dispatchload_record=True,
                                            fcas_flag='FCAS' in usage, der_flag=True, last_prob_id=last_prob_id, dual_flag=dual_flag,
                                            batteries={battery.bat_id: battery}, constr_flag=constr_flag,
                                            intervals=intervals, link_flag=link_flag)
                first_horizon_flag = False
                # total_costs, total_penalty, last_prob_id = update_formulation(prob, problems, model, total_costs, total_penalty, cvp)
                last_prob_id = prob.problem_id
                add_regional_constr(prob, model, cvp)
                saved_regions.append(prob.regions['NSW1'])
                saved_ids.append(prob.problem_id)
                if j == 0:
                    saved_units = prob.units
                    saved_links = [prob.links['BLNKVIC'].mw_flow, prob.links['BLNKTAS'].mw_flow]

            # for bat_id, battery in prob.batteries.items():
            #     battery.final_constr = model.addLConstr(battery.E, gp.GRB.EQUAL, battery.size * 0.5, f'FINAL_STATE_{bat_id}_{prob.problem_id}')
            # model.setObjective(total_costs + total_penalty, gp.GRB.MINIMIZE)
            model.setObjective(prob.cost + prob.penalty, gp.GRB.MINIMIZE)
            model.optimize()
            path_to_model = battery.bat_dir / f'DER_{e}MWh_{default.get_case_datetime(start)}.lp'
            model.write(str(path_to_model))
            print(f'Finished optimisation: {datetime.datetime.now()}')
            base = model.getObjective().getValue()
            region_id = 'NSW1'
            prices = []

            # print(saved_regions[0].rrp_constr.pi)
            # return None

            # dispatchload_path = result.write_dispatchload(saved_units, saved_links, times[0], times[0], 'dispatch',
            #                                               path_to_out=battery.bat_dir)
            levels, generations, loads = [], [], []
            bat_id = 'Battery'
            for problem_id in saved_ids:
                levels.append(model.getVarByName(f'E_{bat_id}_{problem_id}').x)
                generations.append(model.getVarByName(f'Total_Cleared_G_{problem_id}').x)
                loads.append(model.getVarByName(f'Total_Cleared_L_{problem_id}').x)

            # for prob_num, prob in enumerate(problems):
            #     region = prob.regions[region_id]
            print(f'Finished first interval: {datetime.datetime.now()}')
            if dual_flag:
                prices = [model.getConstrByName(f'REGION_BALANCE_{region_id}_{prob_id}').pi for prob_id in saved_ids]
                print(prices[0])
            else:
                for prob_num, (problem_id, region) in enumerate(zip(saved_ids, saved_regions)):
                    model.remove(region.rrp_constr)
                    region.rrp_constr = model.addLConstr(
                        region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen == region.total_demand + 1 + region.dispatchable_load + region.losses,
                        name=f'REGION_BALANCE_{region_id}_INCREASED')

                    # model.setObjective(total_costs + total_penalty, gp.GRB.MINIMIZE)
                    model.setObjective(prob.cost + prob.penalty, gp.GRB.MINIMIZE)
                    # model.addLConstr(total_penalty == 0, name='HARD_CONSTR')
                    model.optimize()
                    prices.append(model.getObjective().getValue() - base)
                    print(prices)
                    if prob_num == 0:
                        for b in prob.batteries.values():
                            result.write_dispatchis(None, start, prob.regions, {region_id: prices[0]}, k=0, path_to_out=b.bat_dir)
                            # return b.generator.total_cleared.x, b.load.total_cleared.x, prices[0]

                    # Get prices for all intervals
                    model.remove(region.rrp_constr)
                    region.rrp_constr = model.addLConstr(
                        region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen == region.total_demand + region.dispatchable_load + region.losses,
                        name=f'REGION_BALANCE_{region_id}_{problem_id}')
            path_to_csv = battery.bat_dir / f'DER_{battery.size}MWh_{default.get_case_datetime(start)}.csv'
            with path_to_csv.open('w') as f:
                writer = csv.writer(f)
                # for prob, p in zip(problems, prices):
                #     for b in prob.batteries.values():
                #         writer.writerow([prob.current, prob.process, b.E.x, b.generator.total_cleared.x, b.load.total_cleared.x, p])
                for t, e, g, l, p in zip(times, levels, generations, loads, prices):
                    writer.writerow([t, '', e, g, l, p])
            plot_optimisation_with_bids(battery, None, None, der_flag=True, e=battery.size, t=start, bat_dir=b.bat_dir)
            print(f'Finished all intervals: {datetime.datetime.now()}')


def get_all_dispatch(start, process, path_to_out, custom_unit=None):
    total = helpers.get_total_intervals(process, start)
    for i in range(total):
        prices = formulate(start=start, interval=i, process=process, custom_unit=custom_unit, debug_flag=False, path_to_out=path_to_out, dispatchload_flag=False if i == 0 else True)
    return prices


if __name__ == '__main__':
    # process_type = 'dispatch'
    # process_type = 'p5min'
    # process_type = 'predispatch'
    # start = datetime.datetime(2021, 9, 12, 4, 5)
    start = datetime.datetime(2020, 9, 1, 4, 5)

    # path_to_log = default.LOG_DIR / f'{process_type}_{default.get_case_datetime(start_time)}.log'
    # logging.basicConfig(filename=path_to_log, filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)
    # total_intervals = helpers.get_total_intervals(process_type, start_time)
    # # for interval in range(int((end_time-start_time) / default.FIVE_MIN + 1)):
    # last, interval = default.datetime_to_interval(datetime.datetime(2020, 9, 1, 4, 5, 0))
    # b = helpers.Battery(30, 20, 'NSW1', 2)
    # from price_taker import customise_unit
    # u = customise_unit(last, 20, 0, b, market_price_floor)
    # # _, p1, p2 = formulate(start_time, interval, process=process_type, dispatchload_flag=False, path_to_out=b.bat_dir, debug_flag=True)
    # # print(p1, p2)
    # formulate_sequence(30, 'DER-None')
    # formulate_sequence(datetime.datetime(2021, 9, 12, 4, 5), 30, 'DER-Price-taker', temp_results)
    # formulate_participation(30)
    # horizon = 0
    # path_to_out = default.OUT_DIR / 'tiebreak'
    # for i in range(128, 288):
    # import preprocess
    # preprocess.download_dispatch_summary(start_time, True)
    # preprocess.download_xml(start_time, True)
    # preprocess.download_predispatch(start_time, True)
    # while current <= end_time:
    # for horizon in range(288):
    #     dispatchload_path, rrp, fcas_rrp = formulate(start_time, horizon, 'dispatch', path_to_out=path_to_out, dispatchload_flag=(horizon != 0), debug_flag=False)
    #     current += default.FIVE_MIN
    # get_all_dispatch(start_time, process_type, path_to_out)

    # dispatchload_path, rrp, fcas_rrp = formulate(start, 0, 'dispatch',
    #                                              path_to_out=default.DEBUG_DIR,
    #                                              dispatchload_flag=False,
    #                                              dispatchload_record=True,
    #                                              fcas_flag=False,
    #                                              dual_flag=True)
    # print(rrp)
    usage = 'DER Test'
    e = 0
    times = [start + default.FIVE_MIN * i for i in range(2)]
    results = [[0, 0] for _ in times]
    extended_times = [None for _ in times]
    formulate_sequence(start, e, usage, results, times, extended_times, first_horizon_flag=True, link_flag=False, dual_flag=False)