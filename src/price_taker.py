from constrain import get_market_price
import csv
import datetime
import default
import dispatch
import gurobipy
import helpers
import json
import logging
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from offer import Unit, EnergyBid
import preprocess


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


def get_dispatch_prices(t, process, custom_flag, region, k=0, path_to_out=default.OUT_DIR, intervention='0'):
    if custom_flag:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'DISPATCHIS_{default.get_case_datetime(t)}.csv'
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


def get_p5min_prices(t, process, custom_flag, region, k=0, path_to_out=default.OUT_DIR, intervention='0'):
    if custom_flag:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'P5MIN_{default.get_case_datetime(t)}.csv'
        if not p.is_file() and k == 0:
            dispatch.get_all_dispatch(t, process)
    else:
        p = preprocess.download_5min_predispatch(t)
    p5min_times = []
    p5min_prices = []
    aemo_p5min_prices = []
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and row[7] == region and row[5] == intervention:
                p5min_times.append(default.extract_datetime(row[6]))
                p5min_prices.append(float(row[8]))
                if custom_flag:
                    aemo_p5min_prices.append(float(row[9]))
    return p5min_times, p5min_prices, aemo_p5min_prices


def get_predispatch_prices(t, process, custom_flag, region, k=0, path_to_out=default.OUT_DIR, intervention='0'):
    if custom_flag:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'PREDISPATCHIS_{default.get_case_datetime(t)}.csv'
        if not p.is_file():
            if k == 0:
                dispatch.get_all_dispatch(t, process)
    else:
        p = preprocess.download_predispatch(t)
    predispatch_times = []
    predispatch_prices = []
    aemo_predispatch_prices = []
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGION_PRICES' and row[6] == region and row[8] == intervention:
                predispatch_times.append(default.extract_datetime(row[28]))
                predispatch_prices.append(float(row[9]))
                aemo_predispatch_prices.append(float(row[10]))
    return predispatch_times, predispatch_prices, aemo_predispatch_prices


def get_prices(t, process, custom_flag, region, k=0, path_to_out=default.OUT_DIR, intervention='0'):
    price_func = {'dispatch': get_dispatch_prices,
                  'p5min': get_p5min_prices,
                  'predispatch': get_predispatch_prices}
    func = price_func.get(process)
    return func(t, process, custom_flag, region, k, path_to_out, intervention)


def get_predispatch_time(t):
    if t.minute == 0:
        return t
    elif t.minute <= 30:
        return datetime.datetime(t.year, t.month, t.day, t.hour, 30)
    else:
        return datetime.datetime(t.year, t.month, t.day, t.hour + 1, 0)


def preprocess_prices(current, custom_flag, battery, k):
    path_to_out = default.OUT_DIR if k == 0 else battery.bat_dir
    p5min_times, p5min_prices, aemo_p5min_prices = get_prices(current, 'p5min', custom_flag,
                                                              battery.generator.region_id, k, path_to_out)
    predispatch_time = get_predispatch_time(current)
    predispatch_times, predispatch_prices, aemo_predispatch_prices = get_prices(predispatch_time, 'predispatch',
                                                                                custom_flag,
                                                                                battery.generator.region_id, k,
                                                                                path_to_out)
    predispatch_prices = predispatch_prices[2:]
    predispatch_times = predispatch_times[2:]
    return p5min_times, predispatch_times, p5min_prices, predispatch_prices, predispatch_time, aemo_p5min_prices, aemo_predispatch_prices


def get_reminder(i):
    return 5 * (6 - (i % 6))


def customise_unit(current, gen, load, battery, voll=None, market_price_floor=None):
    if gen + load == 0:
        return None
    unit = battery.generator if gen > load else battery.load
    unit.total_cleared = 0.0
    unit.offers = []
    unit.initial_mw = 0
    unit.energy = EnergyBid([])
    if voll is None or market_price_floor is None:
        voll, market_price_floor = get_market_price(current)
    unit.energy.price_band = [market_price_floor, -market_price_floor]
    unit.energy.band_avail = [gen, load]
    unit.energy.fixed_load = 0
    unit.energy.max_avail = unit.max_capacity
    unit.energy.daily_energy_limit = 0
    unit.energy.roc_up = 1000
    unit.energy.roc_down = 1000
    return unit


def plot_forecasts(custom_flag, time, item, labels, times, energy_prices, aemo_energy_prices, battery, middle, k=0):
    fig, ax1 = plt.subplots()
    # ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    # ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax1.set_xlabel('Datetime')
    # col = 'tab:green'
    ax1.set_ylabel(labels, color='tab:orange')
    ax1.plot(times, item, label=labels, color='tab:orange')
    ax1.tick_params(axis='y', labelcolor='tab:orange')
    if middle is not None:
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
    if custom_flag and aemo_energy_prices is not None:
        ax2.plot(times, aemo_energy_prices, label='AEMO Predispatch Price', color='tab:green')

    plt.legend()
    forecast_dir = battery.bat_dir / ('forecast' if k == 0 else f'forecast_{k}')
    forecast_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(forecast_dir / f'{labels} {default.get_result_datetime(time)}')
    plt.close(fig)


def write_forecasts(current, soc, times, prices, pgen, pload, pt, T1, T2, battery_dir, k=0):
    forecast_dir = battery_dir / ('forecast' if k == 0 else f'forecast_{k}')
    forecast_dir.mkdir(parents=True, exist_ok=True)
    result_dir = forecast_dir / f'{default.get_case_datetime(current)}.csv'
    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['I', 'Time', 'Price', 'Generation', 'Load', 'SOC', default.get_interval_datetime(pt)])
        for j, (s, t, p, g, l) in enumerate(zip(soc, times, prices, pgen, pload)):
            process_type = 'PREDISPATCH' if T1 <= j < T1 + T2 or j >= 2 * T1 + T2 else 'P5MIN'
            writer.writerow([process_type, default.get_interval_datetime(t), p, g.x, l.x, s.x])


def read_forecasts(current, battery_dir, k):
    result_dir = battery_dir / ('forecast' if k == 0 else f'forecast_{k}') / f'{default.get_case_datetime(current)}.csv'
    p5min_pgen = {}
    p5min_pload = {}
    predispatch_pgen = {}
    predispatch_pload = {}
    with result_dir.open(mode='r') as result_file:
        reader = csv.reader(result_file)
        for row in reader:
            if row[0] == 'I':
                pt = default.extract_datetime(row[6])
            else:
                pgen = p5min_pgen if row[0] == 'P5MIN' else predispatch_pgen
                pload = p5min_pload if row[0] == 'P5MIN' else predispatch_pload
                pgen[default.extract_datetime(row[1])] = float(row[3])
                pload[default.extract_datetime(row[1])] = float(row[4])
    return p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, pt


def dispatch_with_bids(current, battery, k):
    voll, market_price_floor = get_market_price(current)
    p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, predispatch_time = read_forecasts(current, battery.bat_dir, k - 1)
    for j in range(helpers.get_total_intervals('p5min')):
        t = current + j * default.FIVE_MIN
        if t >= datetime.datetime(2020, 9, 1, 4, 55) or True:
            unit = customise_unit(current, p5min_pgen[t], p5min_pload[t], battery, voll, market_price_floor)
            dispatch.dispatch(start=current, interval=j, process='p5min', iteration=k, custom_unit=unit, path_to_out=battery.bat_dir)
    for j in range(helpers.get_total_intervals('predispatch', predispatch_time)):
        t = predispatch_time + j * default.THIRTY_MIN
        if t >= datetime.datetime(2020, 9, 1, 5, 30) or True:
            gen = predispatch_pgen.get(t, None)
            if gen is None:
                gen = p5min_pgen[t - default.TWENTYFIVE_MIN]
                load = p5min_pload[t - default.TWENTYFIVE_MIN]
            else:
                load = predispatch_pload[t]
            unit = customise_unit(current, gen, load, battery, voll, market_price_floor)
            dispatch.dispatch(start=predispatch_time, interval=j, process='predispatch', iteration=k, custom_unit=unit, path_to_out=battery.bat_dir)


def schedule(current, battery, custom_flag=True, double_flag=True, i=0, k=0):
    model = gurobipy.Model(f'price_taker_{i}')
    p5min_times, predispatch_times, p5min_prices, predispatch_prices, predispatch_time, aemo_p5min_prices, aemo_predispatch_prices = preprocess_prices(current, custom_flag, battery, k)
    middle = predispatch_times[-1] if double_flag else None
    prices = (p5min_prices + predispatch_prices) * (2 if double_flag else 1)
    times = p5min_times + predispatch_times + ([t + default.ONE_DAY for t in p5min_times] + [t + default.ONE_DAY for t in predispatch_times] if double_flag else [])
    remainder = get_reminder(i)
    T1 = len(p5min_prices)
    T2 = len(predispatch_prices)
    T = (T1 + T2) * (2 if double_flag else 1)
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
    plot_forecasts(custom_flag, current, [soc[j].x * 100 for j in range(T)], 'State of Charge (%)', times, prices, (aemo_p5min_prices + aemo_predispatch_prices[2:]) * (2 if double_flag else 1), battery, middle, k=k)
    plot_forecasts(custom_flag, current, [energy_pgen[j].x - energy_pload[j].x for j in range(T)], 'Power (MW)', times, prices, (aemo_p5min_prices + aemo_predispatch_prices[2:]) * (2 if double_flag else 1), battery, middle, k=k)
    write_forecasts(current, soc, times, prices, energy_pgen, energy_pload, predispatch_time, T1, T2, battery.bat_dir, k)
    return energy_pgen[0].x, energy_pload[0].x


def extract_prices(current, battery, k):
    p5min_times, predispatch_times, p5min_prices, predispatch_prices, _, _, _ = preprocess_prices(current, True, battery, k)
    return p5min_times + predispatch_times, p5min_prices + predispatch_prices


def extract_forecasts(current, battery, k):
    p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, _ = read_forecasts(current, battery.bat_dir, k)
    return list(p5min_pgen.keys()) + list(predispatch_pgen.keys()), [p5min_pgen[t] - p5min_pload[t] for t in p5min_pgen.keys()] + [predispatch_pgen[t] - predispatch_pload[t] for t in predispatch_pgen.keys()]


def plot_comparison(current, battery, extract_func, ylabel, k_range):
    fig, ax1 = plt.subplots()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax1.set_xlabel('Datetime')
    # col = 'tab:green'
    ax1.set_ylabel(ylabel)
    ax1.tick_params(axis='y')

    for k in k_range:
        times, items = extract_func(current, battery, k)
        ax1.plot(times, items, label=f'k = {k}')

    plt.legend()
    plt.savefig(battery.bat_dir / f'{ylabel} {battery.Emax}MWh {battery.generator.max_capacity}MW {default.get_result_datetime(current)}')
    plt.close(fig)


def plot_battery_comparison(current, extract_func, ylabel, k):
    fig, ax1 = plt.subplots()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax1.set_xlabel('Datetime')
    # col = 'tab:green'
    ax1.set_ylabel(ylabel)
    ax1.tick_params(axis='y')

    for e, p in zip([65, 429, 1000], [50, 200, 500]):
        battery = Battery('Battery', e, p)
        times, items = extract_func(current, battery, k)
        ax1.plot(times, items, label=f'{battery.Emax}MWh {battery.generator.max_capacity}MW')

    plt.legend()
    plt.savefig(default.OUT_DIR / f'{ylabel} k = {k} {default.get_result_datetime(current)}')
    plt.close(fig)


def test_batteries(current):
    result_dir = default.OUT_DIR / f'Battery_{default.get_case_datetime(current)}.csv'
    with result_dir.open('w') as f:
        writer = csv.writer(f)
        writer.writerow(
            ['Battery Size(MWh)', 'Max Capacity (MW)', 'Type', 'Price Taker Bid (MW)', 'NSW1', 'QLD1', 'SA1', 'TAS1',
             'VIC1'])
        prices = dispatch.dispatch(start=current, interval=0, process='dispatch')
        writer.writerow([0, 0, '', 0] + [prices[r] for r in ['NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']])
    for e, p in zip([12, 65, 129, 429, 1000, 2800, 4000], [30, 50, 100, 200, 500, 700, 1000]):
        battery = Battery('Battery', e, p)
        gen, load = schedule(current, battery)
        if gen + load > 0:
            unit = customise_unit(current, gen, load, battery)
            dispatch.dispatch(start=current, interval=0, process='dispatch', custom_unit=unit, path_to_out=battery.bat_dir)
        else:
            with result_dir.open('a') as f:
                writer = csv.writer(f)
                writer.writerow([e, p, '', '0'])


if __name__ == '__main__':
    t = datetime.datetime(2020, 9, 1, 4, 5)
    path_to_log = default.LOG_DIR / f'price_taker_{default.get_case_datetime(t)}.log'
    logging.basicConfig(filename=path_to_log, filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)
    # b = Battery('Battery', 65, 50)
    # plot_prices_comparison(t, b)
    # for e, p in zip([65, 429, 1000], [50, 200, 500]):
    #     b = Battery('Battery', e, p)
    #     # schedule(t, b, custom_flag=True, double_flag=False, i=0, k=0)
    #     # for k in range(1, 5):
    #     #     dispatch_with_bids(t, b, k=k)
    #     #     schedule(t, b, custom_flag=True, double_flag=False, i=0, k=k)
    #     plot_comparison(t, b, extract_forecasts, 'Forecast', range(5))
    for k in range(5):
        plot_battery_comparison(t, extract_prices, 'Price', k)
        plot_battery_comparison(t, extract_forecasts, 'Forecast', k)



