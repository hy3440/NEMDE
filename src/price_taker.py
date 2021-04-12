from constrain import get_market_price
import csv
import datetime
import default
from dispatch import get_dispatch
import gurobipy
import json
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from offer import Unit, EnergyBid
import preprocess

intervention = '0'


def get_cycles(dod):
    """ Battery degradation model from paper Duggal2015Short. """
    return 1591.1 * pow(dod, -2.089)


def get_degradations(x):
    """ Convert number of cycles versus DoD to degradation percentage versus SoC (see paper Ying2016Stochastic). """
    return 1 / get_cycles(1 - x)


# relationship between number of cycles and DoD (see paper Omar2014Lithium)
dods = [20, 40, 60, 80, 100]
cycles = [34957, 19985, 10019, 3221, 2600]
socs = [0.8, 0.6, 0.2, 0]
degradations = [1 / 34957, 1 / 19985, 1 / 10019, 1 / 3221, 1 / 2600]
# socs = [k / 100 for k in range(0, 100, 5)]
# degradations = [get_degradations(s) for s in socs]


class Battery:
    def __init__(self, name, e, p):
        self.name = name
        self.data = self.read_data()
        self.generator = Unit(self.data['gen_id'])
        self.generator.dispatch_type = 'GENERATOR'
        self.generator.dispatch_mode = 0
        self.generator.region_id = self.data['region']
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
        self.load.region_id = self.data['region']
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
        self.bat_dir = default.OUT_DIR / f'{name} {self.Emax}MWh {self.generator.max_capacity}MW'
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
            return data[self.name]


def get_dispatch_prices(t, process, custom_flag, region, intervention):
    if custom_flag:
        p = preprocess.OUT_DIR / process / f'DISPATCHIS_{preprocess.get_case_datetime(t)}.csv'
    else:
        p = preprocess.download_dispatch_summary(t)
    with p.open() as f:
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


def get_p5min_prices(t, process, custom_flag, region, intervention):
    if custom_flag:
        p = preprocess.OUT_DIR / process / f'P5MIN_{preprocess.get_case_datetime(t)}.csv'
        if not p.is_file():
            get_dispatch(t, process)
    else:
        p = preprocess.download_5min_predispatch(t)
    p5min_times = []
    p5min_prices = []
    aemo_p5min_prices = []
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and row[7] == region and row[5] == intervention:
                p5min_times.append(preprocess.extract_datetime(row[6]))
                p5min_prices.append(float(row[8]))
                if custom_flag:
                    aemo_p5min_prices.append(float(row[9]))
    return p5min_times, p5min_prices, aemo_p5min_prices


def get_predispatch_prices(t, process, custom_flag, region, intervention):
    if custom_flag:
        p = preprocess.OUT_DIR / process / f'PREDISPATCHIS_{preprocess.get_case_datetime(t)}.csv'
        if not p.is_file():
            get_dispatch(t, process)
    else:
        p = preprocess.download_predispatch(t)
    predispatch_times = []
    predispatch_prices = []
    aemo_predispatch_prices = []
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGION_PRICES' and row[6] == region and row[8] == intervention:
                predispatch_times.append(preprocess.extract_datetime(row[28]))
                predispatch_prices.append(float(row[9]))
                aemo_predispatch_prices.append(float(row[10]))
    return predispatch_times, predispatch_prices, aemo_predispatch_prices


def get_prices(t, process, custom_flag, region, intervention):
    price_func = {'dispatch': get_dispatch_prices,
                  'p5min': get_p5min_prices,
                  'predispatch': get_predispatch_prices}
    func = price_func.get(process)
    return func(t, process, custom_flag, region, intervention)


def get_predispatch_time(t):
    if t.minute == 0:
        return t
    elif t.minute <= 30:
        return datetime.datetime(t.year, t.month, t.day, t.hour, 30)
    else:
        return datetime.datetime(t.year, t.month, t.day, t.hour + 1, 0)


def get_reminder(i):
    return 5 * (6 - (i % 6))


def plot_forecasts(custom_flag, time, item, labels, times, energy_prices, aemo_energy_prices, battery, middle):
    fig, ax1 = plt.subplots()
    # ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    # ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax1.set_xlabel('Datetime')
    # col = 'tab:green'
    ax1.set_ylabel(labels, color='tab:orange')
    ax1.plot(times, item, label=labels, color='tab:orange')
    ax1.tick_params(axis='y', labelcolor='tab:orange')
    plt.axvline(middle, 0, 100, c="r")

    ax2 = ax1.twinx()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=8))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax2.set_ylabel('Price', color='b')
    # ax2.plot(energy_times, [price_dict[t] for t in energy_times], label='Actual price')
    # ax2.plot(predispatch_times, predispatch_energy_prices, label='30min Predispatch')
    # ax2.plot(p5min_times, p5min_energy_prices, label='5min predispatch')
    ax2.plot(times, energy_prices, label='Our Predispatch Price', color='tab:blue')
    if custom_flag:
        ax2.plot(times, aemo_energy_prices, label='AEMO Predispatch Price', color='tab:green')


    plt.legend()
    forecast_dir = battery.bat_dir / 'forecast'
    forecast_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(forecast_dir / f'{labels} {preprocess.get_result_datetime(time)}')
    plt.close(fig)


def schedule(current, i, custom_flag, battery):
    model = gurobipy.Model(f'price_taker_{i}')
    p5min_times, p5min_prices, aemo_p5min_prices = get_prices(current, 'p5min', custom_flag, battery.generator.region_id, intervention)
    predispatch_time = get_predispatch_time(current)
    remainder = get_reminder(i)
    predispatch_times, predispatch_prices, aemo_predispatch_prices = get_prices(predispatch_time, 'predispatch', custom_flag, battery.generator.region_id, intervention)
    predispatch_prices = predispatch_prices[2:]
    predispatch_times = predispatch_times[2:]
    middle = predispatch_times[-1]
    prices = p5min_prices + predispatch_prices + p5min_prices + predispatch_prices
    times = p5min_times + predispatch_times + [t + default.ONE_DAY for t in p5min_times] + [t + default.ONE_DAY for t in predispatch_times]
    T1 = len(p5min_prices)
    T2 = len(predispatch_prices)
    T = (T1 + T2) * 2
    tstep = 5 / 60
    cost = 20  # Operation cost ($/MWh)
    fee = 300000  # Replacement fee ($/MWh) used for battery degradation model
    obj = 0

    # Battery variables
    soc = [model.addVar(ub=1.0, name=f'SOC_{j}') for j in range(T)]
    E = [soc[j] * battery.Emax for j in range(T)]
    energy_pgen = [model.addVar(ub=battery.generator.max_capacity, name=f'energy_pgen_{j}') for j in range(T)]
    energy_pload = [model.addVar(ub=battery.load.max_capacity, name=f'energy_pload_{j}') for j in range(T)]
    degradation = [model.addVar(name=f'degradation_{j}') for j in range(T)]

    # Constraints
    model.addConstr(E[0], gurobipy.GRB.EQUAL, 0.5 * battery.Emax + tstep * (energy_pload[0] * battery.eff - energy_pgen[0] / battery.eff), 'TRANSITION_0')
    model.addConstr(E[T - 1] >= 0.5 * battery.Emax)
    for j in range(T):
        # # Battery degradation model (see paper Ying2016Stochastic)
        # alpha = [model.addVar(name=f'alpha_{j}_{k}') for k in range(len(socs))]
        # model.addConstr(soc[j], gurobipy.GRB.EQUAL, sum([s * a for s, a in zip(socs, alpha)]))
        # model.addConstr(degradation[j], gurobipy.GRB.EQUAL, sum([d * a for d, a in zip(degradations, alpha)]))
        # model.addConstr(sum(alpha), gurobipy.GRB.EQUAL, 1)
        # model.addSOS(gurobipy.GRB.SOS_TYPE2, alpha)
        # # Method 1: Add degradation constraint
        # model.addConstr(degradation[j] <= 1 / 10 / 365)
        # # Method 2: Add degradation cost to objective function
        # obj -= fee * degradation[j] * battery.Emax

        # Objective
        obj += prices[j] * (battery.generator.transmission_loss_factor * energy_pgen[
            j] - battery.load.transmission_loss_factor * energy_pload[j]) * tstep
        # Add operational cost to objective function
        obj -= (energy_pgen[j] + energy_pload[j]) * tstep * cost

        model.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[energy_pgen[j], energy_pload[j]])
        if times[j].hour == 4 and times[j].minute == 0:
            model.addConstr(E[j] >= battery.Emax * 0.5)
        if j == T1 or j == T1 + T2 + T1:
            tstep = remainder / 60
        elif T1 < j < T1 + T2 or j > 2 * T1 + T2:
            tstep = 30 / 60
        else:
            tstep = 5 / 60
        if j >= 1:
            model.addConstr(E[j], gurobipy.GRB.EQUAL, E[j - 1] + tstep * (energy_pload[j] * battery.eff - energy_pgen[j] / battery.eff), f'TRANSITION_{j}')
            model.addConstr(energy_pgen[j] <= energy_pgen[j - 1] + tstep * battery.generator.ramp_up_rate / 60)
            model.addConstr(energy_pgen[j] >= energy_pgen[j - 1] - tstep * battery.generator.ramp_down_rate / 60)
            model.addConstr(energy_pload[j] <= energy_pload[j - 1] + tstep * battery.load.ramp_up_rate / 60)
            model.addConstr(energy_pload[j] >= energy_pload[j - 1] - tstep * battery.load.ramp_up_rate / 60)

    # Optimise
    model.setObjective(obj, gurobipy.GRB.MAXIMIZE)
    model.optimize()
    # Plot results
    plot_forecasts(custom_flag, current, [soc[j].x * 100 for j in range(T)], 'State of Charge (%)', times, prices, (aemo_p5min_prices + aemo_predispatch_prices[2:]) * 2, battery, middle)
    plot_forecasts(custom_flag, current, [energy_pgen[j].x - energy_pload[j].x for j in range(T)], 'Power (MW)', times, prices, (aemo_p5min_prices + aemo_predispatch_prices[2:]) * 2, battery, middle)
    # for j in range(T1 + T2):
    #     print(f'{(p5min_times + predispatch_times)[j]} Gen {energy_pgen[j].x} Load {energy_pload[j].x} Price {(p5min_prices + predispatch_prices)[j]}')
    return energy_pgen[0].x, energy_pload[0].x


if __name__ == '__main__':
    current = datetime.datetime(2020, 9, 1, 4, 5)
    result_dir = preprocess.OUT_DIR / f'Battery_{preprocess.get_case_datetime(current)}.csv'
    with result_dir.open('w') as f:
        writer = csv.writer(f)
        writer.writerow(['Battery Size(MWh)', 'Max Capacity (MW)', 'Type', 'Price Taker Bid (MW)', 'NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1'])
        prices = get_dispatch(current, 'dispatch', None)
        writer.writerow([0, 0, '', 0] + [prices[r] for r in ['NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']])
    for e, p in zip([12, 65, 129, 429, 1000, 2800, 4000], [30, 50, 100, 200, 500, 700, 1000]):
        battery = Battery('Battery', e, p)
        pgen, pload = schedule(current, 0, True, battery)
        if pgen + pload > 0:
            unit = battery.generator if pgen > pload else battery.load
            unit.energy = EnergyBid([])
            voll, market_price_floor = get_market_price(current)
            unit.energy.price_band = [market_price_floor if pgen > pload else -market_price_floor]
            unit.energy.band_avail = [pgen if pgen > pload else pload]
            unit.energy.fixed_load = 0
            unit.energy.max_avail = unit.max_capacity
            get_dispatch(current, 'dispatch', unit)
        else:
            with result_dir.open('a') as f:
                writer = csv.writer(f)
                writer.writerow([e, p, '', '0'])


