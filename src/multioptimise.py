import datetime
import default
import multiprocessing as mp
import price_taker
import time
import helpers
import write
import read
import plot
from constrain import get_market_price
import traceback
import csv


region_id = 'NSW1'
method = 2


def apply_multiprocess_optimise_for_batteries(b):
    t = datetime.datetime(2020, 9, 1, 4, 5)
    return price_taker.optimise_whole_horizon(t, b, method)


def apply_multiprocess_optimise_using_methods(m):
    t = datetime.datetime(2020, 9, 1, 4, 5)
    b = helpers.Battery(45, 30, region_id, m)
    return price_taker.optimise_whole_horizon(t, b, m)


def apply_multiprocess_optimise_with_bids(b):
    start_time = time.time()
    start = datetime.datetime(2020, 9, 1, 4, 5)
    voll, market_price_floor = get_market_price(start)
    cvp = helpers.read_cvp()    # g, l, e = price_taker.schedule(start, b, custom_flag=True, method=method)
    # energies, times = [e], [start]
    # start += default.FIVE_MIN
    # i = 0
    # while start <= datetime.datetime(2020, 9, 2, 4, 0):
    #     price_taker.forward_dispatch_with_bids(start, i, b, k=1)
    #     g, l, e = price_taker.schedule(start, b, E_initial=e, custom_flag=True, method=method, k=1)
    #     energies.append(e)
    #     times.append(start)
    #     start += default.FIVE_MIN
    #     i += 1
    # opt_dir = default.OUT_DIR / f'battery optimisation with bids {b.generator.region_id} method {method}'
    # opt_dir.mkdir(exist_ok=True, parents=True)
    # plot.plot_forecasts(True, times, [en / b.Emax * 100 for en in energies], 'SOC (%)', times, None, None, b,
    #                     forecast_dir=opt_dir, process_type='dispatch', title='SOC')

    try:
        (p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload), e = price_taker.schedule(start, b, custom_flag=True, method=method)
        energies, times = [e], [start]
        # while start <= datetime.datetime(2020, 9, 1, 4, 10):
        for i in range(1, 288):
            t = start + i * default.FIVE_MIN
            p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices = price_taker.forward_dispatch_with_bids(t, i, b, 1, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, cvp=cvp, voll=voll, market_price_floor=market_price_floor)
            (p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload), e = price_taker.schedule(t, b, p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices, E_initial=e, horizon=i, custom_flag=True, method=method, k=1)
            energies.append(e)
            times.append(t)
    except Exception as e:
        print(e)
        print(traceback.format_exc())
    finally:
        end_time = time.time()
        hours, rem = divmod(end_time - start_time, 3600)
        minutes, seconds = divmod(rem, 60)
        print("Total Runtime {:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))
        opt_dir = default.OUT_DIR / f'battery optimisation with bids {b.generator.region_id} method {method}'
        opt_dir.mkdir(exist_ok=True, parents=True)
        opt_path = opt_dir / f'battery optimisation with bids {b.name}.csv'
        with opt_path.open('w') as f:
            writer = csv.writer(f)
            writer.writerow(['Time', 'SOC (%)'])
            for t, e in zip(times, energies):
                writer.writerow([t, e / b.Emax * 100])
        # plot.plot_forecasts(True, times, [en / b.Emax * 100 for en in energies], 'SOC (%)', times, None, None, b,
        #                     forecast_dir=opt_dir, process_type='dispatch', title='SOC')


def apply_multiprocess_optimise_with_iterations(b):
    iterations = 5
    t = datetime.datetime(2020, 9, 1, 4, 5)
    (p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload), _ = price_taker.schedule(t, b, custom_flag=True, horizon=0, k=0, method=method)
    for k in range(1, iterations):
        price_taker.iterative_dispatch_with_bids(t, b, k, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload)
        (p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload), _ = price_taker.schedule(t, b, custom_flag=True, horizon=0, k=k, method=method)
    plot.plot_comparison(t, b, price_taker.extract_prices, 'Price', range(iterations))
    plot.plot_comparison(t, b, price_taker.extract_forecasts, 'Forecast', range(iterations))


def apply_multiprocess_forward_iterative_optimise_with_bids(b):
    iterations = 5
    start_time = time.time()
    start = datetime.datetime(2020, 9, 1, 4, 5)
    voll, market_price_floor = get_market_price(start)
    cvp = helpers.read_cvp()
    try:
        (p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload), e = price_taker.schedule(start, b, custom_flag=True, method=method)
        energies, times = [e], [start]
        for i in range(1, 4):
            t = start + i * default.FIVE_MIN
            print(t)
            exit()
            start_iteration = 1 if i == 1 else 2
            for k in range(start_iteration, iterations):
                price_taker.iterative_dispatch_with_bids(t, b, k, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload)
                (p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload), _ = price_taker.schedule(t, b, custom_flag=True, horizon=0, k=k, method=method)
            p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices = price_taker.iterative_forward_dispatch_with_bids(t, i, b, 1, p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, cvp=cvp, voll=voll, market_price_floor=market_price_floor)
            (p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload), e = price_taker.schedule(t, b, p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices, E_initial=e, horizon=i, custom_flag=True, method=method, k=iterations - 1)
            energies.append(e)
            times.append(t)
    except Exception as e:
        print(e)
        print(traceback.format_exc())
    finally:
        end_time = time.time()
        hours, rem = divmod(end_time - start_time, 3600)
        minutes, seconds = divmod(rem, 60)
        print("Total Runtime {:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))


if __name__ == '__main__':
    # Optimise for different batteries
    batteries = []
    # for e, p in zip(helpers.ENERGIES, helpers.POWERS):
    #     b = helpers.Battery(e, p, region_id, method)
    #     batteries.append(b)
    # with mp.Pool(len(batteries)) as pool:
    #     revenues = pool.map(apply_multiprocess_optimise_for_batteries, batteries)
    # write.write_revenues(batteries, revenues, region_id, method)
    # capacity_label, capacities, power_label, powers, revenue_label, revenues = read.read_revenues(region_id, method)
    # plot.plot_revenues(capacities, revenues, capacity_label, revenue_label, region_id, method)
    # plot.plot_revenues(powers, revenues, power_label, revenue_label, region_id, method)

    # # Optimise for different methods
    # methods = [None, 0, 1, 2]
    # with mp.Pool(len(methods)) as pool:
    #     revenues = pool.map(apply_multiprocess_optimise_using_methods, methods)

    # Optimise with bids for different batteries
    # import itertools
    # from decimal import Decimal
    # for a in itertools.chain([0.3, 0.5, 0.7, 0.9], range(1, 21)):
    #     e = float(Decimal('1.5') * Decimal(str(a)))
    #     if e not in [7.5, 15, 22.5, 30]:
    #         p = 1 * a
    #         b = helpers.Battery(e, p, region_id, method)
    #         batteries.append(b)
    # with mp.Pool(len(batteries)) as pool:
    #     pool.map(apply_multiprocess_optimise_with_bids, batteries)

    # # Optimise with iterations for different batteries
    # import time
    # start_timeit = time.time()
    # for a in range(6, 8, 2):
    #     e = 40 * a
    #     p = 30 * a
    #     b = helpers.Battery(e, p, region_id, method)
    #     batteries.append(b)
    # with mp.Pool(len(batteries)) as pool:
    #     pool.map(apply_multiprocess_optimise_with_iterations, batteries)
    # print("--- %s seconds ---" % (time.time() - start_timeit))

    #
    import time
    start_timeit = time.time()
    for a in range(6, 8, 2):
        e = 40 * a
        p = 30 * a
        b = helpers.Battery(e, p, region_id, method)
        batteries.append(b)
    with mp.Pool(len(batteries)) as pool:
        pool.map(apply_multiprocess_forward_iterative_optimise_with_bids, batteries)
    print("--- %s seconds ---" % (time.time() - start_timeit))