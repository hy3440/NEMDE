import gurobipy
import logging


def add_max_avail_constr(model, unit, hard_flag, slack_variables, penalty, voll, cvp):
    # Unit MaxAvail constraint
    if unit.dispatch_type == 'LOAD':
        unit.deficit_trader_energy_capacity = model.addVar(name='Deficit_Trader_Energy_Capacity_{}'.format(unit.duid))  # Item14 CONFUSED
        slack_variables.add('Deficit_Trader_Energy_Capacity_{}'.format(unit.duid))
        if hard_flag:
            model.addConstr(unit.deficit_trader_energy_capacity, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'DEFICIT_TRADER_ENERGY_CAPACITY_{unit.duid}')
        penalty += unit.deficit_trader_energy_capacity * cvp['Unit_MaxAvail'] * voll
        unit.max_avail_constr = model.addConstr(unit.total_cleared - unit.deficit_trader_energy_capacity <= unit.energy.max_avail, name=f'MAX_AVAIL_{unit.duid}')
    return penalty


def add_total_band_constr(model, unit, hard_flag, slack_variables, penalty, voll, cvp):
    # Total Band MW Offer constraint
    unit.deficit_offer_mw = model.addVar(name=f'Deficit_Offer_MW_{unit.duid}')  # Item8
    slack_variables.add(f'Deficit_Offer_MW_{unit.duid}')
    if hard_flag:
        model.addConstr(unit.deficit_offer_mw, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'DEFICIT_OFFER_MW_{unit.duid}')
    penalty += unit.deficit_offer_mw * cvp['Total_Band_MW_Offer'] * voll
    unit.total_band_mw_offer_constr = model.addConstr(unit.total_cleared + unit.deficit_offer_mw,
                                                      sense=gurobipy.GRB.EQUAL,
                                                      rhs=sum(unit.offers),
                                                      name=f'TOTAL_BAND_MW_OFFER_{unit.duid}')
    return penalty


def add_uigf_constr(model, unit, regions, hard_flag, slack_variables, penalty, voll, cvp):
    # Unconstrained Intermittent Generation Forecasts (UIGF) for Dispatch
    if unit.forecast_priority is not None and unit.forecast_poe50 is None:
        logging.error(f'Generator {unit.duid} forecast priority is but has no forecast POE50')
    elif unit.forecast_poe50 is not None:
        unit.uigf_surplus = model.addVar(name=f'UIGF_Surplus_{unit.duid}')  # Item12
        slack_variables.add(f'UIGF_Surplus_{unit.duid}')
        if hard_flag:
            model.addConstr(unit.uigf_surplus, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'UIGF_SURPLUS_{unit.duid}')
        penalty += unit.uigf_surplus * cvp['UIGF'] * voll
        model.addConstr(unit.total_cleared - unit.uigf_surplus <= unit.forecast_poe50, name=f'UIGF_{unit.duid}')
        if unit.total_cleared_record is not None and unit.total_cleared_record > unit.forecast_poe50 and abs(unit.total_cleared_record - unit.forecast_poe50) > 0.1:
            logging.warning(
                f'{unit.dispatch_type} {unit.duid} total cleared record {unit.total_cleared_record} above UIGF forecast {unit.forecast_poe50}')
    return penalty


def add_fast_start_inflexibility_profile_constr(model, unit, hard_flag, slack_variables, penalty, voll, cvp):
    # Fast Start Inflexible Profile constraint
    if unit.dispatch_mode > 0:
        unit.profile_deficit_mw = model.addVar(name=f'Profile_Deficit_MW_{unit.duid}')  # Item10
        unit.profile_surplus_mw = model.addVar(name=f'Profile_Surplus_MW_{unit.duid}')  # Item10
        slack_variables.add(f'Profile_Deficit_MW_{unit.duid}')
        slack_variables.add(f'Profile_Surplus_MW_{unit.duid}')
        if hard_flag:
            model.addConstr(unit.profile_deficit_mw, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'PROFILE_DEFICIT_MW_{unit.duid}')
            model.addConstr(unit.profile_surplus_mw, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'PROFILE_SURPLUS_MW_{unit.duid}')
        penalty += (unit.profile_deficit_mw + unit.profile_surplus_mw) * cvp['Fast_Start_Inflexible_Profile'] * voll
        if unit.current_mode == 1:
            unit.fast_start_inflexible_constr = model.addConstr(unit.total_cleared - unit.profile_deficit_mw <= 0.000001, name=f'FAST_START_INFLEXIBLE_MODE1_{unit.duid}')
            model.addConstr(unit.profile_surplus_mw, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'PROFILE_SURPLUS_MW_{unit.duid}')
            if unit.total_cleared_record is not None and unit.total_cleared_record > 0.000001:
                logging.warning(f'{unit.dispatch_type} {unit.duid} avoid fast start inflexible profile mode 1')
        elif unit.current_mode == 2 and unit.energy.t2 != 0:
            unit.fast_start_inflexible_constr = model.addConstr(unit.total_cleared + unit.profile_surplus_mw - unit.profile_deficit_mw, sense=gurobipy.GRB.EQUAL, rhs=unit.current_mode_time*unit.energy.minimum_load/unit.energy.t2, name=f'FAST_START_INFLEXIBLE_MODE2_{unit.duid}')
            if unit.total_cleared_record is not None and abs(unit.total_cleared_record - unit.current_mode_time*unit.energy.minimum_load/unit.energy.t2) > 0.1:
                logging.warning(f'{unit.dispatch_type} {unit.duid} avoid fast start inflexible profile mode 2')
        elif unit.current_mode == 3:
            unit.fast_start_inflexible_constr = model.addConstr(unit.total_cleared + unit.profile_surplus_mw >= unit.energy.minimum_load, name=f'FAST_START_INFLEXIBLE_MODE3_{unit.duid}')
            model.addConstr(unit.profile_deficit_mw, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'PROFILE_DEFICIT_MW_{unit.duid}')
            if unit.total_cleared_record is not None and unit.total_cleared_record < unit.energy.minimum_load:
                logging.warning(f'{unit.dispatch_type} {unit.duid} avoid fast start inflexible profile mode 3')
        elif unit.current_mode == 4 and unit.energy.t4 != 0:
            unit.fast_start_inflexible_constr = model.addConstr(unit.total_cleared + unit.profile_surplus_mw >= ((unit.current_mode_time - unit.energy.t4) / unit.energy.t4) * unit.energy.minimum_load, name=f'FAST_START_INFLEXIBLE_MODE4_{unit.duid}')
            model.addConstr(unit.profile_deficit_mw, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'PROFILE_DEFICIT_MW_{unit.duid}')
            if unit.total_cleared_record is not None and unit.total_cleared_record < ((unit.current_mode_time - unit.energy.t4) / unit.energy.t4) * unit.energy.minimum_load:
                logging.warning(f'{unit.dispatch_type} {unit.duid} avoid fast start inflexible profile mode 4')
                logging.debug(f'total cleared {unit.total_cleared_record} current time {unit.current_mode_time} t4 {unit.energy.t4} min load {unit.energy.minimum_load}')
    return penalty


def add_unit_ramp_constr(model, intervals, unit, hard_flag, slack_variables, penalty, voll, cvp):
    # Unit Ramp Rate constraint (Raise)
    up_rate = unit.energy.roc_up if unit.ramp_up_rate is None else unit.ramp_up_rate / 60
    unit.surplus_ramp_rate = model.addVar(name=f'Surplus_Ramp_Rate_{unit.duid}')  # Item3
    slack_variables.add(f'Surplus_Ramp_Rate_{unit.duid}')
    if hard_flag:
        model.addConstr(unit.surplus_ramp_rate, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'SURPLUS_RAMP_RATE_{unit.duid}')
    penalty += unit.surplus_ramp_rate * cvp['Unit_Ramp_Rate'] * voll
    unit.ramp_up_rate_constr = model.addConstr(
        unit.total_cleared - unit.surplus_ramp_rate <= unit.initial_mw + intervals * up_rate, name=f'ROC_UP_{unit.duid}')
    if unit.total_cleared_record is not None and unit.total_cleared_record > unit.initial_mw + intervals * up_rate and abs(
            unit.total_cleared_record - unit.initial_mw - intervals * up_rate) > 1:
        logging.warning(f'{unit.dispatch_type} {unit.duid} above raise ramp rate constraint')

    # Unit Ramp Rate constraint (Down)
    down_rate = unit.energy.roc_down if unit.ramp_down_rate is None else unit.ramp_down_rate / 60
    unit.deficit_ramp_rate = model.addVar(name=f'Deficit_Ramp_Rate_{unit.duid}')  # Item3
    slack_variables.add(f'Deficit_Ramp_Rate_{unit.duid}')
    if hard_flag:
        model.addConstr(unit.deficit_ramp_rate, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'DEFICIT_RAMP_RATE_{unit.duid}')
    penalty += unit.deficit_ramp_rate * cvp['Unit_Ramp_Rate'] * voll
    unit.ramp_down_rate_constr = model.addConstr(
        unit.total_cleared + unit.deficit_ramp_rate >= unit.initial_mw - intervals * down_rate * 10,
        name=f'ROC_DOWN_{unit.duid}')
    if unit.total_cleared_record is not None and unit.total_cleared_record < unit.initial_mw - intervals * down_rate and abs(
            unit.total_cleared_record - unit.initial_mw + intervals * down_rate) > 1:
        logging.warning(f'{unit.dispatch_type} {unit.duid} below down ramp rate constraint')
        logging.debug(
            f'{unit.dispatch_type} {unit.duid} energy target {unit.total_cleared_record} initial {unit.initial_mw} rate {down_rate}')
    return penalty


def add_fixed_loading_constr(model, unit, hard_flag, slack_variables, penalty, voll, cvp):
    # Fixed loading constraint
    if unit.energy.fixed_load != 0:
        unit.deficit_fixed_loading = model.addVar(name=f'Deficit_Fixed_Loading_{unit.duid}')  # Item13
        slack_variables.add(f'Deficit_Fixed_Loading_{unit.duid}')
        unit.surplus_fixed_loading = model.addVar(name=f'Surplus_Fixed_Loading_{unit.duid}')  # Item13
        slack_variables.add(f'Deficit_Fixed_Loading_{unit.duid}')
        if hard_flag:
            model.addConstr(unit.deficit_fixed_loading, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'DEFICIT_FIXED_LOADING_{unit.duid}')
            model.addConstr(unit.surplus_fixed_loading, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'SURPLUS_FIXED_LOADING_{unit.duid}')
        penalty += (unit.deficit_fixed_loading + unit.surplus_fixed_loading) * cvp['Energy_Inflexible_Offer'] * voll
        model.addConstr(
            unit.total_cleared - unit.surplus_fixed_loading + unit.deficit_fixed_loading,
            sense=gurobipy.GRB.EQUAL, rhs=unit.energy.fixed_load, name=f'FIXED_LOAD_{unit.duid}')
        if unit.total_cleared_record is not None and unit.total_cleared_record != unit.energy.fixed_load:
            logging.warning(
                f'{unit.dispatch_type} {unit.duid} total cleared record {unit.total_cleared_record} not equal to fixed load {unit.energy.fixed_load}')
    return penalty


def add_cost(unit, regions, cost):
    # Cost of an unit
    unit.cost = sum([o * (p / unit.transmission_loss_factor) for o, p in zip(unit.offers, unit.energy.price_band)])
    if unit.dispatch_type == 'GENERATOR':
        # Add cost to objective
        cost += unit.cost
        # Add generation to region generation
        regions[unit.region_id].dispatchable_generation += unit.total_cleared
        regions[unit.region_id].dispatchable_generation_temp += unit.total_cleared_record
        regions[unit.region_id].available_generation += unit.energy.max_avail if unit.forecast_poe50 is None else unit.forecast_poe50
    elif unit.dispatch_type == 'LOAD':
        # Minus cost from objective
        cost -= unit.cost
        # Add load to region load
        regions[unit.region_id].dispatchable_load += unit.total_cleared
        regions[unit.region_id].dispatchable_load_temp += unit.total_cleared_record
        regions[unit.region_id].available_load += unit.energy.max_avail
    else:
        logging.error(f'{unit.duid} has no dispatch type.')
    return cost