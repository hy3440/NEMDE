import csv
import datetime
import logging
import preprocess


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
    def __init__(self, row):
        self.gen_con_id = row[6]
        self.version_no = int(row[5])
        self.constraint_type = row[7]
        self.constraint_value = float(row[8])
        self.generic_constraint_weight = float(row[11])
        self.dispatch = row[16] == '1'
        self.predispatch = row[17] == '1'
        self.stpasa = row[18] == '1'
        self.mtpasa = row[19] == '1'
        self.limit_type = row[22]
        self.force_scada = int(row[29])


def init_constraints(t):
    constr_dir = preprocess.download_dvd_data('GENCONDATA')
    logging.info('Read generic constraint data.')
    with constr_dir.open() as f:
        reader = csv.reader(f)
        constraints = {}
        for row in reader:
            if row[0] == 'D' and t >= preprocess.extract_datetime(row[4]):
                gen_con_id = row[6]
                constr = constraints.get(gen_con_id)
                if not constr or constr.version_no < int(row[5]):
                    constraints[gen_con_id] = Constraint(row)

