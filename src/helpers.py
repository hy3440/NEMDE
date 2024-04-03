import json
import default
from offer import Unit, EnergyBid, FcasBid


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
    """Check if the constraint need to be applied.

    Args:
        process (str): 'dispatch', 'p5min', or 'predispatch'
        dis (bool): constraint's dispatch flag
        pre (bool): constraint's predispatch flag
        rhs (float): constraint's RHS value

    Returns:
        bool: True if satisfied; False otherwise.
    """
    c1 = (process == 'p5min' or process == 'predispatch') and pre
    c2 = process == 'dispatch' and dis
    c3 = rhs is not None
    return (c1 or c2) and c3


def read_cvp():
    """Read predefined CVP factors.

    Returns:
        dict: a dictionary of CVP factors
    """
    input_dir = default.DATA_DIR / 'CVP.json'
    with input_dir.open() as f:
        return json.load(f)


def get_total_intervals(process, start_time=None):
    """Get the number of total intervals.

    Args:
        process (str): 'dispatch', 'p5min', or 'predispatch'
        start_time (datetime.datetime): the start datetime of the process

    Returns:
        int: the number of total intervals
    """
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
    def __init__(self, e, p, region_id='NSW1', method=2, usage=None, bat_id='Battery'):
        self.usage = usage
        self.bat_id = bat_id
        self.region_id = region_id
        self.data = self.read_data()
        self.generator = Unit(self.data['gen_id'])
        self.generator.dispatch_type = 'GENERATOR'
        self.generator.dispatch_mode = 0
        self.generator.region_id = self.data['region'] if region_id is None else region_id
        self.generator.transmission_loss_factor = self.data['gen_mlf']
        # self.generator.ramp_up_rate = self.data['gen_roc_up'] * 60
        # self.generator.ramp_down_rate = self.data['gen_roc_down'] * 60
        self.generator.initial_mw = 0
        self.generator.registered_capacity = self.data['gen_reg_cap']
        self.generator.max_capacity = self.data['gen_max_cap'] if p is None else p
        self.load = Unit(self.data['load_id'])
        self.load.dispatch_type = 'LOAD'
        self.load.dispatch_mode = 0
        self.load.region_id = self.data['region'] if region_id is None else region_id
        self.load.transmission_loss_factor = self.data['load_mlf']
        # self.load.ramp_up_rate = self.data['load_roc_up'] * 60
        # self.load.ramp_down_rate = self.data['load_roc_down'] * 60
        self.load.initial_mw = 0
        self.load.registered_capacity = self.data['load_reg_cap']
        self.load.max_capacity = self.data['load_max_cap'] if p is None else p

        self.size = self.data['Emax'] if e is None else e
        self.Emax = 0.95 * self.size
        self.Emin = 0.15 * self.size
        self.initial_E = 0.5 * self.size
        self.initial_E_record = 0.5 * self.size
        self.generator.Emax = self.Emax
        self.load.Emax = self.Emax
        self.eff = self.data['eff']
        self.name = f'{self.bat_id} {self.size}MWh {self.generator.max_capacity}MW {self.load.region_id} Method {method}'
        if type(self.size) == int and type(self.generator.max_capacity) == int:
            self.plot_name = self.name
        else:
            emax_temp = str(self.Emax).replace('.', '-')
            cap_temp = str(self.generator.max_capacity).replace('.', '-')
            self.plot_name = f'{self.bat_id} {emax_temp}MWh {cap_temp}MW {self.load.region_id} Method {method}'
        self.bat_dir = default.OUT_DIR / usage / self.name
        self.bat_dir.mkdir(parents=True, exist_ok=True)
        self.degradation_cost = 0
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

    # def __repr__(self):
    #     return self.name

    def read_data(self):
        input_dir = default.DATA_DIR / 'batteries.json'
        with input_dir.open() as f:
            data = json.load(f)
            return data[self.bat_id]

    def add_energy_bid(self, gen_price, gen_avail, load_price, load_avail):
        self.generator.energy = EnergyBid([])
        self.generator.energy.price_band = gen_price
        self.generator.energy.band_avail = gen_avail
        self.load.energy = EnergyBid([])
        self.load.energy.price_band = load_price
        self.load.energy.band_avail = load_avail
        for unit in [self.generator, self.load]:
            unit.energy.fixed_load = 0
            unit.energy.max_avail = unit.max_capacity
            unit.energy.daily_energy_limit = 0
            unit.energy.roc_up = None
            unit.energy.roc_down = None

    def add_fcas_bid(self, bid_type, price_bands, band_avails, load_flag):
        fcas_bid = FcasBid([])
        fcas_bid.bid_type = bid_type
        fcas_bid.price_band = price_bands
        fcas_bid.band_avail = band_avails
        tstep = 5 / 60
        # C1 = battery.eff * (E - battery.Emin) / tstep
        # C2 = (battery.Emax - E) / (tstep * self.eff)
        Pmax = self.load.max_capacity
        if (bid_type[:5] == 'RAISE' and not load_flag) or (bid_type[:5] == 'LOWER' and load_flag):
            fcas_bid.max_avail = fcas_bid.enablement_max = Pmax
            # fcas_bid.max_avail = fcas_bid.enablement_max = min(Pmax, C2 if load_flag else C1)
            fcas_bid.enablement_min = fcas_bid.low_breakpoint = fcas_bid.high_breakpoint = 0
        else:
            fcas_bid.max_avail = Pmax
            fcas_bid.enablement_min = 0
            fcas_bid.low_breakpoint = fcas_bid.high_breakpoint = fcas_bid.enablement_max = Pmax
        unit = self.load if load_flag else self.generator
        unit.fcas_bids[bid_type] = fcas_bid

    def update_usage(self, usage):
        self.usage = usage
        self.bat_dir = default.OUT_DIR / usage / self.name


def generate_batteries_by_energies(energies, usage):
    """Generate a list of Battery instances.

    Args:
        energies (list): a list of battery sizes (in MWh)
        usage (str): what those batteries used for

    Returns:
        list: a list of Battery instances
    """
    return [Battery(e, int(e * 2 / 3) if type(e) == int else (e * 2 / 3), usage=usage) for e in energies]


def generate_batteries_by_usages(energy, usages):
    """Generate a list of Battery instances.

    Args:
        energies (list): a list of battery sizes (in MWh)
        usage (str): what those batteries used for

    Returns:
        list: a list of Battery instances
    """
    return [Battery(energy, int(energy * 2 / 3) if type(energy) == int else (energy * 2 / 3), usage=u) for u in usages]


def init_batteries(e, p, u, bat_id):
    b = Battery(e, p, usage=u, bat_id=bat_id)
    return {b.bat_id: b}, {b.generator, b.load}


def phi(dod):
    return 5.24E-4 * pow(dod, 2.03)


def marginal_costs(R, eff, M, m):
    return R * M * (phi(m / M) - phi((m - 1) / M)) / eff