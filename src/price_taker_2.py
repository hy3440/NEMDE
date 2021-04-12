# First version of price-taker based on http://users.cecs.anu.edu.au/~pscott/teaching/engn8527-2015/exercise.html

import csv
import datetime
import gurobipy
import json
import logging
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pathlib
import preprocess

log = logging.getLogger(__name__)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent  # Base directory
DATA_DIR = BASE_DIR.joinpath('data')  # Data directory
OUT_DIR = BASE_DIR.joinpath('out')  # Result directory
FIVE_MIN = datetime.timedelta(minutes=5)
THIRTY_MIN = datetime.timedelta(minutes=30)
ONE_DAY = datetime.timedelta(days=1)
DAYS = 1
INTERVALS = 1
PERIODS = 48
TOTAL_INTERVALS = DAYS * INTERVALS
TOTAL_PERIODS = DAYS * PERIODS
START = 0
intervention = '0'
# # Battery
# region = 'SA1'  # Region ID
# gen_id = 'DALNTH01'  # Generator DUID
# load_id = 'DALNTHL1'  # Load DUID
# gen_mlf = 0.9045  # Marginal loss factor for generator
# load_mlf = 0.9990  # Marginal loss factor for load
# reg_cap = 30  # Regular(?) capacity (MW)
# max_cap = 30  # Max capacity (MW)
# max_roc = 5 * 60  # Ramp rate summarised from bid file (MW / hour)
# Emax = 12.65  # Battery size (MWh)
# eff = 0.5  # Efficiency
# E0 = 11.2369  # Initial battery charge level
tsteps = [5 / 60, 30 / 60]  # Time step duration (hours)
# Energy
E = []
E_record = []
# Price
price_dict = {}
period_rrp_record = []  # Average get_prices over 6 intervals as period price record
interval_rrp_record = []  # Regional reference price record at each interval
interval_prices_dict = {}
# raise6sec_rrp_record = []
# raise60sec_rrp_record = []
# raise5min_rrp_record = []
# raisereg_rrp_record = []
# lower6sec_rrp_record = []
# lower60sec_rrp_record = []
# lower5min_rrp_record = []
# lowerreg_rrp_record = []
# Power
energy_gen = []
energy_load = []
# raise6sec_gen = []
# raise60sec_gen = []
# raise5min_gen = []
# raisereg_gen = []
# lower6sec_gen = []
# lower60sec_gen = []
# lower5min_gen = []
# lowerreg_gen = []
# raise6sec_load = []
# raise60sec_load = []
# raise5min_load = []
# raisereg_load = []
# lower6sec_load = []
# lower60sec_load = []
# lower5min_load = []
# lowerreg_load = []
# Power Record
actual_gen_record = []
actual_load_record = []
energy_gen_record = []
energy_load_record = []

# Revenue
revenue_record = []
# revenue_actual_record = []
revenue = []
objs = []
times = []

forecast_flag = True # True if forecast; False if predispatch
# results_dir = OUT_DIR / 'efficiency={}'.format(eff)
# if not results_dir.is_dir():
#     results_dir.mkdir()
# forecast_dir = results_dir / ('forecast' if forecast_flag else 'predispatch')
# if not forecast_dir.is_dir():
#     forecast_dir.mkdir()
# forecast_csv = results_dir / ('forecast_csv' if forecast_flag else 'predispatch_csv')
# if not forecast_csv.is_dir():
#     forecast_csv.mkdir()


class Battery:
    def __init__(self, name):
        self.name = name
        self.data = self.read_data()
        self.region = self.data['region']
        self.gen_id = self.data['gen_id']
        self.gen_mlf = self.data['gen_mlf']
        self.gen_reg_cap = self.data['gen_reg_cap']
        self.gen_max_cap = self.data['gen_max_cap']
        self.gen_max_roc = self.data['gen_max_roc'] * 60
        self.gen_roc_up = self.data['gen_roc_up'] * 60
        self.gen_roc_down = self.data['gen_roc_down'] * 60
        self.load_id = self.data['load_id']
        self.load_mlf = self.data['load_mlf']
        self.load_reg_cap = self.data['load_reg_cap']
        self.load_max_cap = self.data['load_max_cap']
        self.load_max_roc = self.data['load_max_roc'] * 60
        self.load_roc_up = self.data['load_roc_up'] * 60
        self.load_roc_down = self.data['load_roc_down'] * 60
        self.Emax = self.data['Emax']
        self.eff = self.data['eff']
        self.bat_dir = OUT_DIR / f'{name} eff={self.eff}'
        self.bat_dir.mkdir(parents=True, exist_ok=True)
        self.gen_fcas_types = self.data['gen_fcas_types']
        self.load_fcas_types = self.data['load_fcas_types']
        self.gen_fcas_record = {
            'Raisereg': [],
            'Raise5min': [],
            'Raise60sec': [],
            'Raise6sec': [],
            'Lowerreg': [],
            'Lower5min': [],
            'Lower60sec': [],
            'Lower6sec': []
        }
        self.load_fcas_record = {
            'Raisereg': [],
            'Raise5min': [],
            'Raise60sec': [],
            'Raise6sec': [],
            'Lowerreg': [],
            'Lower5min': [],
            'Lower60sec': [],
            'Lower6sec': []
        }

    def read_data(self):
        input_dir = DATA_DIR / 'batteries.json'
        with input_dir.open() as f:
            data = json.load(f)
            return data[self.name]


def extract_e0(t):
    file_datetime = t.strftime('%d-%b-%Y-%H-%M-%S')
    e0_dir = DATA_DIR.joinpath(f"E0_{t.strftime('%Y%m%d')}.csv")
    with e0_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == file_datetime:
                return float(row[1])


def extract_e_record(start):
    for i in range(TOTAL_INTERVALS + 1):
        t = start + i * FIVE_MIN
        if t.minute == 0 and t.hour == 0:
            t += datetime.timedelta(seconds=4)
        file_datetime = t.strftime('%d-%b-%Y-%H-%M-%S')
        e0_dir = DATA_DIR / 'all' / 'E0.csv'
        with e0_dir.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 0 and row[0] == file_datetime:
                    E_record.append(float(row[1]))
                    break


def extract_trading(t, region):
    trading_dir = preprocess.download_trading(t)
    with trading_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'PRICE' and row[6] == region:
                return float(row[8])  # RRP of period


def get_dir(t, start, process):
    interval_datetime = preprocess.get_case_datetime(t + preprocess.THIRTY_MIN) if process == 'predispatch' else preprocess.get_case_datetime(t + preprocess.FIVE_MIN)
    if process == 'dispatch':
        p = preprocess.OUT_DIR / f'{process}_{preprocess.get_case_datetime(start)}'
    else:
        p = preprocess.OUT_DIR / process / f'{process}_{preprocess.get_case_datetime(start)}'
    return p / f'dispatchload_{interval_datetime}.csv'


def extract_dispatch(t, region):
    dispatch_dir = preprocess.download_dispatch_summary(t)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'PRICE' and row[6] == region and row[8] == intervention:
                # interval_rrp_record.append(float(row[9]))  # RRP of interval
                # interval_prices_dict[t] = float(row[9])
                # raise6sec_rrp_record.append(float(row[15]))
                # raise60sec_rrp_record.append(float(row[18]))
                # raise5min_rrp_record.append(float(row[21]))
                # raisereg_rrp_record.append(float(row[24]))
                # lower6sec_rrp_record.append(float(row[27]))
                # lower60sec_rrp_record.append(float(row[30]))
                # lower5min_rrp_record.append(float(row[33]))
                # lowerreg_rrp_record.append(float(row[36]))
                return float(row[9])


def extract_scada(t, battery):
    scada_dir = preprocess.download_dispatch_scada(t)
    with scada_dir.open() as f:
        reader = csv.reader(f)
        flag = False
        for row in reader:
            if row[0] == 'D':
                if row[5] == battery.gen_id:
                    actual_gen_record.append(float(row[6]))  # SCADA VALUE
                    if flag:
                        return None
                    else:
                        flag = True
                elif row[5] == battery.load_id:
                    actual_load_record.append(float(row[6]))  # SCADA VALUE
                    if flag:
                        return None
                    else:
                        flag = True


def extract_next_day_dispatch(t, battery):
    record_dir = preprocess.download_next_day_dispatch(t)
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'UNIT_SOLUTION' and row[6] == battery.gen_id and row[9] == intervention:
                actual_gen_record.append(float(row[13]))  # Initial MW
                energy_gen_record.append(float(row[14]))  # Total cleared
                # raise6sec_gen_record.append(float(row[22]))
                # raise60sec_gen_record.append(float(row[21]))
                # raise5min_gen_record.append(float(row[20]))
                # raisereg_gen_record.append(float(row[35]))
                # lower6sec_gen_record.append(float(row[19]))
                # lower60sec_gen_record.append(float(row[18]))
                # lower5min_gen_record.append(float(row[17]))
                # lowerreg_gen_record.append(float(row[34]))
            elif row[0] == 'D' and row[2] == 'UNIT_SOLUTION' and row[6] == battery.load_id and row[9] == intervention:
                actual_load_record.append(float(row[13]))  # Initial MW
                energy_load_record.append(float(row[14]))  # Total cleared
                # raise6sec_load_record.append(float(row[22]))
                # raise60sec_load_record.append(float(row[21]))
                # raise5min_load_record.append(float(row[20]))
                # raisereg_load_record.append(float(row[35]))
                # lower6sec_load_record.append(float(row[19]))
                # lower60sec_load_record.append(float(row[18]))
                # lower5min_load_record.append(float(row[17]))
                # lowerreg_load_record.append(float(row[34]))


def extract_5min_predispatch(t, region):
    p5min_times = []
    p5min_energy_prices = []
    # raise6sec_prices = []
    # raise60sec_prices = []
    # raise5min_prices = []
    # raisereg_prices = []
    # lower6sec_prices = []
    # lower60sec_prices = []
    # lower5min_prices = []
    # lowerreg_prices = []
    dispatch_dir = preprocess.download_5min_predispatch(t)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        current = preprocess.get_interval_datetime(t)
        # return [float(row[8]) for row in reader if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and row[7] == region and row[6] != current]  # RRP
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and row[7] == region and row[5] == intervention:
                p5min_times.append(preprocess.extract_datetime(row[6]))
                p5min_energy_prices.append(float(row[8]))
                # raise6sec_prices.append(float(row[11]))
                # raise60sec_prices.append(float(row[13]))
                # raise5min_prices.append(float(row[15]))
                # raisereg_prices.append(float(row[17]))
                # lower6sec_prices.append(float(row[19]))
                # lower60sec_prices.append(float(row[21]))
                # lower5min_prices.append(float(row[23]))
                # lowerreg_prices.append(float(row[25]))
    return p5min_energy_prices, p5min_times
    # return energy_prices, raise6sec_prices, raise60sec_prices, raise5min_prices, raisereg_prices, lower6sec_prices, lower60sec_prices, lower5min_prices, lowerreg_prices


# def extract_predispatch(k, t, energy_prices, raise6sec_prices, raise60sec_prices, raise5min_prices, raisereg_prices, lower6sec_prices, lower60sec_prices, lower5min_prices, lowerreg_prices):
def extract_predispatch(k, t, region):
    # print('30 min file:')
    # print(t + FIVE_MIN * (6 - k))
    dispatch_dir = preprocess.download_predispatch(t + FIVE_MIN * (6 - k))
    p5_datetime = t + 12 * FIVE_MIN
    predispatch_times = []
    predispatch_energy_prices = []
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGION_PRICES' and row[6] == region and preprocess.extract_datetime(row[28]) > p5_datetime and row[8] == intervention:
                predispatch_times.append(preprocess.extract_datetime(row[28]))
                predispatch_energy_prices.append(float(row[9]))
                # raise6sec_prices.append(float(row[29]))
                # raise60sec_prices.append(float(row[30]))
                # raise5min_prices.append(float(row[31]))
                # raisereg_prices.append(float(row[32]))
                # lower6sec_prices.append(float(row[33]))
                # lower60sec_prices.append(float(row[34]))
                # lower5min_prices.append(float(row[35]))
                # lowerreg_prices.append(float(row[36]))
    return predispatch_energy_prices, predispatch_times


def calculate_energy_prices(i, t, region):
    energy_prices = []
    energy_times = []
    k = i % 6
    p5min_energy_prices, p5min_times = extract_5min_predispatch(t + FIVE_MIN, region)
    predispatch_energy_prices, predispatch_times = extract_predispatch(k, t, region)
    first_period = sum(interval_rrp_record[-k-1:]) + sum(p5min_energy_prices[1:6-k])
    energy_prices += [first_period / 6 for _ in range(6-k)]
    energy_prices += [sum(p5min_energy_prices[6-k:12-k]) / 6 for _ in range(6)]
    final_period = sum(p5min_energy_prices[12-k:]) + predispatch_energy_prices[0] * (6-k) if k != 0 else predispatch_energy_prices[0] * (6-k)
    energy_prices += [final_period / 6 for _ in range(6)]
    energy_prices += predispatch_energy_prices[1:]
    energy_times += p5min_times + [p5min_times[-1] + j * FIVE_MIN for j in range(1, 7-k)]
    energy_times += predispatch_times[1:]
    n = 18 - k
    return energy_prices, n, energy_times, p5min_energy_prices, p5min_times, predispatch_energy_prices, predispatch_times


def extract_predispatch_prices(i, t, region):
    energy_prices = []
    energy_times = []
    k = i % 6
    p5min_energy_prices, p5min_times = extract_5min_predispatch(t + FIVE_MIN, region)
    predispatch_energy_prices, predispatch_times = extract_predispatch(k, t, region)
    energy_prices += p5min_energy_prices
    energy_times += p5min_times
    energy_prices += [predispatch_energy_prices[0] for _ in range(6 - k)]
    energy_times += [p5min_times[-1] + j * FIVE_MIN for j in range(1, 7-k)]
    energy_prices += predispatch_energy_prices[1:]
    energy_times += predispatch_times[1:]
    n = 18 - k
    return energy_prices, n, energy_times, p5min_energy_prices, p5min_times, predispatch_energy_prices, predispatch_times


def schedule(i, t, battery):
    model = gurobipy.Model(f'price_taker_{i}')
    # model.setParam('OutputFlag', False)
    # energy_prices, raise6sec_prices, raise60sec_prices, raise5min_prices, raisereg_prices, lower6sec_prices, lower60sec_prices, lower5min_prices, lowerreg_prices = extract_5min_predispatch(t + FIVE_MIN)
    # extract_predispatch(6 - i, t, energy_prices, raise6sec_prices, raise60sec_prices, raise5min_prices, raisereg_prices, lower6sec_prices, lower60sec_prices, lower5min_prices, lowerreg_prices)
    energy_prices, n, energy_times, p5min_energy_prices, p5min_times, predispatch_energy_prices, predispatch_times = calculate_energy_prices(i, t, battery.region) if forecast_flag else extract_predispatch_prices(i, t, battery.region)
    T = len(energy_prices)
    Epred = [model.addVar(ub=battery.Emax, name=f'Epred_{j}') for j in range(T)]
    energy_pgen = [model.addVar(ub=battery.gen_max_cap, name=f'energy_pgen_{j}') for j in range(T)]
    energy_pload = [model.addVar(ub=battery.load_max_cap, name=f'energy_pload_{j}') for j in range(T)]
    # raise6sec_pgen = [model.addVar(ub=max_cap, name='raise6sec_pgen_{}'.format(j)) for j in range(T)]
    # raise6sec_pload = [model.addVar(ub=max_cap, name='raise6sec_pload_{}'.format(j)) for j in range(T)]
    # raise60sec_pgen = [model.addVar(ub=max_cap, name='raise60sec_pgen_{}'.format(j)) for j in range(T)]
    # raise60sec_pload = [model.addVar(ub=max_cap, name='raise60sec_pload_{}'.format(j)) for j in range(T)]
    # raise5min_pgen = [model.addVar(ub=max_cap, name='raise5min_pgen_{}'.format(j)) for j in range(T)]
    # raise5min_pload = [model.addVar(ub=max_cap, name='raise5min_pload_{}'.format(j)) for j in range(T)]
    # raisereg_pgen = [model.addVar(ub=max_cap, name='raisereg_pgen_{}'.format(j)) for j in range(T)]
    # raisereg_pload = [model.addVar(ub=max_cap, name='raisereg_pload_{}'.format(j)) for j in range(T)]
    # lower6sec_pgen = [model.addVar(ub=max_cap, name='lower5sec_pgen_{}'.format(j)) for j in range(T)]
    # lower6sec_pload = [model.addVar(ub=max_cap, name='lower5sec_pload_{}'.format(j)) for j in range(T)]
    # lower60sec_pgen = [model.addVar(ub=max_cap, name='lower60sec_pgen_{}'.format(j)) for j in range(T)]
    # lower60sec_pload = [model.addVar(ub=max_cap, name='lower60sec_pload_{}'.format(j)) for j in range(T)]
    # lower5min_pgen = [model.addVar(ub=max_cap, name='lower5min_pgen_{}'.format(j)) for j in range(T)]
    # lower5min_pload = [model.addVar(ub=max_cap, name='lower5min_pload_{}'.format(j)) for j in range(T)]
    # lowerreg_pgen = [model.addVar(ub=max_cap, name='lowerreg_pgen_{}'.format(j)) for j in range(T)]
    # lowerreg_pload = [model.addVar(ub=max_cap, name='lowerreg_pload_{}'.format(j)) for j in range(T)]

    if i == START:
        current_gen = actual_gen_record[i]
        current_load = actual_load_record[i]
        current_E = E_record[i] if battery.name == 'Dalrymple1' else battery.Emax * 0.5
    else:
        current_gen = energy_gen[i - 1]
        current_load = energy_load[i - 1]
        current_E = E[i - 1]
    obj = 0
    for j in range(T):
        if energy_times[j].hour == 4 and energy_times[j].minute == 0:
            model.addConstr(Epred[j] >= battery.Emax * 0.5)
        tstep = tsteps[0] if j < n else tsteps[1]
        model.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[energy_pgen[j], energy_pload[j]])
        # model.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[raise6sec_pgen[j], raise6sec_pload[j]])
        # model.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[raise60sec_pgen[j], raise60sec_pload[j]])
        # model.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[raise5min_pgen[j], raise5min_pload[j]])
        # model.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[raisereg_pgen[j], raisereg_pload[j]])
        # model.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[lower6sec_pgen[j], lower6sec_pload[j]])
        # model.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[lower60sec_pgen[j], lower60sec_pload[j]])
        # model.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[lower5min_pgen[j], lower5min_pload[j]])
        # model.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[lowerreg_pgen[j], lowerreg_pload[j]])

        obj += energy_prices[j] * (battery.gen_mlf * energy_pgen[j] - battery.load_mlf * energy_pload[j]) * tstep
        # raise6sec_prices[j] * (raise6sec_pgen[j] + raise6sec_pload[j]) + \
        # raise60sec_prices[j] * (raise60sec_pgen[j] + raise60sec_pload[j]) + \
        # raise5min_prices[j] * (raise5min_pgen[j] + raise5min_pload[j]) + \
        # raisereg_prices[j] * (raisereg_pgen[j] + raisereg_pload[j]) + \
        # lower6sec_prices[j] * (lower6sec_pgen[j] + lower6sec_pload[j]) + \
        # lower60sec_prices[j] * (lower60sec_pgen[j] + lower60sec_pload[j]) + \
        # lower5min_prices[j] * (lower5min_pgen[j] + lower5min_pload[j]) + \
        # lowerreg_prices[j] * (lowerreg_pgen[j] + lowerreg_pload[j])
        if j != 0:
            current_gen = energy_pgen[j - 1]
            current_load = energy_pload[j - 1]
            current_E = Epred[j - 1]
        model.addConstr(energy_pgen[j] <= current_gen + tstep * battery.gen_roc_up)
        model.addConstr(energy_pgen[j] >= current_gen - tstep * battery.gen_roc_down)
        model.addConstr(energy_pload[j] <= current_load + tstep * battery.load_roc_up)
        model.addConstr(energy_pload[j] >= current_load - tstep * battery.load_roc_down)
        # model.addConstr(raise6sec_pgen[j] <= max_cap - energy_pgen[j])
        # model.addConstr(raise60sec_pgen[j] <= max_cap - energy_pgen[j])
        # model.addConstr(raise5min_pgen[j] <= max_cap - energy_pgen[j])
        # model.addConstr(raisereg_pgen[j] <= max_cap - energy_pgen[j])
        # model.addConstr(lower6sec_pgen[j] <= energy_pgen[j])
        # model.addConstr(lower60sec_pgen[j] <= energy_pgen[j])
        # model.addConstr(lower5min_pgen[j] <= energy_pgen[j])
        # model.addConstr(lowerreg_pgen[j] <= energy_pgen[j])
        # model.addConstr(raise6sec_pload[j] <= energy_pload[j])
        # model.addConstr(raise60sec_pload[j] <= energy_pload[j])
        # model.addConstr(raise5min_pload[j] <= energy_pload[j])
        # model.addConstr(raisereg_pload[j] <= energy_pload[j])
        # model.addConstr(lower6sec_pload[j] >= max_cap - energy_pload[j])
        # model.addConstr(lower60sec_pload[j] >= max_cap - energy_pload[j])
        # model.addConstr(lower5min_pload[j] >= max_cap - energy_pload[j])
        # model.addConstr(lowerreg_pload[j] >= max_cap - energy_pload[j])
        model.addConstr(Epred[j] == current_E + tstep * (battery.eff * energy_pload[j] - energy_pgen[j]))
    model.addConstr(Epred[-1] >= battery.Emax * 0.5)
    model.setObjective(obj, gurobipy.GRB.MAXIMIZE)
    model.optimize()
    print([y.x for y in Epred])
    plot_forecasts(t, Epred, energy_prices, energy_times, p5min_energy_prices, p5min_times, predispatch_energy_prices, predispatch_times, battery)
    generate_forecasts(t, Epred, energy_prices, energy_times, p5min_energy_prices, p5min_times, predispatch_energy_prices, predispatch_times, battery)
    objs.append(model.objVal)
    energy_gen.append(energy_pgen[0].x)
    energy_load.append(energy_pload[0].x)
    # raise6sec_gen.append(raise6sec_pgen[0].x)
    # raise60sec_gen.append(raise60sec_pgen[0].x)
    # raise5min_gen.append(raise5min_pgen[0].x)
    # raisereg_gen.append(raisereg_pgen[0].x)
    # lower6sec_gen.append(lower6sec_pgen[0].x)
    # lower60sec_gen.append(lower60sec_pgen[0].x)
    # lower5min_gen.append(lower5min_pgen[0].x)
    # lowerreg_gen.append(lowerreg_pgen[0].x)
    # raise6sec_load.append(raise6sec_pload[0].x)
    # raise60sec_load.append(raise60sec_pload[0].x)
    # raise5min_load.append(raise5min_pload[0].x)
    # raisereg_load.append(raisereg_pload[0].x)
    # lower6sec_load.append(lower6sec_pload[0].x)
    # lower60sec_load.append(lower60sec_pload[0].x)
    # lower5min_load.append(lower5min_pload[0].x)
    # lowerreg_load.append(lowerreg_pload[0].x)
    E.append(Epred[0].x)


def generate_csv(time, battery):
    result_dir = battery.bat_dir / 'price_taker_{}_{}.csv'.format('forecast' if forecast_flag else 'predispatch',
                                                                  preprocess.get_case_date(time))
    with result_dir.open(mode='w') as f:
        writer = csv.writer(f, delimiter=',')
        writer.writerow(['No.',
                         'Datetime',
                         'Our Energy (MWh)',
                         'AEMO Energy (MWh)',
                         'Our Power (MW)',
                         'AEMO Dispatch Target',
                         # 'AEMO Actual Power (MW)',
                         'AEMO Price',
                         # 'AEMO Dispatch RRP',
                         # 'AEMO Revenue',
                         # 'AEMO Actual Revenue',
                         'Our Revenue',
                         'Our Objective'
                         ])
        for i in range(TOTAL_INTERVALS):
            writer.writerow([i,
                             times[i],
                             E[i],
                             E_record[i + 1] if battery.name == 'Dalrymple' else None,
                             energy_gen[i] - energy_load[i],
                             energy_gen_record[i] - energy_load_record[i],
                             # actual_gen_record[i + 1] - actual_load_record[i + 1],
                             period_rrp_record[i],
                             # interval_rrp_record[i],
                             # revenue_record[i],
                             # revenue_actual_record[i],
                             revenue[i],
                             objs[i]
                             ])
        writer.writerow(['Total',
                         '',  # Datetime
                         '',  # Our energy
                         '',  # AEMO energy
                         '',  # sum(energy_gen - energy_load),
                         '',  # sum(energy_gen_record - energy_load_record),
                         # sum(actual_gen_record[1:] - actual_gen_record[1:),
                         '',  # Spot price
                         # sum(interval_rrp_record),
                         # sum(revenue_record),
                         # sum(revenue_actual_record),
                         sum(revenue),
                         sum(objs)
                         ])


def plot_power(time, gen, load, gen_record, load_record, prices, name, results_dir):
    plt.figure()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
    plt.gca().xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))
    plt.plot(times, [gen[i] - load[i] for i in range(TOTAL_INTERVALS)], label=f'Our {name}')
    plt.plot(times, [gen_record[i] - load_record[i] for i in range(TOTAL_INTERVALS)], label=f'AEMO {name}')
    plt.plot(times, prices, label=f'{name} price')
    plt.xlabel('Interval')
    plt.ylabel('Power (MW)')
    plt.legend()
    plt.savefig(results_dir / f'{name}_{preprocess.get_case_date(time)}_{DAYS}')


def plot_revenue(time, results_dir):
    plt.figure()
    t = list(range(TOTAL_INTERVALS))
    plt.plot(t, revenue, label='Our Revenue')
    plt.plot(t, revenue_record, label='AEMO Revenue')
    # plt.plot(t, period_rrp_record, label='Energy price')
    # plt.plot(t, raise6sec_rrp_record, label='Raise6Sec price')
    # plt.plot(t, raise60sec_rrp_record, label='Raise60Sec price')
    # plt.plot(t, raise5min_rrp_record, label='Raise5Min price')
    # plt.plot(t, raisereg_rrp_record, label='RaiseReg price')
    # plt.plot(t, lower6sec_rrp_record, label='Lower6Sec price')
    # plt.plot(t, lower60sec_rrp_record, label='Lower60Sec price')
    # plt.plot(t, lower5min_rrp_record, label='Lower5Min price')
    # plt.plot(t, lowerreg_rrp_record, label='LowerReg price')
    plt.xlabel('Interval')
    plt.ylabel('Revenue')
    plt.legend()
    plt.savefig(results_dir / f'revenue_{preprocess.get_case_date(time)}_{DAYS}')


def plot_charge_level(time, results_dir):
    plt.figure()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
    plt.gca().xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))
    plt.plot(times, E, label='Our Charge Level')
    plt.plot(times, E_record[1:], label='AEMO Charge Level')
    plt.xlabel('Interval')
    plt.ylabel('Battery Charge Level (MWh)')
    plt.legend()
    plt.savefig(results_dir / f'battery_charge_level_{preprocess.get_case_date(time)}_{DAYS}')


def plot_forecasts(time, Epred, energy_prices, energy_times, p5min_energy_prices, p5min_times, predispatch_energy_prices, predispatch_times, battery):
    fig, ax1 = plt.subplots()
    # ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    # ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax1.set_xlabel('Datetime')
    col = 'tab:green'
    ax1.set_ylabel('Charge level (MWh)', color=col)
    ax1.plot(energy_times, [pred.x for pred in Epred], label='Charge level (MWh)', color=col)
    ax1.tick_params(axis='y', labelcolor=col)

    ax2 = ax1.twinx()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax2.set_ylabel('Price')
    # ax2.plot(energy_times, [price_dict[t] for t in energy_times], label='Actual price')
    ax2.plot(predispatch_times, predispatch_energy_prices, label='30min Predispatch')
    # ax2.plot(p5min_times, p5min_energy_prices, label='5min predispatch')
    ax2.plot(energy_times, energy_prices, label='Forecasting price')

    plt.legend()
    forecast_dir = battery.bat_dir / 'forecast'
    forecast_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(forecast_dir / preprocess.get_result_datetime(time + FIVE_MIN))
    plt.close(fig)


def generate_forecasts(time, Epred, energy_prices, energy_times, p5min_energy_prices, p5min_times, predispatch_energy_prices, predispatch_times, battery):
    forecast_csv = battery.bat_dir / 'forecast_csv'
    forecast_csv.mkdir(parents=True, exist_ok=True)
    with (forecast_csv / f'{preprocess.get_result_datetime(time + FIVE_MIN)}.csv').open(mode='w') as f:
        writer = csv.writer(f, delimiter=',')
        writer.writerow(['Datetime',
                         'Charge Level (MWh)',
                         'Forecasting Price',
                         'Actual Period',
                         'Actual Interval',
                         '5min Predispatch',
                         '30min Predispatch'])
        for i, (t, e, p) in enumerate(zip(energy_times, Epred, energy_prices)):
            writer.writerow([t,
                             e.x,
                             p,
                             price_dict[t],
                             interval_prices_dict.get(t),
                             p5min_energy_prices[i] if i < len(p5min_energy_prices) else None,
                             predispatch_energy_prices[predispatch_times.index(t)] if t in predispatch_times else None])
        writer.writerow(['Datetime', '30min Predispatch'])
        for t, p in zip(predispatch_times, predispatch_energy_prices):
            writer.writerow([t, p])
        writer.writerow(['Datetime', '5min Predispatch'])
        for t, p in zip(p5min_times, p5min_energy_prices):
            writer.writerow([t, p])


def plot_results(time, battery):
    fig, (ax1, ax3) = plt.subplots(2)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    # ax1.set_xlabel('Datetime')
    col1 = 'tab:green'
    ax1.set_ylabel('Period price', color=col1)
    ax1.plot(times, period_rrp_record, label='Period price ($/MWh)', color=col1)
    ax1.tick_params(axis='y', labelcolor=col1)

    ax2 = ax1.twinx()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    col2 = 'tab:orange'
    ax2.set_ylabel('Charge Level (MWh)', color=col2)
    ax2.plot(times, E, color=col2)
    ax2.tick_params(axis='y', labelcolor=col2)

    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax3.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax3.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax3.set_xlabel('Datetime')
    ax3.set_ylabel('Period price', color=col1)
    ax3.plot(times, period_rrp_record, label='Period price ($/MWh)', color=col1)
    ax3.tick_params(axis='y', labelcolor=col1)

    ax4 = ax3.twinx()
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax4.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax4.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    col3 = 'tab:blue'
    ax4.set_ylabel('Power (MW)', color=col3)
    ax4.plot(times, [energy_gen[i] - energy_load[i] for i in range(TOTAL_INTERVALS)], color=col3, label='Our result')
    ax4.plot(times, [energy_gen_record[i] - energy_load_record[i] for i in range(TOTAL_INTERVALS)], color='tab:red', label='AEMO record')
    ax4.tick_params(axis='y', labelcolor=col3)

    plt.legend()
    print(preprocess.get_case_date(time))
    plt.savefig(battery.bat_dir / '{}_eff={}_{}_{}'.format(battery.name,
                                                           int(battery.eff * 100),
                                                           'forecast' if forecast_flag else 'predispatch',
                                                           preprocess.get_case_date(time)))
    plt.close(fig)


def main(battery):
    time = datetime.datetime(2020, 9, 1, 4, 0, 0)
    if battery.name == 'Dalrymple':
        extract_e_record(time)  # Get E record
    for d in range(DAYS):
        extract_next_day_dispatch(time + d * ONE_DAY, battery)  # Get unit MW record
    extract_scada(time + datetime.timedelta(days=DAYS) + FIVE_MIN, battery)  # Get the last unit MW record
    rrp = None
    t = datetime.datetime(2020, 9, 1, 4, 0, 0)
    for i in range(TOTAL_INTERVALS * 2):
        if i % 6 == 0:
            rrp = extract_trading(t + THIRTY_MIN, battery.region)  # Get spot price for period
        price_dict[t + FIVE_MIN] = rrp
        interval_prices_dict[t + FIVE_MIN] = extract_dispatch(t + FIVE_MIN, battery.region)
        t += FIVE_MIN
    for i in range(TOTAL_INTERVALS):
        if i % 6 == 0:
            rrp = extract_trading(time + THIRTY_MIN, battery.region)  # Get spot price for period
        period_rrp_record.append(rrp)
        interval_rrp_record.append(extract_dispatch(time + FIVE_MIN, battery.region))  # Get energy price and FCAS get_prices for interval
        schedule(i, time, battery)
        times.append(time + FIVE_MIN)
        # revenue_actual_record.append(period_rrp_record[i] * (gen_mlf * actual_gen_record[i + 1] -
        #                                                      load_mlf * actual_load_record[i + 1]))
        revenue.append(rrp * (battery.gen_mlf * energy_gen[i] - battery.load_mlf * energy_load[i]) * tsteps[0]
                       # raise6sec_rrp_record[i] * (raise6sec_gen[i] + raise6sec_load[i]) +
                       # raise60sec_rrp_record[i] * (raise60sec_gen[i] + raise60sec_load[i]) +
                       # raise5min_rrp_record[i] * (raise5min_gen[i] + raise5min_load[i]) +
                       # raisereg_rrp_record[i] * (raisereg_gen[i] + raisereg_load[i]) +
                       # lower6sec_rrp_record[i] * (lower6sec_gen[i] + lower6sec_load[i]) +
                       # lower60sec_rrp_record[i] * (lower60sec_gen[i] + lower60sec_load[i]) +
                       # lower5min_rrp_record[i] * (lower5min_gen[i] + lower5min_load[i]) +
                       # lowerreg_rrp_record[i] * (lowerreg_gen[i] + lowerreg_load[i])
                       )
        time += FIVE_MIN
    # plot_charge_level(time)
    # plot_power(time, energy_gen, energy_load, energy_gen_record, energy_load_record, period_rrp_record, 'Energy')
    # plot_power(time, raise6sec_gen, raise6sec_load, raise6sec_gen_record, raise6sec_load_record, raise6sec_rrp_record, 'Raise6sec')
    # plot_power(time, raise60sec_gen, raise60sec_load, raise60sec_gen_record, raise60sec_load_record, raise60sec_rrp_record, 'Raise60sec')
    # plot_power(time, raise5min_gen, raise5min_load, raise5min_gen_record, raise5min_load_record, raise5min_rrp_record, 'Raise5min')
    # plot_power(time, raisereg_gen, raisereg_load, raisereg_gen_record, raisereg_load_record, raisereg_rrp_record, 'Raisereg')
    # plot_power(time, lower6sec_gen, lower6sec_load, lower6sec_gen_record, lower6sec_load_record, lower6sec_rrp_record, 'Lower6sec')
    # plot_power(time, lower60sec_gen, lower60sec_load, lower60sec_gen_record, lower60sec_load_record, lower60sec_rrp_record, 'Lower60sec')
    # plot_power(time, lower5min_gen, lower5min_load, lower5min_gen_record, lower5min_load_record, lower5min_rrp_record, 'Lower5min')
    # plot_power(time, lowerreg_gen, lowerreg_load, lowerreg_gen_record, lowerreg_load_record, lowerreg_rrp_record, 'Lowerreg')
    # plot_revenue(time)

    generate_csv(time, battery)
    plot_results(time, battery)


if __name__ == '__main__':
    logging.basicConfig(filename='price_taker.log', filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)
    main(Battery('Dalrymple'))
    # main(Battery('Hornsdale'))
    # main(Battery('Gannawarra'))
    # main(Battery('Ballarat'))
