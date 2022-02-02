from helpers import Battery
from price_taker import calculate_revenue
import datetime
from plot import plot_revenues


def compare_revenue(start):
    energies, revenues = [], []
    normalisation_flag = True
    prices_list, powers_list = [], []

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


def plot_all_revenues(start, batteries):
    energies, revenues = [], []
    normalisation_flag = True
    # print('| Battery Size (MWh) | Capacity (MW) | Revenue | Revenue per MWh|')
    # print('| ------------------ | ------------- | ------- | -------------- |')
    for e, p in batteries:
        b = Battery(e, p, 'NSW1', 2)
        energies.append(e)
        r, times, prices, powers = calculate_revenue(start, b, k=1)
        revenues.append(r / e if normalisation_flag else r)
        print(f'| {e} | {p} | {r} | {r/e} |')
        # plot.plot_optimisation_with_bids(b, method, k=1)
    original = None
    plot_revenues(energies, revenues, 'Capacity (MWh)', 'Revenue ($ per MWh)' if normalisation_flag else 'Revenue ($)', b.generator.region_id, 2, original)


if __name__ == '__main__':
    start = datetime.datetime(2020, 9, 1, 4, 5, 0)
    # compare_revenue(start)
    batteries = []
    import itertools
    from decimal import Decimal
    for a in itertools.chain([0.3, 0.5, 0.7, 0.9], range(1, 21)):
        e = float(Decimal('1.5') * Decimal(str(a)))
        if e not in [7.5, 15, 22.5, 30]:
            p = 1 * a
        batteries.append([e, p])
    plot_all_revenues(start, batteries)