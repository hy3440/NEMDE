import csv
import datetime
import default
import multiprocessing as mp
import price_taker
import helpers
import write
import read
import plot

method = 0
region_id = 'VIC1'


def apply_multiprocess_optimise(b):
    t = datetime.datetime(2020, 9, 1, 4, 5)
    return price_taker.optimise_whole_horizon(t, b, method)


if __name__ == '__main__':
    batteries = []
    for e, p in zip([12, 65, 129, 429, 1000, 2800, 4000], [30, 50, 100, 200, 500, 700, 1000]):
        b = helpers.Battery(e, p, region_id, method)
        batteries.append(b)
    with mp.Pool(7) as pool:
        revenues = pool.map(apply_multiprocess_optimise, batteries)
    write.write_revenues(batteries, revenues, region_id, method)
    capacity_label, capacities, power_label, powers, revenue_label, revenues = read.read_revenues(region_id, method)
    plot.plot_revenues(capacities, revenues, capacity_label, revenue_label, region_id, method)
