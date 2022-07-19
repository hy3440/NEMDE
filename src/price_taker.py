# Price-taker bidding strategy
from preprocess import get_market_price
import csv
import datetime
import default
import dispatch
import helpers
import logging
from offer import EnergyBid
import plot
import read
from helpers import Battery
from operate import schedule
from src.price import preprocess_prices


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
    # plot.plot_forecasts(True, t, [en / b.Emax * 100 for en in energy], 'SOC (%)', times, dispatch_prices, aemo_dispatch_prices, b, forecast_dir=opt_dir,
    #                process_type='dispatch', title='SOC')
    path_to_fig = opt_dir / f'SOC {b.name}.jpg'
    plot.plot_soc(times, [dispatch_prices, aemo_dispatch_prices], [en / b.Emax * 100 for en in energy], path_to_fig)
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
    unit.energy.price_band = [market_price_floor, voll]
    unit.energy.band_avail = [gen, load]
    unit.energy.fixed_load = 0
    unit.energy.max_avail = unit.max_capacity
    unit.energy.daily_energy_limit = 0
    unit.energy.roc_up = default.MAX_RAMP_RATE
    unit.energy.roc_down = default.MAX_RAMP_RATE
    return unit


def dispatch_with_first_bid(current, i, gen, load, battery, k):
    voll, market_price_floor = get_market_price(current)
    cvp = helpers.read_cvp()
    predispatch_time = default.get_predispatch_time(current)
    t = current - default.FIVE_MIN
    unit = customise_unit(t, gen, load, battery, voll, market_price_floor)
    dispatch.formulate(t, interval=i - 1, process='dispatch', iteration=k, custom_unit=unit,
                       path_to_out=battery.bat_dir)


def forward_dispatch_with_bids(current, i, battery, k, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, cvp=None, voll=None, market_price_floor=None):
    # if voll is None:
    #     voll, market_price_floor = get_market_price(current)
    #     cvp = helpers.read_cvp()
    predispatch_time = default.get_predispatch_time(current)
    # p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, _ = read.read_forecasts(current - default.FIVE_MIN, battery.bat_dir, 0 if i == 1 else k)
    # Generate Dispatch
    t = current - default.FIVE_MIN
    unit = customise_unit(t, p5min_pgen[t], p5min_pload[t], battery, voll, market_price_floor)
    dispatch_path, _, _ = dispatch.formulate(start=current - i * default.FIVE_MIN, interval=i - 1, process='dispatch',
                                             iteration=k, custom_unit=unit, path_to_out=battery.bat_dir,
                                             dispatchload_flag=False if i == 1 else True)
    # Generate P5MIN
    p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices = [], [], [], [], [], []
    for j in range(helpers.get_total_intervals('p5min')):
        t = current + j * default.FIVE_MIN
        if t in p5min_pgen:
            unit = customise_unit(current, p5min_pgen[t], p5min_pload[t], battery, voll, market_price_floor)
        else:
            predispatch_t = default.get_predispatch_time(t)
            unit = customise_unit(current, predispatch_pgen[predispatch_t], predispatch_pload[predispatch_t], battery, voll, market_price_floor)
        result_path, rrp, rrp_record = dispatch.formulate(start=current, interval=j, process='p5min', iteration=k,
                                                          custom_unit=unit, path_to_out=battery.bat_dir,
                                                          dispatchload_path=dispatch_path if j == 0 else None,
                                                          dispatchload_flag=True)
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
        result_path, rrp, rrp_record = dispatch.formulate(start=predispatch_time, interval=j, process='predispatch',
                                                          iteration=k, custom_unit=unit, path_to_out=battery.bat_dir,
                                                          dispatchload_path=predispatchload_path if j == 0 else None,
                                                          dispatchload_flag=False if i < 6 else True)
        predispatch_times.append(t)
        predispatch_prices.append(rrp)
        aemo_predispatch_prices.append(rrp_record)
    return p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices


def iterative_dispatch_with_bids(current, battery, k, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload):
    for j in range(helpers.get_total_intervals('p5min')):
        t = current + j * default.FIVE_MIN
        unit = customise_unit(current, p5min_pgen[t], p5min_pload[t], battery)
        dispatch.formulate(start=current, interval=j, process='p5min', iteration=k, custom_unit=unit,
                           path_to_out=battery.bat_dir, dispatchload_flag=False if j == 0 else True)
    predispatch_time = default.get_predispatch_time(current)
    for j in range(helpers.get_total_intervals('predispatch', predispatch_time)):
        t = predispatch_time + j * default.THIRTY_MIN
        if t in predispatch_pgen:
            unit = customise_unit(current, predispatch_pgen[t], predispatch_pload[t], battery)
        else:
            unit = customise_unit(current, p5min_pgen[t], p5min_pload[t], battery)
        dispatch.formulate(start=predispatch_time, interval=j, process='predispatch', iteration=k, custom_unit=unit,
                           path_to_out=battery.bat_dir, dispatchload_flag=False if j == 0 else True)


def iterative_forward_dispatch_with_bids(current, i, battery, k, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, cvp=None, voll=None, market_price_floor=None):
    predispatch_time = default.get_predispatch_time(current)
    # p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, _ = read.read_forecasts(current - default.FIVE_MIN, battery.bat_dir, 0 if i == 1 else k)
    # Generate Dispatch
    t = current - default.FIVE_MIN
    unit = customise_unit(t, p5min_pgen[t], p5min_pload[t], battery, voll, market_price_floor)
    dispatch_path, _, _ = dispatch.formulate(start=current - i * default.FIVE_MIN, interval=i - 1, process='dispatch',
                                             iteration=k, custom_unit=unit, path_to_out=battery.bat_dir,
                                             dispatchload_flag=False if i == 1 else True)
    # Generate P5MIN
    p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices = [], [], [], [], [], []
    for j in range(helpers.get_total_intervals('p5min')):
        t = current + j * default.FIVE_MIN
        if t in p5min_pgen:
            unit = customise_unit(current, p5min_pgen[t], p5min_pload[t], battery, voll, market_price_floor)
        else:
            predispatch_t = default.get_predispatch_time(t)
            unit = customise_unit(current, predispatch_pgen[predispatch_t], predispatch_pload[predispatch_t], battery, voll, market_price_floor)
        result_path, rrp, rrp_record = dispatch.formulate(start=current, interval=j, process='p5min', iteration=k,
                                                          custom_unit=unit, path_to_out=battery.bat_dir,
                                                          dispatchload_path=dispatch_path if j == 0 else None,
                                                          dispatchload_flag=True)
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
        result_path, rrp, rrp_record = dispatch.formulate(start=predispatch_time, interval=j, process='predispatch',
                                                          iteration=k, custom_unit=unit, path_to_out=battery.bat_dir,
                                                          dispatchload_path=predispatchload_path if j == 0 else None,
                                                          dispatchload_flag=False if i < 6 else True)
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
    times, predispatch_time, prices, _, _, _ = preprocess_prices(current, True, battery, k)
    return times, prices


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
        prices = dispatch.formulate(start=current, interval=0, process='dispatch')
        writer.writerow([0, 0, '', 0] + [prices[r] for r in ['NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']])
    for e, p in zip(helpers.ENERGIES, helpers.POWERS):
        battery = Battery(e, p)
        gen, load, _ = schedule(current, battery)
        if gen + load > 0:
            unit = customise_unit(current, gen, load, battery)
            dispatch.formulate(start=current, interval=0, process='dispatch', custom_unit=unit,
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


def old_main():
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
