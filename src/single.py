# Investigate influence of single battery (with different MW capacity) on market price.

import csv
import datetime
import default
from dispatch import dispatch
import helpers
import matplotlib.pyplot as plt
import multiprocessing as mp
from price_taker import get_market_price, get_predispatch_time, customise_unit


def single_bid(start, no, gen, load, battery, single_dir):
    voll, market_price_floor = get_market_price(current)
    cvp = helpers.read_cvp()
    unit = customise_unit(current, gen, load, battery, voll, market_price_floor)
    _, rrp, rrp_record = dispatch(start, interval=no - 1, process='dispatch', cvp=cvp, voll=voll, market_price_floor=market_price_floor,
             custom_unit=unit, path_to_out=single_dir, dispatchload_flag=False)
    return rrp, rrp_record


def process(current):
    start, no = default.datetime_to_interval(current)
    prices = {}
    b = helpers.Battery(200, 10000, 'NSW1', 2)
    # range1 = range(0, 100, 10)
    # range2 = range(100, 1100, 100)
    # from itertools import chain
    # mws = chain(range1, range2)
    # mws = [-10, -7.5, -5, -2.5, 0, 2.5, 5, 7.5, 10]
    mws = [0, 10]
    for mw in mws:
        single_dir = default.OUT_DIR / 'single' / f'{mw}'
        rrp, rrp_record = single_bid(start, no, max(mw, 0), -min(mw, 0), b, single_dir)
        prices[mw] = rrp
    return prices


def plot_single(current, mw, prices):
    fig, ax1 = plt.subplots()
    ax1.set_xlabel('Battery (MW)')
    ax1.set_ylabel('Price ($/MWh)')
    ax1.plot(mw, prices, 'o-')
    # plt.show()
    path_to_fig = default.OUT_DIR / 'single' / 'plots' / f'{current:%Y%m%d%H%M}.jpg'
    plt.savefig(path_to_fig)


def save_results(current, prices):
    path_to_result = default.OUT_DIR / 'single' / 'results' / f'{current:%Y%m%d%H%M}.csv'
    with path_to_result.open('a+') as result_file:
        writer = csv.writer(result_file)
        writer.writerow(['I', 'Availability (MW)', 'Market Price ($/MWh)'])
        for k, v in sorted(prices.items()):
            writer.writerow(['D', k, v])


def read_results(current):
    prices = {}
    path_to_result = default.OUT_DIR / 'single' / 'results' / f'{current:%Y%m%d%H%M}.csv'
    with path_to_result.open('r') as result_file:
        reader = csv.reader(result_file)
        for row in reader:
            if row[0] == 'D':
                prices[float(row[1])] = float(row[2])
    return prices


def apply_multiprocess(current):
    prices = process(current)
    # save_results(current, prices)

    # prices = read_results(current)
    print(prices)
    # sorted_prices = sorted(prices.items())
    # plot_single(current, [k for k, v in sorted_prices if abs(k) <= 10], [v for k, v in sorted_prices if abs(k) <= 10])


def multiprocess():
    N = 8  # Number of samples
    current = datetime.datetime(2020, 9, 1, 4, 5, 0)
    from random import sample
    numbers = sample(range(288), N)
    times = [current + n * default.FIVE_MIN for n in numbers]
    print(times)
    with mp.Pool(N) as pool:
        pool.map(apply_multiprocess, times)


if __name__ == '__main__':
    current = datetime.datetime(2020, 9, 1, 14, 0, 0)
    apply_multiprocess(current)

