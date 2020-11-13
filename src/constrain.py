import csv
import datetime
import logging
import preprocess

intervention = '0'


class Constraint:
    """Constraint class.

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
        self.last_changed = preprocess.extract_datetime(row[15])
        self.dispatch = row[16] == '1'
        self.predispatch = row[17] == '1'
        self.stpasa = row[18] == '1'
        self.mtpasa = row[19] == '1'
        self.limit_type = row[22]
        self.force_scada = int(row[29])


def init_constraints(t):
    constraints = {}
    constr_dir = preprocess.download_dvd_data('GENCONDATA', t)
    # logging.info('Read generic constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and t >= preprocess.extract_datetime(row[4]):
                gen_con_id = row[6]
                constr = constraints.get(gen_con_id)
                if not constr:
                    constraints[gen_con_id] = Constraint(row)
                elif constr.last_changed < preprocess.extract_datetime(row[15]):
                    constr.update(row)
        return constraints


def add_spd_connection_point_constraint(t, constraints, units, connection_points, fcas_flag):
    constr_dir = preprocess.download_dvd_data('SPDCONNECTIONPOINTCONSTRAINT', t)
    # logging.info('Read SPD connection point constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        uncovered = set()
        for row in reader:
            if row[0] == 'D' and t >= preprocess.extract_datetime(row[5]):
                constr = constraints.get(row[7])  # 7: Gen con ID
                if constr is None:
                    logging.error(f'Constraint {row[7]} for connection point was not included.')
                last = constr.connection_point_last_changed
                current = preprocess.extract_datetime(row[9])
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
    constr_dir = preprocess.download_dvd_data('SPDINTERCONNECTORCONSTRAINT', t)
    # logging.info('Read SPD interconnector constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and t >= preprocess.extract_datetime(row[5]):
                constr = constraints[row[7]]  # 7: Gen con ID
                current = preprocess.extract_datetime(row[9])
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
    constr_dir = preprocess.download_dvd_data('SPDREGIONCONSTRAINT', t)
    # logging.info('Read SPD region constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and t >= preprocess.extract_datetime(row[5]):  # 5: Effective date
                constr = constraints[row[7]]  # 7: Gen con ID
                last = constr.region_last_changed
                current = preprocess.extract_datetime(row[9])
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


def add_dispatch_constraint(t, constraints):
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
                else:
                    logging.error(f'Constraint {row[6]} was not included')


def add_predispatch_constraint(t, start, constraints):
    constr_dir = preprocess.download_predispatch(start)
    # logging.info('Read pre-dispatch constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'CONSTRAINT_SOLUTION' and preprocess.extract_datetime(row[13]) == t and row[8] == '0':  # 8: Intervention flag; 13: Interval datetime
                constr = constraints.get(row[6])  # 6: Constraint ID
                if constr:
                    constr.rhs = float(row[9])
                    constr.marginal_value = float(row[10])
                    constr.voilation_degree = float(row[11])
                    constr.lhs = float(row[17])
                # else:
                #     logging.error('Constraint {row[6]} was not included')


def add_p5min_constraint(t, start, constraints):
    constr_dir = preprocess.download_5min_predispatch(start)
    # logging.info('Read 5min pre-dispatch constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'CONSTRAINTSOLUTION' and preprocess.extract_datetime(row[6]) == t and row[5] == '0':  # 5: Intervention flag; 6: Interval datetime
                constr = constraints.get(row[7])  # 7: Constraint ID
                if constr:
                    constr.rhs = float(row[8])
                    constr.marginal_value = float(row[9])
                    constr.voilation_degree = float(row[10])
                    constr.lhs = float(row[15])
                # else:
                #     logging.error('Constraint {row[7]} was not included')


def get_constraints(process, t, units, connection_points, interconnectors, regions, start, fcas_flag):
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


def get_market_price(t):
    constr_dir = preprocess.download_dvd_data('MARKET_PRICE_THRESHOLDS', t)
    # logging.info('Read Market Price Cap (MPC).')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and t >= preprocess.extract_datetime(row[4]):
                voll = float(row[6])
                market_price_floor = float(row[7])
    return voll, market_price_floor
