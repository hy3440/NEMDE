import csv
import default
import gurobipy as gp
from helpers import condition1, condition2
import logging
import offer
import preprocess

intervention = '0'


class Constraint:
    """Generic constraint class.

    Attributes:
        gen_con_id (str): Unique ID for the constraint
        version_no (int): Version with respect to the effective date
        constraint_type (str): The logical operator (=, >=, <=)
        constraint_value (float): the RHS value used if there is no dynamic RHS defined in GenericConstraintRHS
        generic_constraint_weight (float): The constraint violation penalty factor
        dispatch (bool): Flag: constraint RHS used for Dispatch? 1-used, 0-not used
        predispatch (bool): Flag to indicate if the constraint RHS is to be used for PreDispatch, 1-used, 0-not used
        stpasa (bool): Flag to indicate if the constraint RHS is to be used for ST PASA, 1-used, 0-not used
        mtpasa (bool): Flag to indicate if the constraint RHS is to be used for MT PASA, 1-used, 0-not used
        limit_type (str): The limit type of the constraint e.g. Transient Stability, Voltage Stability
        force_scada (int): Flags Constraints for which NEMDE must use "InitialMW" values instead of "WhatOfInitialMW" for Intervention Pricing runs
    """
    def __init__(self, row, rhs=None):
        if rhs is None:
            # Generic constraint data
            self.gen_con_id = row[6]
            self.update(row)
        else:
            self.gen_con_id = row
        # Custom attribute
        self.bind_flag = False  # True if constr is recorded as binding
        self.fcas_flag = False  # True if constr contains FCAS factor
        # Generic Constraint Data
        self.constraint_type = None
        self.constraint_value = None
        self.generic_constraint_weight = None
        self.last_changed = None
        self.dispatch = None
        self.predispatch = None
        self.stpasa = None
        self.mtpasa = None
        self.limit_type = None
        self.force_scada = None
        # Dispatch constraint
        self.rhs = rhs
        self.marginal_value = None
        self.violation_degree = None
        self.lhs = None
        self.violation_price = None
        # SPD connection point constraint
        self.connection_point_flag = True  # True if connection point has corresponding unit else False
        self.connection_point_lhs = 0.0
        self.connection_point_lhs_record = 0.0
        self.connection_points = set()
        self.connection_point_last_changed = None
        # SPD interconnector constraint
        self.interconnector_lhs = 0.0
        self.interconnector_lhs_record = 0.0
        self.interconnectors = set()
        self.interconnector_last_changed = None
        # SPD region constraint
        self.region_lhs = 0.0
        self.region_lhs_record = 0.0
        self.regions = set()
        self.region_last_changed = None

    def update(self, row):
        self.constraint_type = row[7]
        self.constraint_value = float(row[8])
        self.generic_constraint_weight = float(row[11])
        self.last_changed = default.extract_datetime(row[15])
        self.dispatch = row[16] == '1'
        self.predispatch = row[17] == '1'
        self.stpasa = row[18] == '1'
        self.mtpasa = row[19] == '1'
        self.limit_type = row[22]
        self.force_scada = int(row[29])


def init_constraints(t):
    """ Initiate generic constraints.

    Args:
        t (datetime.datetime): Current datetime

    Returns:
        A dictionary of constraints.

    """
    constraints = {}
    constr_dir = preprocess.download_dvd_data('GENCONDATA', t)
    # logging.info('Read generic constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and t >= default.extract_datetime(row[4]):
                gen_con_id = row[6]
                constr = constraints.get(gen_con_id)
                if not constr:
                    constraints[gen_con_id] = Constraint(row)
                elif constr.last_changed < default.extract_datetime(row[15]):
                    constr.update(row)
        return constraints


def add_spd_connection_point_constraint(t, constraints, units, connection_points, fcas_flag):
    """ Add SPD Connection Point part of Generic Constraint LHS.

    Args:
        t (datetime.datetime): Current datetime
        constraints (dict): The dictionary of generic constraints
        units (dict): The dictionary of units
        connection_points (dict): The dictionary of connection points
        fcas_flag (bool): Consider FCAS or not

    Returns:
        None
    """
    constr_dir = preprocess.download_dvd_data('SPDCONNECTIONPOINTCONSTRAINT', t)
    # logging.info('Read SPD connection point constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        uncovered = set()
        for row in reader:
            if row[0] == 'D' and t >= default.extract_datetime(row[5]):
                constr = constraints.get(row[7])  # 7: Gen con ID
                if constr is None:
                    logging.error(f'Constraint {row[7]} for connection point was not included.')
                last = constr.connection_point_last_changed
                current = default.extract_datetime(row[9])
                if last is None or last < current:  # 9: Last changed
                    if row[4] not in connection_points:
                        constr.connection_point_flag = False
                        if row[4] not in uncovered:  # 4: Connection point ID
                            uncovered.add(row[4])
                            logging.error(f'Connection point {row[4]} for Constraint {row[7]} has no corresponding unit.')
                    else:
                        constr.connection_points.clear()
                        constr.connection_points.add(f'{connection_points[row[4]]} {row[10]} {row[8]}')
                        if row[10] == 'ENERGY':  # 10: Bid type
                            constr.connection_point_lhs = float(row[8]) * units[connection_points[row[4]]].total_cleared  # 8: Factor
                            constr.connection_point_lhs_record = float(row[8]) * units[connection_points[row[4]]].total_cleared_record
                            constr.connection_point_last_changed = current
                        elif fcas_flag:
                            constr.connection_point_lhs = float(row[8]) * units[connection_points[row[4]]].fcas_bids[row[10]].value
                            constr.connection_point_lhs_record = float(row[8]) * units[connection_points[row[4]]].target_record[row[10]]
                            constr.connection_point_last_changed = current
                elif last == current:
                    if row[4] not in connection_points:
                        constr.connection_point_flag = False
                        if row[4] not in uncovered:
                            uncovered.add(row[4])
                            logging.error(f'Connection point {row[4]} for Constraint {row[7]} has no corresponding unit.')
                    else:
                        constr.connection_points.add(f'{connection_points[row[4]]} {row[10]} {row[8]}')
                        if row[10] == 'ENERGY':
                            constr.connection_point_lhs += float(row[8]) * units[connection_points[row[4]]].total_cleared
                            constr.connection_point_lhs_record += float(row[8]) * units[connection_points[row[4]]].total_cleared_record
                        elif fcas_flag:
                            constr.connection_point_lhs += float(row[8]) * units[connection_points[row[4]]].fcas_bids[row[10]].value
                            constr.connection_point_lhs_record += float(row[8]) * units[connection_points[row[4]]].target_record[row[10]]


def add_spd_interconnector_constraint(t, constraints, interconnectors):
    """ Add SPD Interconnector part of Generic Constraint LHS.

    Args:
        t (datetime.datetime): Current datetime
        constraints (dict): The dictionary of generic constraints
        interconnectors (dict): The dictionary of interconnectors

    Returns:
        None
    """
    constr_dir = preprocess.download_dvd_data('SPDINTERCONNECTORCONSTRAINT', t)
    # logging.info('Read SPD interconnector constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and t >= default.extract_datetime(row[5]):
                constr = constraints[row[7]]  # 7: Gen con ID
                current = default.extract_datetime(row[9])
                last = constr.interconnector_last_changed
                if last is None or last < current:  # 9: Last changed
                    constr.interconnector_lhs = float(row[8]) * interconnectors[row[4]].mw_flow  # 8: Factor; 4: Interconnector ID
                    constr.interconnector_lhs_record = float(row[8]) * interconnectors[row[4]].mw_flow_record
                    constr.interconnectors.clear()
                    constr.interconnectors.add(f'{row[4]} {row[8]}')
                    constr.interconnector_last_changed = current
                elif last == current:
                    constr.interconnector_lhs += float(row[8]) * interconnectors[row[4]].mw_flow
                    constr.interconnector_lhs_record += float(row[8]) * interconnectors[row[4]].mw_flow_record
                    constr.interconnectors.add(f'{row[4]} {row[8]}')


def add_spd_region_constraint(t, constraints, regions):
    """ Add SPD Region part of Generic Constraint LHS.

    Args:
        t (datetime.datetime): Current dateime
        constraints (dict): The dictionary of generic constraints
        regions (dict): The dictionary of regions

    Returns:
        None
    """
    constr_dir = preprocess.download_dvd_data('SPDREGIONCONSTRAINT', t)
    # logging.info('Read SPD region constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and t >= default.extract_datetime(row[5]):  # 5: Effective date
                constr = constraints[row[7]]  # 7: Gen con ID
                last = constr.region_last_changed
                current = default.extract_datetime(row[9])
                if last is None or last < current:  # 9: Last changed
                    constr.region_lhs = float(row[8]) * regions[row[4]].fcas_local_dispatch[row[10]]  # 8: Factor; 4: Region ID; 10: Bid type
                    constr.region_lhs_record = float(row[8]) * regions[row[4]].fcas_local_dispatch_record[row[10]]
                    constr.regions.clear()
                    constr.regions.add(f'{row[4]} {row[10]} {row[8]}')
                    constr.region_last_changed = current
                elif last == current:
                    constr.region_lhs += float(row[8]) * regions[row[4]].fcas_local_dispatch[row[10]]
                    constr.region_lhs_record += float(row[8]) * regions[row[4]].fcas_local_dispatch_record[row[10]]
                    constr.regions.add(f'{row[4]} {row[10]} {row[8]}')


def add_dispatch_constraint(t, constraints, debug_flag):
    """ Add Generic Constraint RHS value for 'dispatch' process.

    Args:
        t (datetime.datetime): Current dateime
        constraints (dict): The dictionary of generic constraints

    Returns:
        None
    """
    # constr_dir = preprocess.download_dvd_data('DISPATCHCONSTRAINT', t)
    constr_dir = preprocess.download_dispatch_summary(t)
    # logging.info('Read dispatch constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'CONSTRAINT' and row[8] == intervention:
                constr = constraints.get(row[6])
                if constr:
                    if constr.rhs is not None:
                        csv_rhs = float(row[9])
                        if abs(constr.rhs - csv_rhs) > 1:
                            print(f'Constraint {row[6]} rhs {constr.rhs} but csv record {csv_rhs}')
                        constr.rhs = float(row[9])
                    constr.marginal_value = float(row[10])
                    constr.violation_degree = float(row[11])
                    constr.lhs = float(row[16])
                    constr.bind_flag = True
                elif debug_flag:
                    logging.error(f'Constraint {row[6]} was not included')


def add_predispatch_constraint(t, start, constraints, debug_flag):
    """ Add Generic Constraint RHS value for 'predispatch' process.

    Args:
        t (datetime.datetime): Current dateime
        start (datetime.datetime): Start datetime
        constraints (dict): The dictionary of generic constraints

    Returns:
        None
    """
    constr_dir = preprocess.download_predispatch(start)
    # logging.info('Read pre-dispatch constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'CONSTRAINT_SOLUTION' and default.extract_datetime(row[13]) == t and row[8] == '0':  # 8: Intervention flag; 13: Interval datetime
                constr = constraints.get(row[6])  # 6: Constraint ID
                if constr:
                    constr.rhs = float(row[9])
                    constr.marginal_value = float(row[10])
                    constr.voilation_degree = float(row[11])
                    constr.lhs = float(row[17])
                    constr.bind_flag = True
                elif debug_flag:
                    logging.error(f'Constraint {row[6]} was not included')


def add_p5min_constraint(t, start, constraints, debug_flag):
    """ Add Generic Constraint RHS value for 'p5min' process.

    Args:
        t (datetime.datetime): Current dateime
        start (datetime.datetime): Start datetime
        constraints (dict): The dictionary of generic constraints

    Returns:
        None
    """
    constr_dir = preprocess.download_5min_predispatch(start)
    # logging.info('Read 5min pre-dispatch constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'CONSTRAINTSOLUTION' and default.extract_datetime(row[6]) == t and row[5] == '0':  # 5: Intervention flag; 6: Interval datetime
                constr = constraints.get(row[7])  # 7: Constraint ID
                if constr:
                    constr.rhs = float(row[8])
                    constr.marginal_value = float(row[9])
                    constr.voilation_degree = float(row[10])
                    constr.lhs = float(row[15])
                    constr.bind_flag = True
                elif debug_flag:
                    logging.error(f'Constraint {row[7]} was not included')


def get_constraints(process, t, units, connection_points, interconnectors, regions, start, fcas_flag):
    """ Get a dictionary of generic constraints.

    Args:
        process (str): 'dispatch', 'predispatch', or 'p5min'
        t (datetime.datetime): Current datetime
        units (dict): The dictionary of units
        connection_points (dict): The dictionary of connection points
        interconnectors (dict): The dictionary of interconnectors
        regions (dict): The dictionary of regions
        start (datetime.datetime): Start datetime
        fcas_flag (bool): Consider FCAS or not

    Returns:
        A dictionary of generic constraints.
    """
    constraints = init_constraints(t)
    if process == 'dispatch':
        add_dispatch_constraint(t, constraints)
    elif process == 'predispatch':
        add_predispatch_constraint(t, start, constraints)
    elif process == 'p5min':
        add_p5min_constraint(t, start, constraints)
    add_spd_connection_point_constraint(t, constraints, units, connection_points, fcas_flag)
    add_spd_interconnector_constraint(t, constraints, interconnectors)
    if fcas_flag:
        add_spd_region_constraint(t, constraints, regions)
    return constraints


def add_max_avail_constr(model, unit, prob_id, debug_flag, penalty, cvp):
    """ Unit MaxAvail constraint.

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    if unit.total_cleared_record is None or unit.total_cleared_record <= unit.energy.max_avail:
        unit.deficit_trader_energy_capacity = model.addVar(name=f'Deficit_Trader_Energy_Capacity_{unit.duid}_{prob_id}')  # Item14
        penalty += unit.deficit_trader_energy_capacity * cvp['CapacityPrice']
        unit.max_avail_constr = model.addLConstr(unit.total_cleared - unit.deficit_trader_energy_capacity <= unit.energy.max_avail, name=f'MAX_AVAIL_{unit.duid}_{prob_id}')
    elif debug_flag:
        logging.warning(f'{unit.dispatch_type} {unit.duid} total cleared record {unit.total_cleared_record} above max avail {unit.energy.max_avail} (total band {sum(unit.energy.band_avail)})')
    return penalty


def add_daily_energy_constr(model, unit, prob_id, debug_flag, penalty, cvp):
    """ Daily Energy constraint.

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    unit.defict_energy = model.addVar(name=f'Deficit_Energy_{unit.duid}_{prob_id}')  # Item14
    penalty += unit.defict_energy * cvp['CapacityPrice']
    unit.daily_energy_constr = model.addLConstr(unit.total_cleared / 2.0 + unit.energy.daily_energy - unit.defict_energy <= unit.energy.daily_energy_limit, name=f'DAILY_ENERGY_{unit.duid}_{prob_id}')
    if debug_flag:
        if unit.total_cleared_record is not None and unit.total_cleared_record / 2.0 + unit.energy.daily_energy_record > unit.energy.daily_energy_limit:
            logging.warning(f'{unit.dispatch_type} {unit.duid} total cleared record above daily energy limit')
            logging.debug(f'record {unit.total_cleared_record} / 2.0 + daily {unit.energy.daily_energy_record} > limit {unit.energy.daily_energy_limit}')
    return penalty


def add_total_band_constr(model, unit, prob_id, debug_flag, penalty, cvp):
    """ Total Band MW Offer constraint.

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    unit.deficit_offer_mw = model.addVar(name=f'Deficit_Offer_MW_{unit.duid}_{prob_id}')  # Item8
    penalty += unit.deficit_offer_mw * cvp['OfferPrice']
    unit.total_band_mw_offer_constr = model.addLConstr(unit.total_cleared + unit.deficit_offer_mw,
                                                      sense=gp.GRB.EQUAL,
                                                      rhs=sum(unit.offers),
                                                      name=f'TOTAL_BAND_MW_OFFER_{unit.duid}_{prob_id}')
    return penalty


def add_uigf_constr(model, unit, prob_id, debug_flag, penalty, cvp):
    """ Unconstrained Intermittent Generation Forecasts (UIGF) for Dispatch (See AEMO2019Dispatch).

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    if unit.forecast_priority is not None and unit.forecast_poe50 is None:
        logging.error(f'Generator {unit.duid} forecast priority is but has no forecast POE50')
    elif unit.forecast_poe50 is not None and unit.total_cleared_record <= unit.forecast_poe50:
        unit.uigf_surplus = model.addVar(name=f'UIGF_Surplus_{unit.duid}_{prob_id}')  # Item12
        penalty += unit.uigf_surplus * cvp['UIGFSurplusPrice']
        model.addLConstr(unit.total_cleared - unit.uigf_surplus <= unit.forecast_poe50, name=f'UIGF_{unit.duid}_{prob_id}')
        if debug_flag:
            if unit.total_cleared_record is not None and unit.total_cleared_record > unit.forecast_poe50 and abs(unit.total_cleared_record - unit.forecast_poe50) > 0.1:
                logging.warning(f'{unit.dispatch_type} {unit.duid} total cleared record {unit.total_cleared_record} above UIGF forecast {unit.forecast_poe50}')
    return penalty


def add_fast_start_inflexibility_profile_constr(model, unit, prob_id, debug_flag, penalty, cvp):
    """ Fast Start Inflexible Profile constraint (See AEMO2014Fast).

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    if unit.dispatch_mode > 0:
        unit.profile_deficit_mw = model.addVar(name=f'Profile_Deficit_MW_{unit.duid}_{prob_id}')  # Item10
        unit.profile_surplus_mw = model.addVar(name=f'Profile_Surplus_MW_{unit.duid}_{prob_id}')  # Item10
        penalty += (unit.profile_deficit_mw + unit.profile_surplus_mw) * cvp['FastStartPrice']
        if unit.current_mode == 1:
            unit.fast_start_inflexible_constr = model.addLConstr(unit.total_cleared - unit.profile_deficit_mw <= 0.000001, name=f'FAST_START_INFLEXIBLE_MODE1_{unit.duid}_{prob_id}')
            model.addLConstr(unit.profile_surplus_mw, sense=gp.GRB.EQUAL, rhs=0, name=f'PROFILE_SURPLUS_MW_{unit.duid}_{prob_id}')
            if debug_flag:
                if unit.total_cleared_record is not None and unit.total_cleared_record > 0.000001:
                    logging.warning(f'{unit.dispatch_type} {unit.duid} avoid fast start inflexible profile mode 1')
        elif unit.current_mode == 2 and unit.energy.t2 != 0:
            unit.fast_start_inflexible_constr = model.addLConstr(unit.total_cleared + unit.profile_surplus_mw - unit.profile_deficit_mw, sense=gp.GRB.EQUAL, rhs=unit.current_mode_time*unit.energy.minimum_load/unit.energy.t2, name=f'FAST_START_INFLEXIBLE_MODE2_{unit.duid}_{prob_id}')
            if debug_flag:
                if unit.total_cleared_record is not None and abs(unit.total_cleared_record - unit.current_mode_time*unit.energy.minimum_load/unit.energy.t2) > 0.1:
                    logging.warning(f'{unit.dispatch_type} {unit.duid} avoid fast start inflexible profile mode 2')
        elif unit.current_mode == 3:
            unit.fast_start_inflexible_constr = model.addLConstr(unit.total_cleared + unit.profile_surplus_mw >= unit.energy.minimum_load, name=f'FAST_START_INFLEXIBLE_MODE3_{unit.duid}_{prob_id}')
            model.addLConstr(unit.profile_deficit_mw, sense=gp.GRB.EQUAL, rhs=0, name=f'PROFILE_DEFICIT_MW_{unit.duid}_{prob_id}')
            if debug_flag:
                if unit.total_cleared_record is not None and unit.total_cleared_record < unit.energy.minimum_load:
                    logging.warning(f'{unit.dispatch_type} {unit.duid} avoid fast start inflexible profile mode 3')
        elif unit.current_mode == 4 and unit.energy.t4 != 0:
            unit.fast_start_inflexible_constr = model.addLConstr(unit.total_cleared + unit.profile_surplus_mw >= ((unit.energy.t4 - unit.current_mode_time) / unit.energy.t4) * unit.energy.minimum_load, name=f'FAST_START_INFLEXIBLE_MODE4_{unit.duid}_{prob_id}')
            model.addLConstr(unit.profile_deficit_mw, sense=gp.GRB.EQUAL, rhs=0, name=f'PROFILE_DEFICIT_MW_{unit.duid}_{prob_id}')
            if debug_flag:
                if unit.total_cleared_record is not None and unit.total_cleared_record < ((unit.energy.t4 - unit.current_mode_time) / unit.energy.t4) * unit.energy.minimum_load:
                    logging.warning(f'{unit.dispatch_type} {unit.duid} avoid fast start inflexible profile mode 4')
                    logging.debug(f'total cleared {unit.total_cleared_record} current time {unit.current_mode_time} t4 {unit.energy.t4} min load {unit.energy.minimum_load}')
    return penalty


def add_unit_ramp_constr(process, model, intervals, unit, prob_id, debug_flag, penalty, cvp):
    """ Unit Ramp Rate Constraint.

    Args:
        process (str): 'dispatch', 'predispatch', or 'p5min'
        model (gp.Model): The optimisation model
        intervals (int): number of minutes per interval (5 or 30)
        unit (offer.Unit): The unit
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    # Note: In Dispatch, the more restrictive of the telemetered ramp rates and the ramp rates submitted in energy
    # offers are used to determine the effective energy ramp rates applied to the calculation of unit energy dispatch.
    # In Pre-dispatch, only the offered ramp rates are used. (See Paper AEMO2021Factors Section 7.2.4.1)

    # Ignore battery's ramp rate constraints
    if unit.ramp_up_rate is None and unit.energy.roc_up is None:
        return penalty

    # Unit Ramp Rate constraint (Raise)
    # up_rate = unit.energy.roc_up if unit.ramp_up_rate is None or process == 'predispatch' else unit.ramp_up_rate / 60
    up_rate = unit.energy.roc_up if unit.ramp_up_rate is None else unit.ramp_up_rate / 60
    unit.surplus_ramp_rate = model.addVar(name=f'Surplus_Ramp_Rate_{unit.duid}_{prob_id}')  # Item3
    penalty += unit.surplus_ramp_rate * cvp['RampRatePrice']
    unit.ramp_up_rate_constr = model.addLConstr(
        unit.total_cleared - unit.surplus_ramp_rate <= unit.initial_mw + intervals * up_rate, name=f'ROC_UP_{unit.duid}_{prob_id}')
    if debug_flag:
        if unit.total_cleared_record is not None and unit.total_cleared_record > unit.initial_mw + intervals * up_rate and abs(unit.total_cleared_record - unit.initial_mw - intervals * up_rate) > 1:
            logging.warning(f'{unit.dispatch_type} {unit.duid} above raise ramp rate constraint')

    # Unit Ramp Rate constraint (Down)
    # down_rate = unit.energy.roc_down if unit.ramp_down_rate is None or process == 'predispatch' else unit.ramp_down_rate / 60
    down_rate = unit.energy.roc_down if unit.ramp_down_rate is None else unit.ramp_down_rate / 60
    unit.deficit_ramp_rate = model.addVar(name=f'Deficit_Ramp_Rate_{unit.duid}_{prob_id}')  # Item3
    penalty += unit.deficit_ramp_rate * cvp['RampRatePrice']
    unit.ramp_down_rate_constr = model.addLConstr(
        unit.total_cleared + unit.deficit_ramp_rate >= unit.initial_mw - intervals * down_rate * 10,
        name=f'ROC_DOWN_{unit.duid}_{prob_id}')
    if debug_flag:
        if unit.total_cleared_record is not None and unit.total_cleared_record < unit.initial_mw - intervals * down_rate and abs(unit.total_cleared_record - unit.initial_mw + intervals * down_rate) > 1:
            logging.warning(f'{unit.dispatch_type} {unit.duid} below down ramp rate constraint')
            logging.debug(f'{unit.dispatch_type} {unit.duid} energy target {unit.total_cleared_record} initial {unit.initial_mw} rate {down_rate}')
    return penalty


def add_fixed_loading_constr(model, unit, prob_id, debug_flag, penalty,  cvp):
    """ Fixed loading constraint.

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    if unit.energy.fixed_load != 0:
        unit.deficit_fixed_loading = model.addVar(name=f'Deficit_Fixed_Loading_{unit.duid}_{prob_id}')  # Item13
        unit.surplus_fixed_loading = model.addVar(name=f'Surplus_Fixed_Loading_{unit.duid}_{prob_id}')  # Item13
        penalty += (unit.deficit_fixed_loading + unit.surplus_fixed_loading) * 5700000
        model.addLConstr(
            unit.total_cleared - unit.surplus_fixed_loading + unit.deficit_fixed_loading,
            sense=gp.GRB.EQUAL, rhs=unit.energy.fixed_load, name=f'FIXED_LOAD_{unit.duid}_{prob_id}')
        if debug_flag:
            if unit.total_cleared_record is not None and unit.total_cleared_record != unit.energy.fixed_load:
                logging.warning(f'{unit.dispatch_type} {unit.duid} total cleared record {unit.total_cleared_record} not equal to fixed load {unit.energy.fixed_load}')
    return penalty


def add_cost(unit, regions, cost, debug_flag):
    """ Calculate unit costs.

    Args:
        unit (offer.Unit): The unit
        regions (dict): The dictionary of regions
        cost (gp.LinExpr): The linear expression who represents the costs

    Returns:
        The cost linear expression.
    """
    # Cost of an unit
    unit.cost = sum([o * (p / unit.transmission_loss_factor) for o, p in zip(unit.offers, unit.energy.price_band)])
    if unit.dispatch_type == 'GENERATOR':
        # Add cost to objective
        cost += unit.cost
        # Add generation to region generation
        regions[unit.region_id].dispatchable_generation += unit.total_cleared
        if debug_flag:
            if unit.total_cleared_record is not None:
                regions[unit.region_id].dispatchable_generation_temp += unit.total_cleared_record
            if unit.forecast_poe50 is None:
                regions[unit.region_id].available_generation += unit.energy.max_avail
            else:
                # TODO: UIGF for Predispaptch is still missing
                regions[unit.region_id].available_generation += unit.forecast_poe50
    elif unit.dispatch_type == 'LOAD':
        # Minus cost from objective
        cost -= unit.cost
        # Add load to region load
        regions[unit.region_id].dispatchable_load += unit.total_cleared
        if debug_flag:
            if unit.total_cleared_record is not None:
                regions[unit.region_id].dispatchable_load_temp += unit.total_cleared_record
            regions[unit.region_id].available_load += unit.energy.max_avail
    else:
        logging.error(f'{unit.duid} has no dispatch type.')
    return cost


def add_tie_break_constr(model, unit, bands, penalty,  cvp):
    """ Tie-Break constraint.

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        bands (list): The list of bidding bands
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    for band_no, (offer, price, avail) in enumerate(zip(unit.offers, unit.energy.price_band, unit.energy.band_avail)):
        if avail > 0:
            p = price / unit.transmission_loss_factor
            if p in bands:
                other_offer, other_avail = bands[p][0]
                tb_slack1 = model.addVar(name=f'TBSlack1_Band{band_no + 1}_{unit.duid}')  # Item47
                tb_slack2 = model.addVar(name=f'TBSlack2_Band{band_no + 1}_{unit.duid}')  # Item47
                penalty += (tb_slack1 + tb_slack2) * cvp['TieBreakPrice']
                model.update()
                model.addLConstr(offer / avail - other_offer / other_avail + tb_slack1 - tb_slack2,
                                sense=gp.GRB.EQUAL, rhs=0,
                                name=f'TIE_BREAK_{offer.VarName}_{other_offer.VarName}')
                bands[p].append((offer, avail))
            else:
                bands[p] = [(offer, avail)]
    return penalty


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
        # Is stranded, not trapped, not enabled (i.e. stranded: The unit is bid available to provide this ancillary
        # service type, however, the unit is operating in the energy market outside of the profile for this service type
        # and is stranded from providing this service).
        fcas.flag = 4
        return False

    fcas.enablement_status = 1
    fcas.flag = 1  # Not stranded, not trapped, is enabled (i.e. available).
    return True


def scale_fcas(unit, fcas, bid_type, process, interval, intervals, agc_flag):
    # Scale for AGC(for regulating services only)
    if (bid_type == 'RAISEREG' or bid_type == 'LOWERREG') and agc_flag:
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
        if condition2(process, interval) and fcas.max_avail > unit.raisereg_availability and agc_flag:
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
    if unit.forecast_poe50 is not None and process != 'predispatch':  # TODO: UIGF for predispatch is unknown
        fcas.high_breakpoint = fcas.high_breakpoint - (
                fcas.enablement_max - min(fcas.enablement_max, unit.forecast_poe50))
        fcas.enablement_max = min(fcas.enablement_max, unit.forecast_poe50)


def preprocess_fcas(unit, process, interval, intervals, debug_flag, agc_flag):
    # Preprocess
    for bid_type, fcas in unit.fcas_bids.items():
        scale_fcas(unit, fcas, bid_type, process, interval, intervals, agc_flag)
        # Check pre-conditions for enabling FCAS
        # if enable_fcas(fcas, unit, process, interval) or (condition1(process, interval) and unit.flags and unit.flags[bid_type] % 2 == 1):
        if enable_fcas(fcas, unit, process, interval):
            # if fcas.flag % 2 != unit.flags[bid_type] % 2:
            #     fcas.enablement_status = unit.flags[bid_type] % 2
            fcas.lower_slope_coeff = (fcas.low_breakpoint - fcas.enablement_min) / fcas.max_avail
            fcas.upper_slope_coeff = (fcas.enablement_max - fcas.high_breakpoint) / fcas.max_avail
        # Verify flag
        if unit.flags and debug_flag:
            # if unit.flags[bid_type] != fcas.flag:
            #     logging.debug(f'{unit.dispatch_type} {unit.duid} {bid_type} FCAS flag record {unit.flags[bid_type]} but {fcas.flag}')
            if unit.flags[bid_type] % 2 != fcas.flag % 2:
                logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} FCAS flag record {unit.flags[bid_type]} but {fcas.flag}')


def add_fcas_offers(model, unit, fcas, bid_type, prob_id, debug_flag):
    # FCAS offers
    for no, avail in enumerate(fcas.band_avail):
        bid_offer = model.addVar(name=f'{bid_type}_Avail{no}_{unit.duid}_{prob_id}')
        fcas.offers.append(bid_offer)
        model.addLConstr(bid_offer <= avail, name=f'{bid_type}_AVAIL{no}_{unit.duid}_{prob_id}')
    if unit.target_record and unit.target_record[bid_type] > sum(fcas.band_avail) and debug_flag:
        logging.warning(
            f'{unit.dispatch_type} {unit.duid} {bid_type} {unit.target_record[bid_type]} above sum of avail {sum(fcas.band_avail)}')


def add_fcas_max_avail_constr(model, unit, fcas, bid_type, prob_id, debug_flag, penalty,  cvp):
    """ FCAS MaxAvail constraint.

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        fcas (offer.FcasBid): The FCAS bid
        bid_type (str): FCAS type
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    fcas.max_avail_deficit = model.addVar(
        name=f'FCAS_Max_Avail_Deficit_{bid_type}_{unit.duid}_{prob_id}')  # Item18
    penalty += fcas.max_avail_deficit * cvp['ASMaxAvailPrice']
    fcas.max_avail_constr = model.addLConstr(fcas.value - fcas.max_avail_deficit <= fcas.max_avail,
                                            name=f'FCAS_MAX_AVAIL_{bid_type}_{unit.duid}_{prob_id}')
    if debug_flag:
        if unit.target_record and unit.target_record[bid_type] > fcas.max_avail and abs(unit.target_record[bid_type] - fcas.max_avail) > 1:
            logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} {unit.target_record[bid_type]} above max avail {fcas.max_avail}')
    return penalty


def process_fcas_bid(model, unit, fcas, bid_type, prob_id, debug_flag, penalty,  cvp, cost, regions):
    fcas.value = model.addVar(name=f'{fcas.bid_type}_Target_{unit.duid}_{prob_id}')
    # FCAS offers
    add_fcas_offers(model, unit, fcas, bid_type, prob_id, debug_flag)
    # FCAS total band constraints
    model.addLConstr(fcas.value, sense=gp.GRB.EQUAL, rhs=sum(fcas.offers),
                    name=f'{bid_type}_SUM_{unit.duid}_{prob_id}')
    # Add cost to objective
    fcas.cost = sum([o * p for o, p in zip(fcas.offers, fcas.price_band)])
    cost += fcas.cost
    # FCAS MaxAvail constraint
    penalty = add_fcas_max_avail_constr(model, unit, fcas, bid_type, prob_id, debug_flag, penalty,  cvp)
    # Add FCAS target to region sum
    regions[unit.region_id].fcas_local_dispatch_temp[bid_type] += fcas.value
    return cost, penalty


def add_enablement_min_constr(model, unit, fcas, bid_type, prob_id, debug_flag, penalty,  cvp):
    """ FCAS EnablementMin constraint.

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        fcas (offer.FcasBid): The FCAS bid
        bid_type (str): FCAS type
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    fcas.lower_surplus = model.addVar(name=f'Lower_Surplus_{unit.duid}_{bid_type}_{prob_id}')  # Item22
    penalty += fcas.lower_surplus * cvp['ASEnablementMinPrice']
    model.addLConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value + fcas.lower_surplus >= fcas.enablement_min, name=f'FCAS_ENABLEMENT_MIN_{bid_type}_{unit.duid}_{prob_id}')
    if debug_flag:
        if unit.total_cleared_record and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] < fcas.enablement_min and abs(unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] - fcas.enablement_min) > 0.1:
            logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} below FCAS EnablementMin constraint')
    return penalty


def add_enablement_max_constr(model, unit, fcas, bid_type, prob_id, debug_flag, penalty,  cvp):
    """ FCAS EnablementMax constraint.

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        fcas (offer.FcasBid): The FCAS bid
        bid_type (str): FCAS type
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    fcas.upper_deficit = model.addVar(name=f'Upper_Deficit_{unit.duid}_{bid_type}_{prob_id}')  # Item22
    penalty += fcas.upper_deficit * cvp['ASEnablementMaxPrice']
    model.addLConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value - fcas.upper_deficit <= fcas.enablement_max, name=f'FCAS_ENABLEMENT_MAX_{bid_type}_{unit.duid}_{prob_id}')
    if debug_flag:
        if unit.total_cleared_record and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] > fcas.enablement_max and abs(unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] - fcas.enablement_max) > 0.1:
            logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} above FCAS Enablement Min constraint')
    return penalty


def add_joint_ramping_constr(model, intervals, unit, fcas, bid_type, prob_id, debug_flag, penalty,  cvp):
    """ Joint ramping constraint.

    Args:
        model (gp.Model): The optimisation model
        intervals (int): Number of minutes per interval (5 or 30)
        unit (offer.Unit): The unit
        fcas (offer.FcasBid): The FCAS bid
        bid_type (str): FCAS type
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    if (unit.dispatch_type == 'GENERATOR' and bid_type == 'RAISEREG') or (unit.dispatch_type == 'LOAD' and bid_type == 'LOWERREG'):
        up_rate = unit.energy.roc_up if unit.ramp_up_rate is None else unit.ramp_up_rate / 60
        if up_rate > 0:
            unit.joint_ramp_deficit = model.addVar(name=f'Joint_Ramp_Deficit_{unit.duid}_{prob_id}')  # Item19
            penalty += unit.joint_ramp_deficit * cvp['ASProfilePrice']
            model.addLConstr(unit.total_cleared + fcas.value - unit.joint_ramp_deficit <= unit.initial_mw + intervals * up_rate, name=f'JOINT_RAMPING_{unit.duid}_{prob_id}')
            if debug_flag:
                if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + unit.target_record[bid_type] > unit.initial_mw + intervals * up_rate:
                    if abs(unit.total_cleared_record + unit.target_record[bid_type] - unit.initial_mw - intervals * up_rate) > 1:
                        logging.warning(f'{unit.dispatch_type} {unit.duid} above joint ramping constraint')
                        logging.debug(f'energy {unit.total_cleared_record} {bid_type} {unit.target_record[bid_type]} initial {unit.initial_mw} up rate {up_rate}')

    elif (unit.dispatch_type == 'GENERATOR' and bid_type == 'LOWERREG') or (unit.dispatch_type == 'LOAD' and bid_type == 'RAISEREG'):
        down_rate = unit.energy.roc_down if unit.ramp_down_rate is None else unit.ramp_down_rate / 60
        if down_rate > 0:
            unit.joint_ramp_surplus = model.addVar(name=f'Joint_Ramp_Surplus_{unit.duid}_{prob_id}')  # Item19
            penalty += unit.joint_ramp_surplus * cvp['ASProfilePrice']
            model.addLConstr(unit.total_cleared - fcas.value + unit.joint_ramp_surplus >= unit.initial_mw - intervals * down_rate, name=f'JOINT_RAMPING_{unit.duid}_{prob_id}')
            if debug_flag:
                if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - unit.target_record[bid_type] < unit.initial_mw - intervals * down_rate:
                    if abs(unit.total_cleared_record - unit.target_record[bid_type] - unit.initial_mw + intervals * down_rate) > 1:
                        logging.warning(f'{unit.dispatch_type} {unit.duid} below joint ramping constraint')
                        logging.debug(f'energy {unit.total_cleared_record} {bid_type} {unit.target_record[bid_type]} initial {unit.initial_mw} down rate {down_rate}')
    return penalty


def add_energy_and_fcas_capacity_constr(model, unit, fcas, bid_type, prob_id, debug_flag, penalty,  cvp):
    """ Energy and regulating FCAS capacity constraint.

    Args:
        model (gp.Model): The optimisation model
        unit (offer.Unit): The unit
        fcas (offer.FcasBid): The FCAS bid
        bid_type (str): FCAS type
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    fcas.upper_deficit = model.addVar(name=f'Upper_Deficit_{unit.duid}_{bid_type}_{prob_id}')  # Item22
    penalty += fcas.upper_deficit * cvp['ASEnablementMaxPrice']
    model.addLConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value - fcas.upper_deficit <= fcas.enablement_max, name=f'ENERGY_AND_FCAS_CAPACITY_UPPER_{bid_type}_{unit.duid}_{prob_id}')
    if debug_flag:
        if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] > fcas.enablement_max:
            if abs(unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] - fcas.enablement_max) > 1:
                logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} above energy and regulating FCAS capacity constraint')
                logging.debug(f'energy {unit.total_cleared_record} upper slop {fcas.upper_slope_coeff} {bid_type} {unit.target_record[bid_type]} enablement max {fcas.enablement_max}')

    fcas.lower_surplus = model.addVar(name=f'Lower_Surplus_{unit.duid}_{bid_type}_{prob_id}')  # Item22
    penalty += fcas.lower_surplus * cvp['ASEnablementMinPrice']
    model.addLConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value + fcas.lower_surplus >= fcas.enablement_min, name=f'ENERGY_AND_FCAS_CAPACITY_LOWER_{bid_type}_{unit.duid}_{prob_id}')
    if debug_flag:
        if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] < fcas.enablement_min:
            if (unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] - fcas.enablement_min) > 1:
                logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} below energy and regulating FCAS capacity constraint')
                logging.debug(f'energy {unit.total_cleared_record} lower slop {fcas.lower_slope_coeff} {bid_type} {unit.target_record[bid_type]} enablement min {fcas.enablement_min}')


def add_joint_capacity_constr_test(model, unit, fcas, bid_type, prob_id, debug_flag, penalty,  cvp):
    # TODO: Joint capacity constraint fault
    # Joint capacity constraint
    if (unit.dispatch_type == 'GENERATOR' and bid_type[:5] == 'RAISE') or (unit.dispatch_type == 'LOAD' and bid_type[:5] == 'LOWER'):
        unit.joint_upper_deficit = model.addVar(name=f'Joint_Upper_Deficit_{bid_type}_{unit.duid}_{prob_id}')  # Item22
        penalty += unit.joint_upper_deficit * cvp['ASEnablementMaxPrice']
        reg = unit.fcas_bids.get('RAISEREG' if unit.dispatch_type == 'GENERATOR' else 'LOWERREG')
        if reg is None:
            model.addLConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value - unit.joint_upper_deficit <= fcas.enablement_max, name=f'UPPER_JOINT_CAPACITY_{bid_type}_{unit.duid}_{prob_id}')
            if debug_flag and unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] > fcas.enablement_max:
                logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} above joint capacity constraint')
        else:
            model.addLConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value + reg.enablement_status * reg.upper_slope_coeff * reg.value - unit.joint_upper_deficit <= fcas.enablement_max, name=f'UPPER_JOINT_CAPACITY_{bid_type}_{unit.duid}')
            # model.addLConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value + reg.enablement_status * reg.upper_slope_coeff * reg.value - unit.joint_upper_deficit <= max(fcas.enablement_max, reg.enablement_max), name=f'UPPER_JOINT_CAPACITY_{bid_type}_{unit.duid}_{prob_id}')
            if debug_flag and unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] + reg.enablement_status * reg.upper_slope_coeff * unit.target_record[reg.bid_type] > max(fcas.enablement_max, reg.enablement_max):
                if abs(unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] + reg.enablement_status * reg.upper_slope_coeff * unit.target_record[reg.bid_type] - max(fcas.enablement_max, reg.enablement_max)) > 1:
                    logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} above joint capacity constraint')
                    logging.debug(f'cleared {unit.total_cleared_record} upper {fcas.upper_slope_coeff} target {unit.target_record[bid_type]} status {reg.enablement_status} upper {reg.upper_slope_coeff} value {unit.target_record[reg.bid_type]} max {fcas.enablement_max}')
    if (unit.dispatch_type == 'GENERATOR' and bid_type[:5] == 'LOWER') or (unit.dispatch_type == 'LOAD' and bid_type[:5] == 'RAISE'):
        unit.joint_lower_surplus = model.addVar(name=f'Joint_Lower_Surplus_{bid_type}_{unit.duid}_{prob_id}')  # Item22
        penalty += unit.joint_lower_surplus * cvp['ASEnablementMinPrice']
        reg = unit.fcas_bids.get('LOWERREG' if unit.dispatch_type == 'GENERATOR' else 'RAISEREG')
        if reg is None:
            model.addLConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value + unit.joint_lower_surplus >= fcas.enablement_min, name=f'LOWER_JOINT_CAPACITY_{bid_type}_{unit.duid}_{prob_id}')
            if debug_flag and unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] < fcas.enablement_min:
                logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} below joint capacity constraint')
        else:
            model.addLConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value - reg.enablement_status * reg.lower_slope_coeff * reg.value + unit.joint_lower_surplus >= fcas.enablement_min, name=f'LOWER_JOINT_CAPACITY_{bid_type}_{unit.duid}')
            # model.addLConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value - reg.enablement_status * reg.lower_slope_coeff * reg.value + unit.joint_lower_surplus >= min(fcas.enablement_min, reg.enablement_min), name=f'LOWER_JOINT_CAPACITY_{bid_type}_{unit.duid}_{prob_id}')
            if debug_flag and unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] - reg.enablement_status * reg.lower_slope_coeff * unit.target_record[reg.bid_type] < min(fcas.enablement_min, reg.enablement_min):
                if abs(unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] - reg.enablement_status * reg.lower_slope_coeff * unit.target_record[reg.bid_type] - min(fcas.enablement_min, reg.enablement_min)) > 1:
                    logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} below joint capacity constraint')
    return penalty


def add_joint_capacity_constr(model, unit, fcas, bid_type, prob_id, debug_flag, penalty,  cvp):
    unit.joint_upper_deficit = model.addVar(name=f'Joint_Upper_Deficit_{bid_type}_{unit.duid}_{prob_id}')  # Item22
    penalty += unit.joint_upper_deficit * cvp['ASEnablementMaxPrice']
    reg = unit.fcas_bids.get('RAISEREG')
    if reg is None:
        model.addLConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value - unit.joint_upper_deficit <= fcas.enablement_max, name=f'UPPER_JOINT_CAPACITY_{bid_type}_{unit.duid}_{prob_id}')
        if debug_flag and unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * \
                unit.target_record[bid_type] > fcas.enablement_max:
            logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} above joint capacity constraint')
    else:
        model.addLConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value + reg.enablement_status * reg.upper_slope_coeff * reg.value - unit.joint_upper_deficit <= fcas.enablement_max, name=f'UPPER_JOINT_CAPACITY_{bid_type}_{unit.duid}')
        # model.addLConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value + reg.enablement_status * reg.upper_slope_coeff * reg.value - unit.joint_upper_deficit <= max(fcas.enablement_max, reg.enablement_max), name=f'UPPER_JOINT_CAPACITY_{bid_type}_{unit.duid}_{prob_id}')
        if debug_flag and unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * \
                unit.target_record[bid_type] + reg.enablement_status * reg.upper_slope_coeff * unit.target_record[
            reg.bid_type] > max(fcas.enablement_max, reg.enablement_max):
            if abs(unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[
                bid_type] + reg.enablement_status * reg.upper_slope_coeff * unit.target_record[reg.bid_type] - max(
                fcas.enablement_max, reg.enablement_max)) > 1:
                logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} above joint capacity constraint')
                logging.debug(
                    f'cleared {unit.total_cleared_record} upper {fcas.upper_slope_coeff} target {unit.target_record[bid_type]} status {reg.enablement_status} upper {reg.upper_slope_coeff} value {unit.target_record[reg.bid_type]} max {fcas.enablement_max}')
    unit.joint_lower_surplus = model.addVar(name=f'Joint_Lower_Surplus_{bid_type}_{unit.duid}_{prob_id}')  # Item22
    penalty += unit.joint_lower_surplus * cvp['ASEnablementMinPrice']
    reg = unit.fcas_bids.get('LOWERREG')
    if reg is None:
        model.addLConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value + unit.joint_lower_surplus >= fcas.enablement_min, name=f'LOWER_JOINT_CAPACITY_{bid_type}_{unit.duid}_{prob_id}')
        if debug_flag and unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * \
                unit.target_record[bid_type] < fcas.enablement_min:
            logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} below joint capacity constraint')
    else:
        model.addLConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value - reg.enablement_status * reg.lower_slope_coeff * reg.value + unit.joint_lower_surplus >= fcas.enablement_min, name=f'LOWER_JOINT_CAPACITY_{bid_type}_{unit.duid}')
        # model.addLConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value - reg.enablement_status * reg.lower_slope_coeff * reg.value + unit.joint_lower_surplus >= min(fcas.enablement_min, reg.enablement_min), name=f'LOWER_JOINT_CAPACITY_{bid_type}_{unit.duid}_{prob_id}')
        if debug_flag and unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * \
                unit.target_record[bid_type] - reg.enablement_status * reg.lower_slope_coeff * unit.target_record[
            reg.bid_type] < min(fcas.enablement_min, reg.enablement_min):
            if abs(unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[
                bid_type] - reg.enablement_status * reg.lower_slope_coeff * unit.target_record[reg.bid_type] - min(
                fcas.enablement_min, reg.enablement_min)) > 1:
                logging.warning(f'{unit.dispatch_type} {unit.duid} {bid_type} below joint capacity constraint')
    return penalty


def add_interconnector_capacity_constr(model, ic, ic_id, prob_id, debug_flag, penalty,  cvp):
    # Interconnector Capacity Limit constraint (lower bound)
    ic.flow_deficit = model.addVar(name=f'Flow_Deficit_{ic_id}_{prob_id}')  # Item5
    penalty += ic.flow_deficit * cvp['InterconnectorPrice']
    ic.import_limit_constr = model.addLConstr(ic.mw_flow + ic.flow_deficit >= -ic.import_limit, name=f'IMPORT_LIMIT_{ic_id}_{prob_id}')
    if debug_flag:
        if ic.mw_flow_record is not None and ic.mw_flow_record < -ic.import_limit and abs(ic.mw_flow_record + ic.import_limit) > 1:
            logging.warning(f'IC {ic_id} mw flow record {ic.mw_flow_record} below import limit {-ic.import_limit}')
    # Interconnector Capacity Limit constraint (upper bound)
    ic.flow_surplus = model.addVar(name=f'Flow_Surplus_{ic_id}_{prob_id}')  # Item5
    penalty += ic.flow_surplus * cvp['InterconnectorPrice']
    ic.export_limit_constr = model.addLConstr(ic.mw_flow - ic.flow_surplus <= ic.export_limit, name=f'EXPORT_LIMIT_{ic_id}_{prob_id}')
    if debug_flag:
        if ic.mw_flow_record is not None and ic.mw_flow_record > ic.export_limit and abs(ic.mw_flow_record - ic.export_limit) > 1:
            logging.warning(f'IC {ic_id} mw flow record {ic.mw_flow_record} above export limit {ic.export_limit}')
    return penalty


def add_interconnector_limit_constr(model, ic, ic_id):
    # Interconnector Import Limit Record
    ic.import_record_constr = model.addLConstr(ic.mw_flow >= ic.import_limit_record, name=f'IMPORT_LIMIT_RECORD_{ic_id}')
    if ic.mw_flow_record is not None and ic.import_limit_record is not None and ic.mw_flow_record < ic.import_limit_record and abs(
            ic.mw_flow_record - ic.import_limit_record) > 1:
        logging.warning(
            f'IC {ic_id} mw flow record {ic.mw_flow_record} below import limit record {ic.import_limit_record}')
    # Interconnector Export Limit Record
    ic.export_record_constr = model.addLConstr(ic.mw_flow <= ic.export_limit_record, name=f'EXPORT_LIMIT_RECORD_{ic_id}')
    if ic.mw_flow_record is not None and ic.export_limit_record is not None and ic.mw_flow_record > ic.export_limit_record and abs(
            ic.mw_flow_record - ic.export_limit_record) > 1:
        logging.warning(f'IC {ic_id} mw flow record {ic.mw_flow_record} above export limit {ic.export_limit_record}')


def add_mnsp_ramp_constr(model, intervals, link, link_id, prob_id, debug_flag, penalty,  cvp):
    """ MNSP Ramp Rate Constraint.

    Args:
        model (gp.Model): The optimisation model
        intervals (int): Number of minutes per interval (5 or 30)
        link (offer.Link): The link
        link_id (str): Link ID
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    # MNSPInterconnector ramp rate constraint (Up)
    if link.ramp_up_rate is not None:
        link.mnsp_up_deficit = model.addVar(name=f'MNSP_Up_Deficit_{link_id}_{prob_id}')  # Item4
        penalty += link.mnsp_up_deficit * cvp['MNSPRampRatePrice']
        link.mnsp_up_constr = model.addLConstr(
            link.mw_flow - link.mnsp_up_deficit <= link.metered_mw_flow + intervals * link.ramp_up_rate / 60,
            name=f'MNSPINTERCONNECTOR_UP_RAMP_RATE_{link_id}_{prob_id}')
        if debug_flag:
            if link.mw_flow_record is not None and link.mw_flow_record > link.metered_mw_flow + intervals * link.ramp_up_rate / 60:
                logging.warning(f'Link {link_id} above MNSPInterconnector up ramp rate constraint')
                logging.debug(f'MW flow {link.mw_flow_record} metered {link.metered_mw_flow} up rate {link.ramp_up_rate / 60}')
    # MNSPInterconnector ramp rate constraint (Down)
    if link.ramp_down_rate is not None:
        link.mnsp_dn_surplus = model.addVar(name=f'MNSP_Dn_Surplus_{link_id}_{prob_id}')  # Item4
        penalty += link.mnsp_dn_surplus * cvp['MNSPRampRatePrice']
        link.mnsp_dn_constr = model.addLConstr(
            link.mw_flow + link.mnsp_dn_surplus >= link.metered_mw_flow - intervals * link.ramp_down_rate / 60,
            name=f'MNSPINTERCONNECTOR_DN_RAMP_RATE_{link_id}_{prob_id}')
        if debug_flag:
            if link.mw_flow_record is not None and link.mw_flow_record < link.metered_mw_flow - intervals * link.ramp_down_rate / 60:
                logging.warning(f'Link {link_id} below MNSPInterconnector down ramp rate constraint')
    return penalty


def add_mnsp_total_band_constr(model, link, link_id, prob_id, debug_flag, penalty,  cvp):
    """ Total Band MW Offer constraint - MNSP only.

    Args:
        model (gp.Model): The optimisation model
        link (offer.Link): The link
        link_id (str): Link ID
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    link.mnsp_offer_deficit = model.addVar(name=f'MNSP_Offer_Deficit_{link_id}_{prob_id}')  # Item9
    penalty += link.mnsp_offer_deficit * cvp['MNSPOfferPrice']
    link.total_band_mw_offer_constr = model.addLConstr(link.mw_flow + link.mnsp_offer_deficit,
                                                      sense=gp.GRB.EQUAL,
                                                      rhs=sum(link.offers),
                                                      name=f'MNSP_TOTAL_BAND_MW_OFFER_{link_id}_{prob_id}')
    return penalty


def add_mnsp_avail_constr(model, link, link_id, prob_id, debug_flag, penalty,  cvp):
    """ MNSP Availability constraint.

    Args:
        model (gp.Model): The optimisation model
        link (offer.Link): The link
        link_id (str): Link ID
        prob_id (str): Problem ID
        debug_flag (bool): Used for debugging or not
        penalty (gp.LinExpr): The linear expression who represents the penalty
        voll (float): Market Price Cap
        cvp (dict): The dictionary of Constraint Violation Penalty (CVP) factor

    Returns:
        The penalty linear expression
    """
    if link.max_avail is not None:
        link.mnsp_capacity_deficit = model.addVar(name=f'MNSP_Capacity_Deficit_{link_id}_{prob_id}')  # Item15
        penalty += link.mnsp_capacity_deficit * cvp['MNSPCapacityPrice']
        link.mnsp_availability_constr = model.addLConstr(link.mw_flow - link.mnsp_capacity_deficit <= link.max_avail,
                                                        name=f'MNSP_AVAILABILITY_{link_id}_{prob_id}')
        if debug_flag:
            if link.mw_flow_record is not None and link.mw_flow_record > link.max_avail:
                logging.warning(f'Link {link_id} mw flow record {link.mw_flow_record} above max avail {link.max_avail}')
    return penalty