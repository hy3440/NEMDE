import gurobipy
from helpers import condition1, condition2
import logging


def enable_fcas(fcas, unit, process, i):
    if fcas is None:
        return False
    fcas.flag = 0  # Not stranded, not trapped, not enabled (i.e. is unavailable).
    # For Dispatch and 1st interval of Predispatch and 5min Predispatch, regulating FCAS is enabled if AGC status is On
    if condition1(process, i):
        if fcas.bid_type == 'RAISEREG' or fcas.bid_type == 'LOWERREG':
            if unit.agc_status == 0:
                return False
    # The maximum availability offered for the service is greater than zero.
    if fcas.max_avail <= 0:
        return False
    # At least one of the offer price bands has a capacity greater than zero for the service
    if sum(fcas.band_avail) <= 0:
        return False
    # The energy availability is greater than or equal to the FCAS trapezium enablement minimum of the service
    if unit.energy is not None:
        if unit.energy.max_avail < fcas.enablement_min:
            return False
    # The FCAS trapezium enablement maximum of the service is greater than or equal to zero
    if fcas.enablement_max < 0:
        return False
    # The unit is initially operating between the FCAS trapezium enablement minimum and maximum of the service
    # "stranded outside the FCAS trapezium"
    if unit.initial_mw < fcas.enablement_min or unit.initial_mw > fcas.enablement_max:
        fcas.flag = 4  # Is stranded, not trapped, not enabled (i.e. stranded).
        return False
    fcas.enablement_status = 1
    fcas.flag = 1  # Not stranded, not trapped, is enabled (i.e. available).
    return True


def scale_fcas(unit, fcas, bid_type, process, interval, intervals):
    # Scale for AGC(for regulating services only)
    if bid_type == 'RAISEREG' or bid_type == 'LOWERREG':
        # Scale for AGC enablement limits (for dispatch and 1st interval of predispatch and 5min)
        if condition1(process, interval):
            agc_enablement_max = unit.raisereg_enablement_max if bid_type == 'RAISEREG' else unit.lowerreg_enablement_max
            agc_enablement_min = unit.raisereg_enablement_min if bid_type == 'RAISEREG' else unit.lowerreg_enablement_min
            if fcas.enablement_max > agc_enablement_max >= agc_enablement_min:
                fcas.high_breakpoint = fcas.high_breakpoint + agc_enablement_max - fcas.enablement_max
                fcas.enablement_max = agc_enablement_max
            if fcas.enablement_min < agc_enablement_min <= agc_enablement_max:
                fcas.low_breakpoint = fcas.low_breakpoint + agc_enablement_min - fcas.enablement_min
                fcas.enablement_min = agc_enablement_min
        # Scale for AGC ramp rates (for dispatch and 1st interval of 5min predispatch)
        if condition2(process, interval) and fcas.max_avail > unit.raisereg_availability:
            if (unit.dispatch_type == 'GENERATOR' and bid_type == 'RAISEREG') or (
                    unit.dispatch_type == 'LOAD' and bid_type == 'LOWERREG'):
                rate = unit.energy.roc_up if unit.ramp_up_rate is None else unit.ramp_up_rate / 60
            elif (unit.dispatch_type == 'GENERATOR' and bid_type == 'LOWERREG') or (
                    unit.dispatch_type == 'LOAD' and bid_type == 'RAISEREG'):
                rate = unit.energy.roc_down if unit.ramp_down_rate is None else unit.ramp_down_rate / 60
            agc_ramping_capability = rate * intervals
            fcas.low_breakpoint = fcas.low_breakpoint - (fcas.max_avail - agc_ramping_capability) * (
                    fcas.low_breakpoint - fcas.enablement_min) / fcas.max_avail
            fcas.high_breakpoint = fcas.high_breakpoint + (fcas.max_avail - agc_ramping_capability) * (
                    fcas.enablement_max - fcas.high_breakpoint) / fcas.max_avail
            fcas.max_avail = agc_ramping_capability
    # Scale for UIGF (for both regulating and contingency services)
    if unit.forecast_poe50 is not None:
        fcas.high_breakpoint = fcas.high_breakpoint - (
                fcas.enablement_max - min(fcas.enablement_max, unit.forecast_poe50))
        fcas.enablement_max = min(fcas.enablement_max, unit.forecast_poe50)
    # if unit.duid == 'HDWF2':
    #     print(fcas.bid_type)
    #     print(fcas.max_avail)
    #     print(fcas.enablement_min)
    #     print(fcas.enablement_max)
    #     print(fcas.low_breakpoint)
    #     print(fcas.high_breakpoint)


def preprocess_fcas(model, unit, process, interval, intervals):
    # Preprocess
    for bid_type, fcas in unit.fcas_bids.items():
        scale_fcas(unit, fcas, bid_type, process, interval, intervals)
        # Check pre-conditions for enabling FCAS
        if enable_fcas(fcas, unit, process, interval):
            fcas.lower_slope_coeff = (fcas.low_breakpoint - fcas.enablement_min) / fcas.max_avail
            fcas.upper_slope_coeff = (fcas.enablement_max - fcas.high_breakpoint) / fcas.max_avail
        # Verify flag
        if fcas.flag == 3:
            logging.debug(f'{unit.duid} {fcas.bid_type} flag is {fcas.flag}')
        if unit.flags[bid_type] != fcas.flag:
            logging.warning(
                f'{unit.dispatch_type} {unit.duid} {bid_type} FCAS flag record {unit.flags[bid_type]} but {fcas.flag}')


def add_fcas_offers(model, unit, fcas, bid_type):
    # FCAS offers
    for no, avail in enumerate(fcas.band_avail):
        bid_offer = model.addVar(name=f'{bid_type}_Avail{no}_{unit.duid}')
        fcas.offers.append(bid_offer)
        model.addConstr(bid_offer <= avail, name=f'{bid_type}_AVAIL{no}_{unit.duid}')
    if unit.target_record and unit.target_record[bid_type] > sum(fcas.band_avail):
        logging.warning(
            f'{unit.dispatch_type} {unit.duid} {bid_type} {unit.target_record[bid_type]} above sum of avail {sum(fcas.band_avail)}')


def add_fcas_max_avail_constr(model, unit, fcas, bid_type, hard_flag, slack_variables, penalty, voll, cvp):
    # FCAS MaxAvail constraint
    fcas.max_avail_deficit = model.addVar(
        name=f'FCAS_Max_Avail_Deficit_{bid_type}_{unit.duid}')  # Item18
    slack_variables.add(f'FCAS_Max_Avail_Deficit_{bid_type}_{unit.duid}')
    if hard_flag:
        model.addConstr(fcas.max_avail_deficit, sense=gurobipy.GRB.EQUAL, rhs=0,
                        name=f'FCAS_MAX_AVAIL_DEFICIT_{bid_type}_{unit.duid}')
    penalty += fcas.max_avail_deficit * cvp['FCAS_MaxAvail'] * voll
    fcas.max_avail_constr = model.addConstr(fcas.value - fcas.max_avail_deficit <= fcas.max_avail,
                                            name=f'FCAS_MAX_AVAIL_{bid_type}_{unit.duid}')
    fcas.max_avail_constr = model.addConstr(fcas.value <= fcas.max_avail, name=f'{fcas.bid_type}_MAX_AVAIL_{unit.duid}')
    if unit.target_record and unit.target_record[bid_type] > fcas.max_avail:
        logging.warning(
            f'{unit.dispatch_type} {unit.duid} {bid_type} {unit.target_record[bid_type]} above max avail {fcas.max_avail} constraint')
    return penalty


def add_fcas_to_region_sum(region, bid_type, value, record):
    region.fcas_local_dispatch_temp[bid_type] += value
    region.fcas_local_dispatch_record_temp[bid_type] += record


def process_fcas_bid(model, unit, fcas, bid_type, hard_flag, slack_variables, penalty,
                                        voll, cvp, cost, regions):
    fcas.value = model.addVar(name=f'{fcas.bid_type}_Target_{unit.duid}')
    # FCAS offers
    add_fcas_offers(model, unit, fcas, bid_type)
    # FCAS total band constraints
    model.addConstr(fcas.value, sense=gurobipy.GRB.EQUAL, rhs=sum(fcas.offers),
                    name=f'{bid_type}_SUM_{unit.duid}')
    # Add cost to objective
    fcas.cost = sum([o * p for o, p in zip(fcas.offers, fcas.price_band)])
    cost += fcas.cost
    # FCAS MaxAvail constraint
    penalty = add_fcas_max_avail_constr(model, unit, fcas, bid_type, hard_flag, slack_variables, penalty,
                                        voll, cvp)
    # Add FCAS target to region sum
    add_fcas_to_region_sum(regions[unit.region_id], bid_type, fcas.value,
                           unit.target_record[bid_type])
    return cost, penalty


def add_enablement_min_constr(model, unit, fcas, bid_type, hard_flag, slack_variables, penalty, voll, cvp):
    # FCAS EnablementMin constraint
    unit.lower_surplus = model.addVar(name=f'Lower_Surplus_{unit.duid}_{bid_type}')  # Item22
    return penalty


def add_enablement_max_constr(model, unit, fcas, bid_type, hard_flag, slack_variables, penalty, voll, cvp):
    return penalty


def add_joint_ramping_constr(model, intervals, unit, fcas, bid_type, hard_flag, slack_variables, penalty, voll, cvp):
    # Joint ramping constraint
    if (unit.dispatch_type == 'GENERATOR' and bid_type == 'RAISEREG') or (unit.dispatch_type == 'LOAD' and bid_type == 'LOWERREG'):
        up_rate = unit.energy.roc_up if unit.ramp_up_rate is None else unit.ramp_up_rate / 60
        if up_rate > 0:
            unit.joint_ramp_deficit = model.addVar(name=f'Joint_Ramp_Deficit_{unit.duid}')  # Item19
            slack_variables.add(f'Joint_Ramp_Deficit_{unit.duid}')
            if hard_flag:
                model.addConstr(unit.joint_ramp_deficit, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'JOINT_RAMP_DEFICIT_{unit.duid}')
            penalty += unit.joint_ramp_deficit * cvp['FCAS_Joint_Ramping'] * voll
            model.addConstr(unit.total_cleared + fcas.value - unit.joint_ramp_deficit <= unit.initial_mw + intervals * up_rate, name=f'JOINT_RAMPING_{unit.duid}')
            if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + \
                    unit.target_record[bid_type] > unit.initial_mw + intervals * up_rate:
                if abs(unit.total_cleared_record + unit.target_record[
                    bid_type] - unit.initial_mw - intervals * up_rate) > 1:
                    logging.warning(f'{unit.dispatch_type} {unit.duid} above joint ramping constraint')
                    logging.debug(
                        f'energy {unit.total_cleared_record} {bid_type} {unit.target_record[bid_type]} initial {unit.initial_mw} up rate {up_rate}')

    elif (unit.dispatch_type == 'GENERATOR' and bid_type == 'LOWERREG') or (unit.dispatch_type == 'LOAD' and bid_type == 'RAISEREG'):
        down_rate = unit.energy.roc_down if unit.ramp_down_rate is None else unit.ramp_down_rate / 60
        if down_rate > 0:
            unit.joint_ramp_surplus = model.addVar(name=f'Joint_Ramp_Surplus_{unit.duid}')  # Item19
            slack_variables.add(f'Joint_Ramp_Surplus_{unit.duid}')
            if hard_flag:
                model.addConstr(unit.joint_ramp_surplus, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'JOINT_RAMP_SURPLUS_{unit.duid}')
            penalty += unit.joint_ramp_surplus * cvp['FCAS_Joint_Ramping'] * voll
            model.addConstr(unit.total_cleared - fcas.value + unit.joint_ramp_surplus >= unit.initial_mw - intervals * down_rate, name=f'JOINT_RAMPING_{unit.duid}')
            if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - \
                    unit.target_record[bid_type] < unit.initial_mw - intervals * down_rate:
                if abs(unit.total_cleared_record - unit.target_record[
                    bid_type] - unit.initial_mw + intervals * down_rate) > 1:
                    logging.warning(f'{unit.dispatch_type} {unit.duid} below joint ramping constraint')
                    logging.debug(
                        f'energy {unit.total_cleared_record} {bid_type} {unit.target_record[bid_type]} initial {unit.initial_mw} down rate {down_rate}')
    return penalty


def add_energy_and_fcas_capacity_constr(model, unit, fcas, bid_type):
    # Energy and regulating FCAS capacity constraint
    model.addConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value <= fcas.enablement_max, name=f'ENERGY_AND_FCAS_CAPACITY_UPPER_{bid_type}_{unit.duid}')
    if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * \
            unit.target_record[bid_type] > fcas.enablement_max:
        if abs(unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[
            bid_type] - fcas.enablement_max) > 1:
            logging.warning(
                f'{unit.dispatch_type} {unit.duid} {bid_type} above energy and regulating FCAS capacity constraint')
            logging.debug(
                f'energy {unit.total_cleared_record} upper slop {fcas.upper_slope_coeff} {bid_type} {unit.target_record[bid_type]} enablement max {fcas.enablement_max}')
    model.addConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value >= fcas.enablement_min, name=f'ENERGY_AND_FCAS_CAPACITY_LOWER_{bid_type}_{unit.duid}')
    if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * \
            unit.target_record[bid_type] < fcas.enablement_min:
        if (unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[
            bid_type] - fcas.enablement_min) > 1:
            logging.warning(
                f'{unit.dispatch_type} {unit.duid} {bid_type} below energy and regulating FCAS capacity constraint')
            logging.debug(
                f'energy {unit.total_cleared_record} lower slop {fcas.lower_slope_coeff} {bid_type} {unit.target_record[bid_type]} enablement min {fcas.enablement_min}')


def add_joint_capacity_constr(model, unit, fcas, bid_type, hard_flag, slack_variables, penalty, voll, cvp):
    # Joint capacity constraint
    if (unit.dispatch_type == 'GENERATOR' and bid_type == 'RAISE5MIN' and 'RAISEREG' in unit.fcas_bids) or (unit.dispatch_type == 'LOAD' and bid_type == 'LOWER5MIN' and 'LOWERREG' in unit.fcas_bids):
        reg_type = 'RAISEREG' if unit.dispatch_type == 'GENERATOR' else 'LOWERREG'
        reg = unit.fcas_bids[reg_type]
        unit.joint_upper_deficit = model.addVar(name=f'Joint_Upper_Deficit_{unit.duid}')  # Item19?
        slack_variables.add(f'Joint_Upper_Deficit_{unit.duid}')
        if hard_flag:
            model.addConstr(unit.joint_upper_deficit, sense=gurobipy.GRB.EQUAL, rhs=0,
                            name=f'JOINT_UPPER_DEFICIT_{unit.duid}')
        penalty += unit.joint_upper_deficit * cvp['FCAS_Joint_Ramping'] * voll
        model.addConstr(
            unit.total_cleared + fcas.upper_slope_coeff * fcas.value + reg.enablement_status * reg.upper_slope_coeff * reg.value - unit.joint_upper_deficit <= max(fcas.enablement_max, reg.enablement_max), name=f'UPPER_JOINT_CAPACITY_{bid_type}_{unit.duid}')
        if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * \
                unit.target_record[bid_type] + (unit.flags[reg_type] % 2) * unit.fcas_bids[reg_type].upper_slope_coeff * \
                unit.target_record[reg_type] > max(fcas.enablement_max, reg.enablement_max):
            if abs(unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[
                bid_type] + (unit.flags[reg_type] % 2) * unit.target_record[
                       reg_type] * unit.fcas_bids[reg_type].upper_slope_coeff - max(fcas.enablement_max, reg.enablement_max)) > 0.01:
                logging.warning(
                    f'{unit.dispatch_type} {unit.duid} {bid_type} above joint capacity constraint')

    if (unit.dispatch_type == 'GENERATOR' and bid_type == 'LOWER5MIN' and 'LOWERREG' in unit.fcas_bids) or (unit.dispatch_type == 'LOAD' and bid_type == 'RAISE5MIN' and 'RAISEREG' in unit.fcas_bids):
        reg_type = 'LOWERREG' if unit.dispatch_type == 'GENERATOR' else 'RAISEREG'
        reg = unit.fcas_bids[reg_type]
        unit.joint_lower_surplus = model.addVar(name=f'Joint_Lower_Surplus_{unit.duid}')  # Item19?
        slack_variables.add(f'Joint_Lower_surplus_{unit.duid}')
        if hard_flag:
            model.addConstr(unit.joint_lower_surplus, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'JOINT_LOWER_SURPLUS_{unit.duid}')
        penalty += unit.joint_lower_surplus * cvp['FCAS_Joint_Ramping'] * voll
        model.addConstr(
            unit.total_cleared - fcas.lower_slope_coeff * fcas.value - reg.enablement_status * reg.lower_slope_coeff * reg.value + unit.joint_lower_surplus >= min(fcas.enablement_min, reg.enablement_min), name=f'LOWER_JOINT_CAPACITY_{bid_type}_{unit.duid}')
        if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * \
                unit.target_record[bid_type] - (unit.flags[reg_type] % 2) * \
                unit.target_record[reg_type] < min(fcas.enablement_min, reg.enablement_min):
            if abs(unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[
                bid_type] - (unit.flags[reg_type] % 2) * unit.target_record[
                       reg_type] - min(fcas.enablement_min, reg.enablement_min)) > 0.01:
                logging.warning(
                    f'{unit.dispatch_type} {unit.duid} {bid_type} below joint capacity constraint')
                logging.debug(
                    f"energy {unit.total_cleared_record} lower slope {fcas.lower_slope_coeff} target {unit.target_record[bid_type]} status {unit.flags[reg_type] % 2} {reg_type} {unit.target_record[reg_type]} enablemin {fcas.enablement_min}")
    return penalty