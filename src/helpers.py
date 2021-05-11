import json
import default
from offer import Unit


def condition1(process, i):
    """ All intervals of dispatch and first interval of p5min and predispatch.

    Args:
        process (str): 'dispatch', 'p5min' or 'predispatch'
        i (int): Interval number

    Returns:
        bool: True if satisfied; False otherwise.
    """
    return process == 'dispatch' or i == 0


def condition2(process, i):
    """ All intervals of dispatch, first interval of p5min, and none of predispatch.

        Args:
            process (str): 'dispatch', 'p5min' or 'predispatch'
            i (int): Interval number

        Returns:
            bool: True if satisfied; False otherwise.
        """
    return process == 'dispatch' or (process == 'p5min' and i == 0)


def condition3(process, dis, pre, rhs):
    c1 = (process == 'p5min' or process == 'predispatch') and pre
    c2 = process == 'dispatch' and dis
    c3 = rhs is not None
    return (c1 or c2) and c3


def read_cvp():
    input_dir = default.DATA_DIR / 'CVP.json'
    with input_dir.open() as f:
        return json.load(f)


def get_total_intervals(process, start_time=None):
    dispatch_intervals = 288
    p5min_intervals = 12
    if process == 'dispatch' or process == 'DISPATCH':
        return dispatch_intervals
    elif process == 'p5min' or process == 'P5MIN':
        return p5min_intervals
    else:
        pre_dir = default.DATA_DIR / 'predispatch_intervals.json'
        with pre_dir.open() as f:
            return json.load(f)[start_time.strftime('%H:%M')]


class Battery:
    def __init__(self, e, p, region_id=None, method=None):
        self.bat_id = 'Battery'
        self.data = self.read_data()
        self.generator = Unit(self.data['gen_id'])
        self.generator.dispatch_type = 'GENERATOR'
        self.generator.dispatch_mode = 0
        self.generator.region_id = self.data['region'] if region_id is None else region_id
        self.generator.transmission_loss_factor = self.data['gen_mlf']
        self.generator.ramp_up_rate = self.data['gen_roc_up'] * 60
        self.generator.ramp_down_rate = self.data['gen_roc_down'] * 60
        self.generator.initial_mw = 0
        self.generator.registered_capacity = self.data['gen_reg_cap']
        # self.generator.max_capacity = self.data['gen_max_cap']
        self.generator.max_capacity = p
        self.load = Unit(self.data['load_id'])
        self.load.dispatch_type = 'LOAD'
        self.load.dispatch_mode = 0
        self.load.region_id = self.data['region'] if region_id is None else region_id
        self.load.transmission_loss_factor = self.data['load_mlf']
        self.load.ramp_up_rate = self.data['load_roc_up'] * 60
        self.load.ramp_down_rate = self.data['load_roc_down'] * 60
        self.load.initial_mw = 0
        self.load.registered_capacity = self.data['load_reg_cap']
        # self.load.max_capacity = self.data['load_max_cap']
        self.load.max_capacity = p
        # self.Emax = self.data['Emax']
        # self.generator.Emax = self.data['Emax']
        # self.load.Emax = self.data['Emax']
        self.Emax = e
        self.generator.Emax = e
        self.load.Emax = e
        self.eff = self.data['eff']
        self.name = f'{self.bat_id} {self.Emax}MWh {self.generator.max_capacity}MW {self.load.region_id} Method {method}'
        self.bat_dir = default.OUT_DIR / self.name
        self.bat_dir.mkdir(parents=True, exist_ok=True)
        # self.gen_fcas_types = self.data['gen_fcas_types']
        # self.load_fcas_types = self.data['load_fcas_types']
        # self.gen_fcas_record = {
        #     'Raisereg': [],
        #     'Raise5min': [],
        #     'Raise60sec': [],
        #     'Raise6sec': [],
        #     'Lowerreg': [],
        #     'Lower5min': [],
        #     'Lower60sec': [],
        #     'Lower6sec': []
        # }
        # self.load_fcas_record = {
        #     'Raisereg': [],
        #     'Raise5min': [],
        #     'Raise60sec': [],
        #     'Raise6sec': [],
        #     'Lowerreg': [],
        #     'Lower5min': [],
        #     'Lower60sec': [],
        #     'Lower6sec': []
        # }

    def read_data(self):
        input_dir = default.DATA_DIR / 'batteries.json'
        with input_dir.open() as f:
            data = json.load(f)
            return data[self.bat_id]