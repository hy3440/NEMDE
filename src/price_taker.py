from constrain import get_market_price
import csv
import datetime
import default
import dispatch
import gurobipy as gp
import helpers
import logging
from offer import EnergyBid
import plot
import read
import traceback
import write
from helpers import Battery


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


def phi(dod):
    return 5.24E-4 * pow(dod, 2.03)


def marginal_costs(R, eff, M, m):
    return R * M * (phi(m / M) - phi((m - 1) / M)) / eff


def get_predispatch_time(t):
    if t.minute == 0:
        return t
    elif t.minute <= 30:
        return datetime.datetime(t.year, t.month, t.day, t.hour, 30)
    else:
        return (t + default.ONE_HOUR).replace(minute=0)


def preprocess_prices(current, custom_flag, battery, k):
    path_to_out = default.OUT_DIR if k == 0 else battery.bat_dir
    p5min_times, p5min_prices, aemo_p5min_prices, p5min_fcas_prices, aemo_p5min_fcas_prices = read.read_prices(current, 'p5min', custom_flag,
                                                               battery.generator.region_id, k, path_to_out)
    predispatch_time = get_predispatch_time(current)
    predispatch_times, predispatch_prices, aemo_predispatch_prices, predispatch_fcas_prices, aemo_predispatch_fcas_prices = read.read_prices(predispatch_time, 'predispatch',
                                                                                 custom_flag,
                                                                                 battery.generator.region_id, k,
                                                                                 path_to_out)
    return p5min_times, predispatch_times[2:], p5min_prices, predispatch_prices[2:], predispatch_time, aemo_p5min_prices, aemo_predispatch_prices[2:]


def extend_forcast_horizon(current, times, prices, aemo_prices, custom_flag, battery, k):
    path_to_out = default.OUT_DIR if k == 0 else battery.bat_dir
    end_time = current + default.ONE_DAY - default.FIVE_MIN
    extend_time = end = times[-1]
    if extend_time < end_time:
        # 30min-based
        # while end_time - extend_time > default.THIRTY_MIN:
        #     extend_time += default.THIRTY_MIN
        #     price, _ = read.read_trading_prices(extend_time - default.ONE_DAY, custom_flag, battery.load.region_id, k, path_to_out)
        #     aemo_price, _ = read.read_trading_prices(extend_time, False, battery.load.region_id)
        #     prices.append(price)
        #     aemo_prices.append(aemo_price)
        #     times.append(extend_time)
        # 5min-based
        while extend_time < end_time:
            extend_time += default.FIVE_MIN
            price, aemo_price, _, _ = read.read_dispatch_prices(extend_time - default.ONE_DAY, 'dispatch', custom_flag,
                                                                battery.load.region_id, k, path_to_out)
            prices.append(price)
            aemo_prices.append(aemo_price)
            times.append(extend_time)
    elif extend_time > end_time:
        while extend_time >= end_time + default.THIRTY_MIN:
            times.pop()
            prices.pop()
            aemo_prices.pop()
            extend_time = times[-1]
        # times[-1] = min(extend_time, end_time)
        end = None
    return times, prices, aemo_prices, end


def extend_forcast_horizon_new(current, times, prices, aemo_prices, custom_flag, battery, k):
    path_to_out = default.OUT_DIR if k == 0 else battery.bat_dir
    end_time = current + default.ONE_DAY - default.FIVE_MIN
    extend_time = end = times[-1]
    print(f'end {end_time}')
    print(f'extend {extend_time}')
    if extend_time < end_time:
        # 30min-based
        # while end_time - extend_time > default.THIRTY_MIN:
        #     extend_time += default.THIRTY_MIN
        #     price, _ = read.read_trading_prices(extend_time - default.ONE_DAY, custom_flag, battery.load.region_id, k, path_to_out)
        #     aemo_price, _ = read.read_trading_prices(extend_time, False, battery.load.region_id)
        #     prices.append(price)
        #     aemo_prices.append(aemo_price)
        #     times.append(extend_time)
        # 5min-based
        while extend_time <= end_time:
            extend_time += default.FIVE_MIN
            price, aemo_price, _, _ = read.read_dispatch_prices(extend_time - default.ONE_DAY, 'dispatch', custom_flag, battery.load.region_id, k, path_to_out)
            prices.append(price)
            aemo_prices.append(aemo_price)
            times.append(extend_time)
    elif extend_time > end_time:
        while extend_time >= end_time + default.THIRTY_MIN:
            times.pop()
            prices.pop()
            aemo_prices.pop()
            extend_time = times[-1]
        times[-1] = min(extend_time, end_time)
        end = None
    return times, prices, aemo_prices, end


def process_prices_by_interval(current, custom_flag, battery, k):
    p5min_times, predispatch_times, p5min_prices, predispatch_prices, predispatch_time, aemo_p5min_prices, aemo_predispatch_prices = preprocess_prices(current, custom_flag, battery, k)
    times, prices, aemo_prices, end = extend_forcast_horizon(current, p5min_times + predispatch_times, p5min_prices + predispatch_prices, aemo_p5min_prices + aemo_predispatch_prices, custom_flag, battery, k)
    return times, prices, p5min_prices, predispatch_prices, predispatch_time, aemo_prices, end


def process_prices_by_interval_new(current, custom_flag, battery, k, p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices):
    predispatch_times, predispatch_prices, aemo_predispatch_prices = predispatch_times[2:], predispatch_prices[2:], aemo_predispatch_prices[2:]
    predispatch_time = get_predispatch_time(current)
    times, prices, aemo_prices, end = extend_forcast_horizon(current, p5min_times + predispatch_times, p5min_prices + predispatch_prices, aemo_p5min_prices + aemo_predispatch_prices, custom_flag, battery, k)
    return times, prices, p5min_prices, predispatch_prices, predispatch_time, aemo_prices, end


def process_prices_by_period(current, horizon, custom_flag, battery, k):
    r = horizon % 6
    p5min_times, predispatch_times, p5min_prices, predispatch_prices, predispatch_time, aemo_p5min_prices, aemo_predispatch_prices = preprocess_prices(current, custom_flag, battery, k)
    times = p5min_times + predispatch_times
    price1 = sum([read.read_dispatch_prices(current - n * default.FIVE_MIN, 'dispatch', custom_flag, battery.generator.region_id, k=0, path_to_out=default.OUT_DIR)[0] for n in range(1, r + 1)] + p5min_prices[:6-r]) / 6
    aemo_price1 = sum([read.read_dispatch_prices(current - n * default.FIVE_MIN, 'dispatch', custom_flag, battery.generator.region_id, k=0, path_to_out=default.OUT_DIR)[1] for n in range(1, r + 1)] + aemo_p5min_prices[:6-r]) / 6
    price2 = sum(p5min_prices[6 - r: 12 - r]) / 6
    aemo_price2 = sum(aemo_p5min_prices[6 - r: 12 - r]) / 6
    price3 = (sum(p5min_prices[-r:]) + (6 - r) * predispatch_prices[0]) / 6
    aemo_price3 = (sum(aemo_p5min_prices[-r:]) + (6 - r) * predispatch_prices[0]) / 6
    prices = [price1] * (6 - r) + [price2] * 6 + [price3] * (r + 1) + predispatch_prices[1:]
    aemo_prices = [aemo_price1] * (6 - r) + [aemo_price2] * 6 + [aemo_price3] * (r + 1) + aemo_predispatch_prices[1:]
    times, prices, aemo_prices, end = extend_forcast_horizon(current, times, prices, aemo_prices, custom_flag, battery, k)
    return times, prices, p5min_prices, predispatch_prices, predispatch_time, aemo_prices, end


def schedule(current, battery, p5min_times=None, p5min_prices=None, aemo_p5min_prices=None, predispatch_times=None, predispatch_prices=None, aemo_predispatch_prices=None, custom_flag=True, horizon=None, k=0, E_initial=None, method=None):
    tstep = 5 / 60
    cost = 20  # Operation cost ($/MWh)
    fee = 300000  # Replacement fee ($/MWh) used for battery degradation model
    obj = 0
    SOC_MIN = 0
    SOC_MAX = 1
    horizon = default.datetime_to_interval(current)[1] - 1 if horizon is None else horizon

    M = 16  # Number of segments
    R = 300000  # Replacement cost ($/MWh)
    if p5min_times is None:
        times, prices, p5min_prices, predispatch_prices, predispatch_time, aemo_prices, end = process_prices_by_interval(current, custom_flag, battery, k)
        # times, prices, p5min_prices, predispatch_prices, predispatch_time, aemo_prices, end = process_prices_by_period(current, horizon, custom_flag, battery, k)
    else:
        times, prices, p5min_prices, predispatch_prices, predispatch_time, aemo_prices, end = process_prices_by_interval_new(current, custom_flag, battery, k, p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices)

    remainder = horizon % 6
    T1 = len(p5min_prices)
    T2 = len(predispatch_prices)
    T = len(prices)
    with gp.Env() as env, gp.Model(env=env, name=f'price_taker_{battery.name}_{horizon}') as model:
        model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
        # Battery variables
        soc = [model.addVar(lb=SOC_MIN, ub=SOC_MAX, name=f'SOC_{j}') for j in range(T)]
        E = [soc[j] * battery.Emax for j in range(T)]
        energy_pgen = [model.addVar(ub=battery.generator.max_capacity, name=f'energy_pgen_{j}') for j in range(T)]
        energy_pload = [model.addVar(ub=battery.load.max_capacity, name=f'energy_pload_{j}') for j in range(T)]
        degradation = [model.addVar(name=f'degradation_{j}') for j in range(T)]
        # Constraints
        model.addLConstr(E[0], gp.GRB.EQUAL, (0.5 * battery.Emax if horizon == 0 or E_initial is None else E_initial) + tstep * (energy_pload[0] * battery.eff - energy_pgen[0] / battery.eff), 'TRANSITION_0')
        model.addLConstr(E[T - 1], gp.GRB.EQUAL, E[0], 'FINAL_STATE')
        for j in range(T):
            # Charge or discharge
            model.addSOS(type=gp.GRB.SOS_TYPE1, vars=[energy_pgen[j], energy_pload[j]])
            # Different length of forecast horizon
            if j == T1:
                tstep = (6 - remainder) * 5 / 60
            # 30min-based
            # elif remainder != 0 and j == T - 1:
            #     tstep = remainder * 5 / 60
            # elif T1 < j:
            elif T1 < j < T1 + T2:
                tstep = 30 / 60
            else:
                tstep = 5 / 60
            # Transition between horizons
            if j >= 1:
                model.addLConstr(E[j], gp.GRB.EQUAL, E[j - 1] + tstep * (energy_pload[j] * battery.eff - energy_pgen[j] / battery.eff), f'TRANSITION_{j}')
                # model.addLConstr(energy_pgen[j] <= energy_pgen[j - 1] + tstep * battery.generator.ramp_up_rate / 60)
                # model.addLConstr(energy_pgen[j] >= energy_pgen[j - 1] - tstep * battery.generator.ramp_down_rate / 60)
                # model.addLConstr(energy_pload[j] <= energy_pload[j - 1] + tstep * battery.load.ramp_up_rate / 60)
                # model.addLConstr(energy_pload[j] >= energy_pload[j - 1] - tstep * battery.load.ramp_up_rate / 60)
            # Objective
            obj += prices[j] * (battery.generator.transmission_loss_factor * energy_pgen[j] - battery.load.transmission_loss_factor * energy_pload[j]) * tstep
            # Method 0: Add operational cost to objective function
            if method == 0:
                obj -= (energy_pgen[j] + energy_pload[j]) * tstep * cost
            # Method 1: Battery degradation model (see paper Ying2016Stochastic)
            elif method == 1:
                alpha = [model.addVar(name=f'alpha_{j}_{k}') for k in range(len(socs))]
                model.addLConstr(soc[j], gp.GRB.EQUAL, sum([s * a for s, a in zip(socs, alpha)]))
                model.addLConstr(degradation[j], gp.GRB.EQUAL, sum([d * a for d, a in zip(degradations, alpha)]))
                model.addLConstr(sum(alpha), gp.GRB.EQUAL, 1)
                model.addSOS(gp.GRB.SOS_TYPE2, alpha)
                # Method (a): Add degradation constraint
                # model.addLConstr(degradation[j] <= 1 / 10 / 365)
                # Method (b): Add degradation cost to objective function
                obj -= fee * degradation[j] * battery.Emax
            # Method 2: Add factorised aging cost to objective function (Xu2018Factoring)
            elif method == 2:
                pgens = [model.addVar(ub=battery.generator.max_capacity, name=f'pgen_{j}_segment_{m + 1}') for m in range(M)]
                model.addLConstr(energy_pgen[j] == sum(pgens))
                obj -= tstep * sum([pgens[m] * marginal_costs(R, battery.eff, M, m + 1) for m in range(M)])
        # Optimise
        model.setObjective(obj, gp.GRB.MAXIMIZE)
        model.optimize()
        # Write results
        return write.write_forecasts(current, soc, times, prices, energy_pgen, energy_pload, predispatch_time, T1, T2, battery.bat_dir, k), E[0].getValue()
        # Plot results
        # plot.plot_forecasts(custom_flag, current, [soc[j].x * 100 for j in range(T)], 'SOC (%)', times, prices, aemo_prices, battery, end=end, k=k, title='SOC')
        # plot.plot_forecasts(custom_flag, current, [energy_pgen[j].x - energy_pload[j].x for j in range(T)], 'Power (MW)', times, prices, aemo_prices, battery, end=end, k=k, title='Power')
        # return energy_pgen[0].x, energy_pload[0].x, E[0].getValue()


def optimise_whole_horizon(t, b, method):
    times, generations, loads, energy, power, dispatch_prices, aemo_dispatch_prices = [], [], [], [], [], [], []
    revenue = 0
    e = None
    for i in range(288):
        current = t + i * default.FIVE_MIN
        p, ap, _, _ = read.read_dispatch_prices(current, process='dispatch', custom_flag=True, region_id=b.load.region_id)
        # if i % 6 == 0:
        #     period_time = current + default.TWENTYFIVE_MIN
        #     p, ap = read.read_trading_prices(period_time, custom_flag=True, region_id=b.generator.region_id)
        g, l, e = schedule(current, b, horizon=i, E_initial=e, custom_flag=True, method=method)
        times.append(current)
        generations.append(g)
        loads.append(l)
        power.append(g - l)
        energy.append(e)
        dispatch_prices.append(p)
        aemo_dispatch_prices.append(ap)
        revenue += (g - l) * p * 5 / 60
    with (b.bat_dir / f'Optimisation {default.get_case_datetime(t)}.csv').open('w') as f:
        writer = csv.writer(f)
        writer.writerow(['H', 'Revenue ($)', revenue])
        writer.writerow(['I', 'Time', 'Generation (MW)', 'Load (MW)', 'Power (MW)', 'E (MWh)', 'Price ($/MW)', 'AEMO Price ($/MW)'])
        for t, g, l, e, p, ap in zip(times, generations, loads, energy, dispatch_prices, aemo_dispatch_prices):
            writer.writerow(['D', t, g, l, g - l, e, p, ap])

    # times, generations, loads, energy, power, dispatch_prices, aemo_dispatch_prices, revenue = read.read_optimisation(t, b)

    opt_dir = default.OUT_DIR / f'battery optimisation'
    opt_dir.mkdir(exist_ok=True, parents=True)
    plot.plot_forecasts(True, t, [en / b.Emax * 100 for en in energy], 'SOC (%)', times, dispatch_prices, aemo_dispatch_prices, b, forecast_dir=opt_dir,
                   process_type='dispatch', title='SOC')
    # plot.plot_forecasts(True, t, power, 'Power (MW)', times, dispatch_prices, aemo_dispatch_prices, b, forecast_dir=opt_dir,
    #                process_type='dispatch', title='Power')
    return revenue


def compare_battery_revenue(t):
    # for r in ['TAS1', 'NSW1', 'SA1', 'VIC1', 'QLD1']:
    #     b = Battery('Battery', 129, 100, r)
    #     optimise_whole_horizon(t, b)
    path_to_revenue = default.OUT_DIR / 'revenue.csv'
    with path_to_revenue.open('w') as rf:
        writer = csv.writer(rf)
        writer.writerow(['Capacity (MWh)', 'Power (MW)', 'Revenue ($)'])
        for e, p in zip(helpers.ENERGIES, helpers.POWERS):
            b = Battery(e, p)
            r = optimise_whole_horizon(t, b)
            writer.writerow([e, p, r])


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
    unit.energy.price_band = [0, voll]
    unit.energy.band_avail = [gen, load]
    unit.energy.fixed_load = 0
    unit.energy.max_avail = unit.max_capacity
    unit.energy.daily_energy_limit = 0
    unit.energy.roc_up = 1000000
    unit.energy.roc_down = 1000000
    return unit


def dispatch_with_first_bid(current, i, gen, load, battery, k):
    voll, market_price_floor = get_market_price(current)
    cvp = helpers.read_cvp()
    predispatch_time = get_predispatch_time(current)
    t = current - default.FIVE_MIN
    unit = customise_unit(t, gen, load, battery, voll, market_price_floor)
    dispatch.dispatch(t, interval=i - 1, process='dispatch', cvp=cvp, voll=voll, market_price_floor=market_price_floor,
                      iteration=k, custom_unit=unit, path_to_out=battery.bat_dir)


def forward_dispatch_with_bids(current, i, battery, k, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, cvp=None, voll=None, market_price_floor=None):
    # if voll is None:
    #     voll, market_price_floor = get_market_price(current)
    #     cvp = helpers.read_cvp()
    predispatch_time = get_predispatch_time(current)
    # p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, _ = read.read_forecasts(current - default.FIVE_MIN, battery.bat_dir, 0 if i == 1 else k)
    # Generate Dispatch
    t = current - default.FIVE_MIN
    unit = customise_unit(t, p5min_pgen[t], p5min_pload[t], battery, voll, market_price_floor)
    dispatch_path, _, _ = dispatch.dispatch(start=current - i * default.FIVE_MIN, interval=i - 1, process='dispatch', cvp=cvp, voll=voll, market_price_floor=market_price_floor, iteration=k, custom_unit=unit, dispatchload_flag=False if i == 1 else True, path_to_out=battery.bat_dir)
    # Generate P5MIN
    p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices = [], [], [], [], [], []
    for j in range(helpers.get_total_intervals('p5min')):
        t = current + j * default.FIVE_MIN
        if t in p5min_pgen:
            unit = customise_unit(current, p5min_pgen[t], p5min_pload[t], battery, voll, market_price_floor)
        else:
            predispatch_t = get_predispatch_time(t)
            unit = customise_unit(current, predispatch_pgen[predispatch_t], predispatch_pload[predispatch_t], battery, voll, market_price_floor)
        result_path, rrp, rrp_record = dispatch.dispatch(start=current, interval=j, process='p5min', cvp=cvp, voll=voll, market_price_floor=market_price_floor, iteration=k, custom_unit=unit, dispatchload_flag=True, path_to_out=battery.bat_dir, dispatchload_path=dispatch_path if j == 0 else None)
        p5min_times.append(t)
        p5min_prices.append(rrp)
        aemo_p5min_prices.append(rrp_record)
    # Generate Predispatch
    temp_flag = True
    for j in range(helpers.get_total_intervals('predispatch', predispatch_time)):
        t = predispatch_time + j * default.THIRTY_MIN
        gen = predispatch_pgen.get(t, None)
        if gen is None:
            gen = p5min_pgen.get(t - default.FIVE_MIN)
            if gen is None:
                if temp_flag:
                    gen = load = 0
                    temp_flag = False
                else:
                    break
            else:
                load = p5min_pload[t - default.FIVE_MIN]
        else:
            load = predispatch_pload[t]
        unit = customise_unit(current, gen, load, battery, voll, market_price_floor)
        predispatchload_path = battery.bat_dir / f'dispatch_{k}' / f'dispatchload_{default.get_case_datetime(predispatch_time - default.TWENTYFIVE_MIN)}.csv'
        result_path, rrp, rrp_record = dispatch.dispatch(start=predispatch_time, interval=j, process='predispatch', cvp=cvp, voll=voll, market_price_floor=market_price_floor, iteration=k, custom_unit=unit, dispatchload_flag=False if i < 6 else True, path_to_out=battery.bat_dir, dispatchload_path=predispatchload_path if j == 0 else None)
        predispatch_times.append(t)
        predispatch_prices.append(rrp)
        aemo_predispatch_prices.append(rrp_record)
    return p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices


def iterative_dispatch_with_bids(current, battery, k, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload):
    for j in range(helpers.get_total_intervals('p5min')):
        t = current + j * default.FIVE_MIN
        unit = customise_unit(current, p5min_pgen[t], p5min_pload[t], battery)
        dispatch.dispatch(start=current, interval=j, process='p5min', iteration=k, custom_unit=unit, dispatchload_flag=False if j == 0 else True,
                          path_to_out=battery.bat_dir)
    predispatch_time = get_predispatch_time(current)
    for j in range(helpers.get_total_intervals('predispatch', predispatch_time)):
        t = predispatch_time + j * default.THIRTY_MIN
        if t in predispatch_pgen:
            unit = customise_unit(current, predispatch_pgen[t], predispatch_pload[t], battery)
        else:
            unit = customise_unit(current, p5min_pgen[t], p5min_pload[t], battery)
        dispatch.dispatch(start=predispatch_time, interval=j, process='predispatch', iteration=k, custom_unit=unit,
                          dispatchload_flag=False if j == 0 else True, path_to_out=battery.bat_dir)


def iterative_forward_dispatch_with_bids(current, i, battery, k, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, cvp=None, voll=None, market_price_floor=None):
    predispatch_time = get_predispatch_time(current)
    # p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, _ = read.read_forecasts(current - default.FIVE_MIN, battery.bat_dir, 0 if i == 1 else k)
    # Generate Dispatch
    t = current - default.FIVE_MIN
    unit = customise_unit(t, p5min_pgen[t], p5min_pload[t], battery, voll, market_price_floor)
    dispatch_path, _, _ = dispatch.dispatch(start=current-i*default.FIVE_MIN, interval=i-1, process='dispatch', cvp=cvp, voll=voll, market_price_floor=market_price_floor, iteration=k, custom_unit=unit, dispatchload_flag=False if i == 1 else True, path_to_out=battery.bat_dir)
    # Generate P5MIN
    p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices = [], [], [], [], [], []
    for j in range(helpers.get_total_intervals('p5min')):
        t = current + j * default.FIVE_MIN
        if t in p5min_pgen:
            unit = customise_unit(current, p5min_pgen[t], p5min_pload[t], battery, voll, market_price_floor)
        else:
            predispatch_t = get_predispatch_time(t)
            unit = customise_unit(current, predispatch_pgen[predispatch_t], predispatch_pload[predispatch_t], battery, voll, market_price_floor)
        result_path, rrp, rrp_record = dispatch.dispatch(start=current, interval=j, process='p5min', cvp=cvp, voll=voll, market_price_floor=market_price_floor, iteration=k, custom_unit=unit, dispatchload_flag=True, path_to_out=battery.bat_dir, dispatchload_path=dispatch_path if j == 0 else None)
        p5min_times.append(t)
        p5min_prices.append(rrp)
        aemo_p5min_prices.append(rrp_record)
    # Generate Predispatch
    temp_flag = True
    for j in range(helpers.get_total_intervals('predispatch', predispatch_time)):
        t = predispatch_time + j * default.THIRTY_MIN
        gen = predispatch_pgen.get(t, None)
        if gen is None:
            gen = p5min_pgen.get(t - default.FIVE_MIN)
            if gen is None:
                if temp_flag:
                    gen = load = 0
                    temp_flag = False
                else:
                    break
            else:
                load = p5min_pload[t - default.FIVE_MIN]
        else:
            load = predispatch_pload[t]
        unit = customise_unit(current, gen, load, battery, voll, market_price_floor)
        predispatchload_path = battery.bat_dir / f'dispatch_{k}' / f'dispatchload_{default.get_case_datetime(predispatch_time - default.TWENTYFIVE_MIN)}.csv'
        result_path, rrp, rrp_record = dispatch.dispatch(start=predispatch_time, interval=j, process='predispatch', cvp=cvp, voll=voll, market_price_floor=market_price_floor, iteration=k, custom_unit=unit, dispatchload_flag=False if i < 6 else True, path_to_out=battery.bat_dir, dispatchload_path=predispatchload_path if j == 0 else None)
        predispatch_times.append(t)
        predispatch_prices.append(rrp)
        aemo_predispatch_prices.append(rrp_record)
    return p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices


def calculate_revenue(t, b, k=1):
    revenue = 0
    times, prices, powers = [], [], []
    for i in range(287):
        current = t + i * default.FIVE_MIN
        times.append(current)
        p, ap, _, _ = read.read_dispatch_prices(current, process='dispatch', custom_flag=True, k=k,
                                                region_id=b.load.region_id, path_to_out=b.bat_dir)
        prices.append(p)
        p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, pt = read.read_forecasts(current, b.bat_dir, 0 if i == 0 else k)
        revenue += (p5min_pgen[current] - p5min_pload[current]) * p * 5 / 60
        powers.append(p5min_pgen[current] - p5min_pload[current])
        # if p5min_pgen[current] - p5min_pload[current] != 0:
        #     print(f'{current} | {p} | {ap} | {p5min_pgen[current] - p5min_pload[current]}')
    return revenue, times, prices, powers


def extract_prices(current, battery, k):
    p5min_times, predispatch_times, p5min_prices, predispatch_prices, _, _, _ = preprocess_prices(current, True, battery, k)
    return p5min_times + predispatch_times, p5min_prices + predispatch_prices


def extract_forecasts(current, battery, k):
    p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, _ = read.read_forecasts(current, battery.bat_dir, k)
    return list(p5min_pgen.keys()) + list(predispatch_pgen.keys()), [p5min_pgen[t] - p5min_pload[t] for t in p5min_pgen.keys()] + [predispatch_pgen[t] - predispatch_pload[t] for t in predispatch_pgen.keys()]


def test_batteries(current):
    result_dir = default.OUT_DIR / f'Battery_{default.get_case_datetime(current)}.csv'
    with result_dir.open('w') as f:
        writer = csv.writer(f)
        writer.writerow(
            ['Capacity(MWh)', 'Power (MW)', 'Type', 'Price Taker Bid (MW)', 'NSW1', 'QLD1', 'SA1', 'TAS1',
             'VIC1'])
        prices = dispatch.dispatch(start=current, interval=0, process='dispatch')
        writer.writerow([0, 0, '', 0] + [prices[r] for r in ['NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']])
    for e, p in zip(helpers.ENERGIES, helpers.POWERS):
        battery = Battery(e, p)
        gen, load, _ = schedule(current, battery)
        if gen + load > 0:
            unit = customise_unit(current, gen, load, battery)
            dispatch.dispatch(start=current, interval=0, process='dispatch', custom_unit=unit,
                              path_to_out=battery.bat_dir)
        else:
            with result_dir.open('a') as f:
                writer = csv.writer(f)
                writer.writerow([e, p, '', '0'])


def test_battery_bids(t, iterations=5, method=2):
    # for e, p in zip(helpers.ENERGIES, helpers.POWERS):
    for e, p in [[10, 5]]:
        b = Battery(e, p, 'NSW1', method)
        (p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload), _ = schedule(t, b, custom_flag=True, horizon=0, k=0, method=method)
        for k in range(1, iterations):
            iterative_dispatch_with_bids(t, b, k, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload)
            (p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload), _ = schedule(t, b, custom_flag=True, horizon=0, k=k, method=method)
        plot.plot_comparison(t, b, extract_prices, 'Price', range(iterations))
        plot.plot_comparison(t, b, extract_forecasts, 'Forecast', range(iterations))
    # for k in range(iterations):
    #     plot.plot_battery_comparison(t, extract_prices, 'Price', k)
    #     plot.plot_battery_comparison(t, extract_forecasts, 'Forecast', k)


if __name__ == '__main__':
    import time
    start_time = time.time()
    start = datetime.datetime(2020, 9, 1, 4, 5)
    voll, market_price_floor = get_market_price(start)
    cvp = helpers.read_cvp()
    h = 0
    # t = start + default.FIVE_MIN * h
    path_to_log = default.LOG_DIR / f'price_taker_{default.get_case_datetime(start)}.log'
    logging.basicConfig(filename=path_to_log, filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)
    method = 2
    # test_battery_bids(start)
    # exit()
    # b = Battery(150, 100, 'NSW1', method)
    # try:
    #     g, l, e = schedule(start, b, custom_flag=True, method=method)
    #     energies, times = [e], [start]
    #     # while start <= datetime.datetime(2020, 9, 1, 4, 10):
    #     for i in range(1, 288):
    #         t = start + i * default.FIVE_MIN
    #         forward_dispatch_with_bids(t, i, b, k=1, cvp=cvp, voll=voll, market_price_floor=market_price_floor)
    #         g, l, e = schedule(t, b, E_initial=e, horizon=i, custom_flag=True, method=method, k=1)
    #         energies.append(e)
    #         times.append(t)
    # except Exception as e:
    #     logging.error(e)
    #     logging.error(traceback.format_exc())
    # finally:
    #     end_time = time.time()
    #     hours, rem = divmod(end_time - start_time, 3600)
    #     minutes, seconds = divmod(rem, 60)
    #     logging.info("Total Runtime {:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))
    #     opt_dir = default.OUT_DIR / f'battery optimisation with bids {b.generator.region_id} method {method}'
    #     opt_dir.mkdir(exist_ok=True, parents=True)
    #     opt_path = opt_dir / f'battery optimisation with bids {b.name}.csv'
    #     with opt_path.open('w') as f:
    #         writer = csv.writer(f)
    #         writer.writerow(['Time', 'SOC (%)'])
    #         for t, e in zip(times, energies):
    #             writer.writerow([t, e / b.Emax * 100])
    #     plot.plot_forecasts(True, times, [en / b.Emax * 100 for en in energies], 'SOC (%)', times, None, None, b, forecast_dir=opt_dir,
    #                         process_type='dispatch', title='SOC')

    # optimise_whole_horizon(start, b, method)
    energies, revenues = [], []
    normalisation_flag = True
    # for a in range(1, 21):
    #     e = 15 * a / 2 if a % 2 == 1 else int(15 * a / 2)
    #     p = 10 * a / 2 if a % 2 == 1 else int(10 * a / 2)
    #     b = Battery(e, p, 'NSW1', 2)
    #     energies.append(e)
    #     r = calculate_revenue(start, b, k=1)
    #     # print(e)
    #     revenues.append(r / e if normalisation_flag else r)
    #     print(b.name)
    #     plot.plot_optimisation_with_bids(b, method, k=1)
    # for a in range(11, 15):
    #     e = 15 * a
    #     p = 10 * a

    # import itertools
    # from decimal import Decimal
    # for a in itertools.chain([0.3, 0.5, 0.7, 0.9], range(1, 21)):
    #     e = float(Decimal('1.5') * Decimal(str(a)))
    #     # if e in [7.5, 15, 22.5, 30]:
    #     #     continue
    #     p = 1 * a
    #     if p == 5:
    #         p = 5.0
    #     elif e == 15:
    #         e = 15
    #     elif p == 15:
    #         p = 15.0
    #     elif e == 30:
    #         e = 30
    prices_list, powers_list = [], []
    # print('| Battery Size (MWh) | Capacity (MW) | Revenue | Revenue per MWh|')
    # print('| ------------------ | ------------- | ------- | -------------- |')
    for e, p in [[1.5, 1], [30, 20]]:
        b = Battery(e, p, 'NSW1', 2)
        energies.append(e)
        r, times, prices, powers = calculate_revenue(start, b, k=1)
        prices_list.append(prices)
        powers_list.append(powers)
        revenues.append(r / e if normalisation_flag else r)
        # print(f'| {e} | {p} | {r} | {r/e} |')
        # plot.plot_optimisation_with_bids(b, method, k=1)
    # plot.plot_price_comparison(times, prices_list[0], prices_list[1])
    print('Datetime | Price (Small) | Price (Large) | Difference in Prices | Power (Small) | Power (Large)')
    print('-------- | ------------- | ------------- | -------------------- | ------------- | -------------')
    for t, price1, price2, power1, power2 in zip(times, prices_list[0], prices_list[1], powers_list[0], powers_list[1]):
        # if power1 != 0 or power2 != 0:
        if abs(price1 - price2) > 1 and (power1 != 0 or power2 != 0):
            print(f'{t} | {price1} | {price2} | {price1 - price2} | {power1} | {power2}')
    original = None
    # plot.plot_revenues(energies, revenues, 'Capacity (MWh)', 'Revenue ($ per MWh)' if normalisation_flag else 'Revenue ($)', b.generator.region_id, 2, original)
