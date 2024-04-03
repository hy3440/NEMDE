# from read import read_battery_power, read_battery_optimisation, read_dispatch_prices
# from helpers import generate_batteries_by_energies, Battery
# from offer import add_du_detail_summary, add_du_detail
from plot import plot_revenues, plot_soc, plot_power
import default
import numpy as np
import datetime
import csv
import gurobipy as gp
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
import matplotlib.pyplot as plt
# plt.style.use(['science', 'ieee', 'no-latex'])
plt.rcParams['axes.unicode_minus'] = False
# plt.rcParams.update({'font.sans-serif': "Arial",
#                      'font.family': "sans-serif",
#                      'mathtext.fontset' : 'custom',
#                      'mathtext.rm': 'Arial',
#                     })
import matplotlib.dates as mdates
import matplotlib.ticker as ticker


def calculate_revenue(start, battery, usage, print_flag=0, sign='', total_intervals=288):
    """Calculate total revenue of battery.

    Args:
        start (datetime.datetime): start datetime
        battery (helpers.Battery): battery instance
        usage (str): battery usage
        print_flag (str): used to identify different print content
        sign (str): used to identify different files

    Returns:
        float: total revenue
    """
    times, generations, loads, prices, generator_fcas, load_fcas, fcas_prices = read_battery_power(battery.bat_dir / f'{default.get_case_datetime(start)}{sign}.csv', usage)
    energy_revenue, fcas_revenue = [], {}
    if len(times) % total_intervals != 0:
        print('Interval Number Error!')
    revenue = 0
    if print_flag == 3:
        print('Datetime | Generator | Load | Price')
        print('---------|-----------|------|------')
    elif print_flag == 1:
        print('Day | Energy Revenue | FCAS Revenue | Total')
        print('----|----------------|--------------|------')
    for n, (t, g, l, p) in enumerate(zip(times, generations, loads, prices)):
        # if n >= 288:
        #     break
        if n % (total_intervals - 1) == 0 and n > 0:
            energy_revenue.append(revenue)
            revenue = 0
        if g > 0 and l > 0:
            print('Energy Error!')
        if (g > 0 or l > 0) and print_flag == 3:
            print(f'`{t}` | {g:.2f} | {l:.2f} | {p:.2f}')
        revenue += (g - l) * p * (1440 / total_intervals) / 60
    if 'FCAS' in usage:
        for bid_type in fcas_prices.keys():
            fcas_revenue[bid_type] = []
            for n, (t, gen_value, load_value, price) in enumerate(zip(times, generator_fcas[bid_type], load_fcas[bid_type], fcas_prices[bid_type])):
                # if n >= 288:
                #     break
                if n % (total_intervals - 1) == 0 and n > 0:
                    fcas_revenue[bid_type].append(revenue)
                    revenue = 0
                revenue += (gen_value + load_value) * price * (1440 / total_intervals) / 60
    total_revenue = 0
    for n in range(len(energy_revenue)):
        total_fcas_revenue = 0
        if 'FCAS' in usage:
            for revenue in fcas_revenue.values():
                total_fcas_revenue += revenue[n]
        total_revenue += energy_revenue[n] + total_fcas_revenue
        if print_flag == 1:
            print(f'{n + 1} | {energy_revenue[n]:.2f} | {total_fcas_revenue:.2f} | {energy_revenue[n] + total_fcas_revenue:.2f}')
    if print_flag == 1:
        print(f'Total | {sum(energy_revenue):.2f} | {total_revenue - sum(energy_revenue):.2f} | {total_revenue:.2f}')
    elif print_flag == 2:
        print(f'{usage} | {sum(energy_revenue):.2f} | {total_revenue - sum(energy_revenue):.2f} | {total_revenue:.2f}')
    return total_revenue


def compare_revenue_by_day(start, battery, usage):
    """Compare revenue of each day for one battery.

    Args:
        start (datetime.datetime): start datetime
        battery (helpers.Battery): battery instance
        usage (str): battery usage

    Returns:
        None
    """
    print('Day | Energy Revenue | FCAS Revenue | Total')
    print('----|----------------|--------------|------')
    calculate_revenue(start, battery, usage, 1)


def calculate_revenue_and_volatility(start, energies, usage, sign=''):
    """Calculate revenue and volatility of different batteries.

    Args:
        energies (list): different battery sizes
        usage (str): battery usage
        sign (str): used to identify different files

    Returns:
        (list, list, list): revenue rates, standard deviations, means
    """
    batteries = generate_batteries_by_energies(energies, usage)
    revenues = [calculate_revenue(start, b, usage, print_flag=1, sign=sign) for b in batteries]
    rates = [r / e for e, r in zip(energies, revenues)]
    mean, var, std = calculate_volatility(start, batteries, usage)
    return rates, std, mean


def compare_revenue_by_usage_and_size(start, sign=''):
    """Compare revenues of different batteries with different usages.

    Args:
        start (datetime.datetime): start datetime
        sign (str): used to identify different files

    Returns:
        None
    """
    e1 = [0.03, 3, 30, 120, 240, 360, 480, 600, 720, 960, 1200, 2100, 3000]  # Cost-reflective + multiple FCAS
    # e1 = [0.03, 3, 30, 120, 240, 360, 480, 720]  # Price-taker
    # e2 = [0.03, 3, 30, 120, 240, 360, 480, 720, 960, 1200, 2100, 3000]  # Price-taker + multiple FCAS

    u1 = 'Cost-reflective + multiple FCAS'
    u2 = 'Price-taker500 + multiple FCAS'
    u3 = 'Cost-reflective'
    u4 = 'Price-taker'

    rate1, std1, mean1 = calculate_revenue_and_volatility(e1, u1, sign)
    rate2, std2, mean2 = calculate_revenue_and_volatility(e1, u2, sign)
    # rate3, std3 = calculate_revenue_and_volatility(e1, u3, sign)
    # rate4, std4 = calculate_revenue_and_volatility(e1, u4, sign)

    # print(f'Battery Capacity (MWh) | {u1} | {u2} | {u3} | {u4}')
    # for e, r1, r2, r3, r4 in zip(e1, rate1, rate2, rate3, rate4):
    #     print(f'{e} | {r1:.2f} | {r2:.2f} | {r3:.2f} | {r4:.2f}')

    plot_revenues(e1, rate1, 'Battery Size (MWh)', 'Revenue Rate', u1, 'Revenue Rate')
    plot_revenues(e1, rate2, 'Battery Size (MWh)', 'Revenue Rate', u2, 'Revenue Rate')
    plot_revenues(e1, rate1, 'Battery Size (MWh)', 'Revenue Rate ($/MWh)', u1[:-16], 'Revenue Comparison', e1, rate2, u2[:-19])
    plot_revenues(e1, std1, 'Battery Size (MWh)', 'Standard Deviation', u1, 'Standard Deviation')
    plot_revenues(e1, std2, 'Battery Size (MWh)', 'Standard Deviation', u2, 'Standard Deviation')
    plot_revenues(e1, std1, 'Battery Size (MWh)', 'Standard Deviation', u1[:-16], 'Standard Deviation', e1, std2, u2[:-19])
    plot_revenues(e1, mean1, 'Battery Size (MWh)', 'Average Price ($/MWh)', u1[:-16], 'Average Price', e1, mean2, u2[:-19])


def compare_soc_by_size(start, batteries):
    times0, socs0, prices0 = read_battery_optimisation(batteries[0].bat_dir / f'{default.get_case_datetime(start)}.csv')
    times1, socs1, prices1 = read_battery_optimisation(batteries[1].bat_dir / f'{default.get_case_datetime(start)}.csv')
    print('Datetime | SOC 1 (%) | SOC 2 (%) | Price 1 | Price 2 | Without Battery')
    print('---------|-------|-------|---------|---------|----------------')
    for t0, t1, s0, s1, p0, p1 in zip(times0, times1, socs0, socs1, prices0, prices1):
        if t0 != t1:
            print('error!')
        if t0 - start >= datetime.timedelta(hours=24):
            return None
        rrp, rrp_record, _, _ = read_dispatch_prices(t0, 'dispatch', True, batteries[0].generator.region_id,
                                                     path_to_out=default.OUT_DIR / 'sequence')
        if p0 != p1:
            print(f'`{t0}` | {s0:.2f} | {s1:.2f} | {p0:.2f} | {p1:.2f} | {rrp:.2f}')
            # print(f'**`{t0}`** | **{s0:.2f}** | **{s1:.2f}** | **{p0:.2f}** | **{p1:.2f}** | **{rrp:.2f}**')
        # else:
        #     print(f'`{t0}` | {s0:.2f} | {s1:.2f} | {p0:.2f} | {p1:.2f} | {rrp:.2f}')


def compare_revenue_by_usage(start):
    energy = 3000
    power = int(energy * 2 / 3)
    print(f'**{power}MW/{energy}MWh**\n')
    print('Strategy | Energy Revenue | FCAS Revenue | Total')
    print('-------- | -------------- | ------------ | -----')
    for usage in ['Basic price-taker',
                  'Basic price-taker + FCAS',
                  'Basic price-taker + multiple FCAS',
                  'Price-taker',
                  'Price-taker + FCAS',
                  'Price-taker + multiple FCAS',
                  'Cost-reflective',
                  'Cost-reflective + FCAS',
                  'Cost-reflective + multiple FCAS',
                  'Cost-reflective + multiple FCAS + new band price']:
        battery = Battery(energy, power, usage=usage)
        calculate_revenue(start, battery, usage, 2)


def calculate_volatility(start, batteries, usage):
    """Caluate volatility for different batteries.

    Args:
        start (datetime.datetime): start datetime
        batteries (list): different batteries
        usage (str): battery usage

    Returns:
        (list, list, list): means, variances, standard deviations
    """
    print('Battery Size | Mean | Variance | Standard Deviation')
    print('-------------|------|----------|-------------------')
    means, vars, stds = [], [], []
    for battery in batteries:
        times, generations, loads, prices, generator_fcas, load_fcas, fcas_prices = read_battery_power(battery.bat_dir / f'{default.get_case_datetime(start)}.csv', usage)
        print(f'{battery.size} | {np.mean(prices):.2f} | {np.var(prices):.2f} | {np.std(prices):.2f}')
        means.append(np.mean(prices))
        vars.append(np.var(prices))
        stds.append(np.std(prices))
    return means, vars, stds


def plot_cost_reflective_bands():
    times = [datetime.datetime(2020, 9, 1, 4, 5), datetime.datetime(2020, 9, 1, 4, 10),
             datetime.datetime(2020, 9, 1, 4, 15), datetime.datetime(2020, 9, 1, 4, 20),
             datetime.datetime(2020, 9, 1, 4, 25), datetime.datetime(2020, 9, 1, 4, 30),
             datetime.datetime(2020, 9, 1, 5, 0), datetime.datetime(2020, 9, 1, 5, 30),
             datetime.datetime(2020, 9, 1, 6, 0), datetime.datetime(2020, 9, 1, 6, 30),
             datetime.datetime(2020, 9, 1, 7, 0), datetime.datetime(2020, 9, 1, 7, 30),
             datetime.datetime(2020, 9, 1, 8, 0), datetime.datetime(2020, 9, 1, 8, 30),
             datetime.datetime(2020, 9, 1, 9, 0), datetime.datetime(2020, 9, 1, 9, 30),
             datetime.datetime(2020, 9, 1, 10, 0), datetime.datetime(2020, 9, 1, 10, 30),
             datetime.datetime(2020, 9, 1, 11, 0), datetime.datetime(2020, 9, 1, 11, 30),
             datetime.datetime(2020, 9, 1, 12, 0), datetime.datetime(2020, 9, 1, 12, 30),
             datetime.datetime(2020, 9, 1, 13, 0), datetime.datetime(2020, 9, 1, 13, 30),
             datetime.datetime(2020, 9, 1, 14, 0), datetime.datetime(2020, 9, 1, 14, 30),
             datetime.datetime(2020, 9, 1, 15, 0), datetime.datetime(2020, 9, 1, 15, 30),
             datetime.datetime(2020, 9, 1, 16, 0), datetime.datetime(2020, 9, 1, 16, 30),
             datetime.datetime(2020, 9, 1, 17, 0), datetime.datetime(2020, 9, 1, 17, 30),
             datetime.datetime(2020, 9, 1, 18, 0), datetime.datetime(2020, 9, 1, 18, 30),
             datetime.datetime(2020, 9, 1, 19, 0), datetime.datetime(2020, 9, 1, 19, 30),
             datetime.datetime(2020, 9, 1, 20, 0), datetime.datetime(2020, 9, 1, 20, 30),
             datetime.datetime(2020, 9, 1, 21, 0), datetime.datetime(2020, 9, 1, 21, 30),
             datetime.datetime(2020, 9, 1, 22, 0), datetime.datetime(2020, 9, 1, 22, 30),
             datetime.datetime(2020, 9, 1, 23, 0), datetime.datetime(2020, 9, 1, 23, 30),
             datetime.datetime(2020, 9, 2, 0, 0), datetime.datetime(2020, 9, 2, 0, 30),
             datetime.datetime(2020, 9, 2, 1, 0), datetime.datetime(2020, 9, 2, 1, 30),
             datetime.datetime(2020, 9, 2, 2, 0), datetime.datetime(2020, 9, 2, 2, 30),
             datetime.datetime(2020, 9, 2, 3, 0), datetime.datetime(2020, 9, 2, 3, 30),
             datetime.datetime(2020, 9, 2, 4, 0)]
    # prices = [-1000.0, 38.38961038961039, 36.073921928003074, 35.80692319894694, 38.38887158725215, 35.79446863741125, 38.38887158725215, 33.89266269698151, 39.796851193499236, 40.33909531611587, 54.511498197857875, 66.59926416529618, 65.57324118283478, 62.450588173504805, 39.796851193499236, 39.796851193499236, 44.00427729138909, 57.995352767215884, 68.4002031488065, 48.49994809508979, 42.92580042462126, 41.79579271421241, 57.995352767215884, 42.65829710305824, 41.52579271421241, 38.44983260626965, 35.30840726658217, 34.23997458057956, 35.14997458057956, 35.30840726658217, 32.50481891041899, 38.38887158725215, 58.01427644386762, 316.8499610661911, 319.0823393915827, 72.6666156488837, 62.34221669518306, 60.53075917945435, 49.57635945339224, 46.726851193499236, 39.79437611012494, 39.796851193499236, 38.38961038961039, 35.171025494961505, 39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 35.35905457180256, 32.50481891041899, 32.2298278356063, 28.338175420680397]
    # socs = [54.72222222222223, 54.722222222222214, 54.722222222222214, 54.722222222222214, 54.722222222222214, 65.09803921568627, 65.09803921568627, 93.43137254901961, 93.43137254901961, 93.43137254901961, 93.43137254901961, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 43.333333333333336, 66.66666666666666, 66.66666666666666, 95.0, 95.0, 95.0, 55.7843137254902, 16.568627450980387, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 21.666666666666668, 50.0, 50.0]
    # powers = [-20.0, 0.0, 0.0, 0.0, 0.0, -4.3944636678200695, 0.0, -20.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -20.0, -16.47058823529412, 0.0, -20.0, 0.0, 0.0, 20.0, 20.0, 0.7999999999999972, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -4.705882352941177, -20.0, 0.0]

    prices = [0.0, 38.38961038961039, 36.073921928003074, 35.80692319894694, 38.38887158725215, 35.79446863741125, 38.38887158725215, 33.89266269698151, 39.796851193499236, 40.33909531611587, 54.511498197857875, 66.59926416529618, 65.57324118283478, 62.450588173504805, 39.796851193499236, 39.796851193499236, 44.00427729138909, 57.995352767215884, 68.4002031488065, 48.49994809508979, 42.92580042462126, 41.79579271421241, 57.995352767215884, 42.65829710305824, 41.52579271421241, 38.44983260626965, 35.30840726658217, 34.23997458057956, 35.14997458057956, 35.30840726658217, 32.50481891041899, 38.38887158725215, 58.01427644386762, 316.8499610661911, 319.0823393915827, 72.6666156488837, 62.34221669518306, 60.53075917945435, 49.57635945339224, 46.726851193499236, 39.79437611012494, 39.796851193499236, 38.38961038961039, 35.171025494961505, 39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 35.35905457180256, 32.50481891041899, 32.2298278356063, 28.338175420680397]
    socs = [54.72222222222223, 54.722222222222214, 54.722222222222214, 54.722222222222214, 54.722222222222214, 65.09803921568627, 65.09803921568627, 93.43137254901961, 93.43137254901961, 93.43137254901961, 93.43137254901961, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 43.333333333333336, 66.66666666666666, 66.66666666666666, 95.0, 95.0, 95.0, 55.7843137254902, 16.568627450980387, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 21.666666666666668, 50.0, 50.0]
    powers = [-20.0, 0.0, 0.0, 0.0, 0.0, -4.3944636678200695, 0.0, -20.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -20.0, -16.47058823529412, 0.0, -20.0, 0.0, 0.0, 20.0, 20.0, 0.7999999999999972, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -4.705882352941177, -20.0, 0.0]

    # prices = [142.85714285714286, 38.38961038961039, 36.073921928003074, 35.80692319894694, 38.38887158725215,
    #           35.79446863741125, 38.38887158725215, 33.89266269698151, 39.796851193499236, 40.33909531611587,
    #           54.511498197857875, 66.59926416529618, 65.57324118283478, 62.450588173504805, 39.796851193499236,
    #           39.796851193499236, 44.00427729138909, 57.995352767215884, 68.4002031488065, 48.49994809508979,
    #           42.92580042462126, 41.79579271421241, 57.995352767215884, 42.65829710305824, 41.52579271421241,
    #           38.44983260626965, 35.30840726658217, 34.23997458057956, 35.14997458057956, 35.30840726658217,
    #           32.50481891041899, 38.38887158725215, 58.01427644386762, 316.8499610661911, 319.0823393915827,
    #           72.6666156488837, 62.34221669518306, 60.53075917945435, 49.57635945339224, 46.726851193499236,
    #           39.79437611012494, 39.796851193499236, 38.38961038961039, 35.171025494961505, 39.796644636502286,
    #           39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 35.35905457180256,
    #           32.50481891041899, 32.2298278356063, 28.338175420680397]
    # socs = [43.4640522875817, 43.464052287581694, 43.464052287581694, 43.464052287581694, 43.464052287581694,
    #         65.09803921568627, 65.09803921568627, 93.43137254901961, 93.43137254901961, 93.43137254901961,
    #         93.43137254901961, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814,
    #         54.215686274509814, 54.215686274509814, 54.215686274509814, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0,
    #         15.0, 43.333333333333336, 66.66666666666666, 66.66666666666666, 95.0, 95.0, 95.0, 55.7843137254902,
    #         16.568627450980387, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0,
    #         15.0, 21.666666666666668, 50.0, 50.0]
    # powers = [20.0, 0.0, 0.0, 0.0, 0.0, -9.162629757785469, 0.0, -20.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -20.0, -16.47058823529412, 0.0, -20.0, 0.0, 0.0, 20.0, 20.0, 0.7999999999999972, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -4.705882352941177, -20.0, 0.0]

    # prices = [214.28571428571428, 38.38961038961039, 36.073921928003074, 35.80692319894694, 38.38887158725215, 35.79446863741125, 38.38887158725215, 33.89266269698151, 39.796851193499236, 40.33909531611587, 54.511498197857875, 66.59926416529618, 65.57324118283478, 62.450588173504805, 39.796851193499236, 39.796851193499236, 44.00427729138909, 57.995352767215884, 68.4002031488065, 48.49994809508979, 42.92580042462126, 41.79579271421241, 57.995352767215884, 42.65829710305824, 41.52579271421241, 38.44983260626965, 35.30840726658217, 34.23997458057956, 35.14997458057956, 35.30840726658217, 32.50481891041899, 38.38887158725215, 58.01427644386762, 316.8499610661911, 319.0823393915827, 72.6666156488837, 62.34221669518306, 60.53075917945435, 49.57635945339224, 46.726851193499236, 39.79437611012494, 39.796851193499236, 38.38961038961039, 35.171025494961505, 39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 35.35905457180256, 32.50481891041899, 32.2298278356063, 28.338175420680397]
    # socs = [43.4640522875817, 43.464052287581694, 43.464052287581694, 43.464052287581694, 43.464052287581694, 65.09803921568627, 65.09803921568627, 93.43137254901961, 93.43137254901961, 93.43137254901961, 93.43137254901961, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 43.333333333333336, 66.66666666666666, 66.66666666666666, 95.0, 95.0, 95.0, 55.7843137254902, 16.568627450980387, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 21.666666666666668, 50.0, 50.0]
    # powers = [20.0, 0.0, 0.0, 0.0, 0.0, -9.162629757785469, 0.0, -20.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -20.0, -16.47058823529412, 0.0, -20.0, 0.0, 0.0, 20.0, 20.0, 0.7999999999999972, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -4.705882352941177, -20.0, 0.0]

    # prices = [500.0, 38.38961038961039, 36.073921928003074, 35.80692319894694, 38.38887158725215, 35.79446863741125, 38.38887158725215, 33.89266269698151, 39.796851193499236, 40.33909531611587, 54.511498197857875, 66.59926416529618, 65.57324118283478, 62.450588173504805, 39.796851193499236, 39.796851193499236, 44.00427729138909, 57.995352767215884, 68.4002031488065, 48.49994809508979, 42.92580042462126, 41.79579271421241, 57.995352767215884, 42.65829710305824, 41.52579271421241, 38.44983260626965, 35.30840726658217, 34.23997458057956, 35.14997458057956, 35.30840726658217, 32.50481891041899, 38.38887158725215, 58.01427644386762, 316.8499610661911, 319.0823393915827, 72.6666156488837, 62.34221669518306, 60.53075917945435, 49.57635945339224, 46.726851193499236, 39.79437611012494, 39.796851193499236, 38.38961038961039, 35.171025494961505, 39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 35.35905457180256, 32.50481891041899, 32.2298278356063, 28.338175420680397]
    # socs = [43.4640522875817, 43.464052287581694, 43.464052287581694, 43.464052287581694, 43.464052287581694, 65.09803921568627, 65.09803921568627, 93.43137254901961, 93.43137254901961, 93.43137254901961, 93.43137254901961, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 43.333333333333336, 66.66666666666666, 66.66666666666666, 95.0, 95.0, 95.0, 55.7843137254902, 16.568627450980387, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 21.666666666666668, 50.0, 50.0]
    # powers = [20.0, 0.0, 0.0, 0.0, 0.0, -9.162629757785469, 0.0, -20.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -20.0, -16.47058823529412, 0.0, -20.0, 0.0, 0.0, 20.0, 20.0, 0.7999999999999972, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -4.705882352941177, -20.0, 0.0]

    # prices = [15000.0, 38.38961038961039, 36.073921928003074, 35.80692319894694, 38.38887158725215, 35.79446863741125, 38.38887158725215, 33.89266269698151, 39.796851193499236, 40.33909531611587, 54.511498197857875, 66.59926416529618, 65.57324118283478, 62.450588173504805, 39.796851193499236, 39.796851193499236, 44.00427729138909, 57.995352767215884, 68.4002031488065, 48.49994809508979, 42.92580042462126, 41.79579271421241, 57.995352767215884, 42.65829710305824, 41.52579271421241, 38.44983260626965, 35.30840726658217, 34.23997458057956, 35.14997458057956, 35.30840726658217, 32.50481891041899, 38.38887158725215, 58.01427644386762, 316.8499610661911, 319.0823393915827, 72.6666156488837, 62.34221669518306, 60.53075917945435, 49.57635945339224, 46.726851193499236, 39.79437611012494, 39.796851193499236, 38.38961038961039, 35.171025494961505, 39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 39.796644636502286, 35.35905457180256, 32.50481891041899, 32.2298278356063, 28.338175420680397]
    # socs = [43.4640522875817, 43.464052287581694, 43.464052287581694, 43.464052287581694, 43.464052287581694, 65.09803921568627, 65.09803921568627, 93.43137254901961, 93.43137254901961, 93.43137254901961, 93.43137254901961, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 54.215686274509814, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 43.333333333333336, 66.66666666666666, 66.66666666666666, 95.0, 95.0, 95.0, 55.7843137254902, 16.568627450980387, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 21.666666666666668, 50.0, 50.0]
    # powers = [20.0, 0.0, 0.0, 0.0, 0.0, -9.162629757785469, 0.0, -20.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -20.0, -16.47058823529412, 0.0, -20.0, 0.0, 0.0, 20.0, 20.0, 0.7999999999999972, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -4.705882352941177, -20.0, 0.0]


    # path_to_fig = default.OUT_DIR / 'Cost-reflective Bands' / f'{prices[0]:.0f}.jpg'
    # plot_soc(times, prices, socs, path_to_fig, price_flag=True, soc_flag=True)
    path_to_fig = default.OUT_DIR / 'Cost-reflective Bands' / f'POWER {prices[0]:.0f}.jpg'
    plot_power(times, prices, powers, 'Power', path_to_fig)


def isgt2022_experiments():
    # energies = [3, 15, 30, 45, 60, 75, 90, 180, 270, 300, 360, 450, 540, 630, 720, 810, 900]  # price-taker
    # energies = [0.03, 3, 30, 120, 240, 360, 480, 720, 960, 1200, 2100, 3000]
    start = datetime.datetime(2021, 9, 12, 4, 5)
    # compare_revenue_by_size(start, energies, batteries, usage, '')
    # compare_revenue_by_usage_and_size(start)
    # compare_soc_by_size(start, batteries, usage)

    # Generate smarter price bands
    # for region_id in ['NSW1', 'SA1', 'VIC1', 'TAS1', 'QLD1']:
    # region_id = 'NSW1'
    # extract_prices(region_id)

    # Compare SOCs
    # start = datetime.datetime(2020, 9, 1, 4, 5)
    # b1 = Battery(30, 20, usage='basic-price-taker')
    # b2 = Battery(300, 200, usage='basic-price-taker')
    # times1, socs1, prices1 = read_battery_optimisation(b1.bat_dir / f'{default.get_case_datetime(start)}.csv')
    # times2, socs2, prices2 = read_battery_optimisation(b2.bat_dir / f'{default.get_case_datetime(start)}.csv')
    # for t, s1, s2 in zip(times1, socs1, socs2):
    #     if s1 != s2 and abs(s1 - s2) > 0.1:
    #         print(t, s1, s2)


class Unit:
    def __init__(self, duid, total_cleared):
        self.duid = duid
        self.total_cleared = total_cleared
        self.last_to_current = 0
        self.current_to_next = 0
        self.dispatch_type = None


def read_total_cleared(path_to_csv, battery):
    units = {}
    with path_to_csv.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                duid = row[1]
                if duid == 'G' or duid == 'L':
                    unit = battery.load if duid == 'L' else battery.generator
                    unit.total_cleared = float(row[2])
                    units[duid] = unit
                else:
                    unit = Unit(duid, float(row[2]))
                    units[duid] = unit
                # if len(row) > 4:
                #     unit.last_to_current = float(row[-4])
                #     unit.current_to_next = float(row[-3])
    return units


def read_costs(path_to_csv, battery):
    units = {}
    with path_to_csv.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                duid = row[1]
                if duid == 'G' or duid == 'L':
                    unit = battery.load if duid == 'L' else battery.generator
                    unit.total_cleared = float(row[2])
                    units[duid] = unit
                    unit.region_id = battery.region_id
                else:
                    unit = Unit(duid, float(row[2]))
                    units[duid] = unit
                    unit.region_id = 'NSW1'
                if duid == 'BLNKTAS':
                    unit.region_id = 'TAS1'
                elif duid == 'BLNKVIC':
                    unit.region_id = 'VIC1'
                if len(row) > 4:
                    # unit.last_to_current = float(row[-4])
                    # unit.current_to_next = float(row[-3])
                    unit.cost = float(row[-1])
                    unit.dispatch_type = row[-2]
                    unit.region_id = row[-3]
    return units


def calculate_metrics(start, batteries, usage):
    eff = 0.85
    for battery in batteries:
        transition_prices = []
        times, _, surplus_parts, total_costs, prices, battery_costs = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
        lmp_surplus = tlmp_surplus = surplus = sum(surplus_parts)
        for t, p in zip(times, prices):
            regional_prices = read_dispatch_prices(t, 'dispatch', True, None, path_to_out=battery.bat_dir)
            units = read_total_cleared(battery.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(t + default.FIVE_MIN)}.csv', battery)
            add_du_detail(units, start)
            add_du_detail_summary(units, start)
            for unit in units.values():
                lmp_surplus += ((-1) if unit.dispatch_type == 'LOAD' else 1) * regional_prices[unit.region_id][0] * unit.total_cleared * unit.transmission_loss_factor
                if unit.duid == 'G':
                    # print(f'{t} {unit.duid} {unit.current_to_next}')
                    transition_prices.append(unit.current_to_next)
                # elif unit.duid == 'L':
                #     print(f'{t} {unit.duid} {unit.current_to_next}')
        times, generations, loads, prices, generator_fcas, load_fcas, fcas_prices = read_battery_power(battery.bat_dir / f'{default.get_case_datetime(start)}.csv', usage)
        battery_lmp_surplus = battery_tlmp_surplus = battery_surplus = 0
        bidding_prices = [0.5] * 24
        uplift(times, prices, battery, bidding_prices, transition_prices)
        for g, l, p, c, tp in zip(generations, loads, prices, battery_costs, transition_prices):
            battery_lmp_surplus += (g - l) * p - c
            battery_surplus += g * (p + tp / eff) - l * (p + eff * tp) - c
            # print(f'{g} | {l} | {p} | {tp}')
        print(f'{battery.load.max_capacity}MW/{battery.size}MWh | {sum(total_costs):.4e} | {lmp_surplus:.4e} | {battery_lmp_surplus:.3e} | {battery_surplus:.3e}')


def uplift(times, prices, battery, bidding_prices, transition_prices=None):
    T = len(prices)
    tstep = 1
    E_initial = 0.5 * battery.size
    obj = 0
    with gp.Env() as env, gp.Model(env=env, name=f'price-taker_{battery.name}') as model:
        model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
        # Battery variables
        E = [model.addVar(lb=battery.Emin, ub=battery.Emax, name=f'E_{j}') for j in range(T)]  # Battery charge level (MWh)
        pgen = [model.addVar(ub=battery.generator.max_capacity,
                             name=f'energy_pgen_{j}') for j in range(T)]  # Generator / discharging power (MW)
        pload = [model.addVar(ub=battery.load.max_capacity,
                              name=f'energy_pload_{j}') for j in range(T)]  # Load / charging power (MW)
        model.addLConstr(E[0], gp.GRB.EQUAL,
                         E_initial + tstep * (pload[0] * battery.eff - pgen[0] / battery.eff),
                         'TRANSITION_0')
        for j in range(T):
            model.addSOS(type=gp.GRB.SOS_TYPE1, vars=[pgen[j], pload[j]])  # Charge or discharge
            if j >= 1:
                model.addLConstr(E[j], gp.GRB.EQUAL,
                                 E[j - 1] + tstep * (pload[j] * battery.eff - pgen[j] / battery.eff), f'TRANSITION_{j}')
            # Objective
            # obj += prices[j] * (battery.generator.transmission_loss_factor * pgen[j] -
            #                     battery.load.transmission_loss_factor * pload[j]) * tstep
            if transition_prices:
                obj += (prices[j] - bidding_prices[j] / battery.generator.transmission_loss_factor + transition_prices[j] / battery.eff) * pgen[j] - (prices[j] - bidding_prices[j] / battery.load.transmission_loss_factor + transition_prices[j] * battery.eff) * pload[j] * tstep
            else:
                obj += (prices[j] - bidding_prices[j]) * (pgen[j] - pload[j]) * tstep
        model.addLConstr(E[-1] >= 0.5 * battery.size, 'FINAL_STATE')
        model.setObjective(obj, gp.GRB.MAXIMIZE)
        model.optimize()
        print(f'{battery.load.max_capacity}MW/{battery.size}MWh | {obj.getValue():.3e}')
        if battery.size == 0:
            return None
        from plot import plot_soc
        socs = [e.x * 100 / battery.size for e in E]
        plot_soc(times, prices, socs, None, price_flag=True, soc_flag=True)


def paper_experiment():
    # usage = 'DER None Integrated Hour No-losses'
    usage = 'DER None Elastic Bilevel Hour No-losses'
    # usage = 'DER None Inelastic Bilevel Hour'
    start = datetime.datetime(2021, 7, 18, 4, 30)
    # start = datetime.datetime(2020, 9, 1, 4, 30)
    # energies = [0]
    energies = [0, 30, 300, 3000]
    batteries = generate_batteries_by_energies(energies, usage)
    # for battery in batteries:
    #     calculate_revenue(start, battery, usage, print_flag=2, total_intervals=24)
    print(usage)
    # calculate_metrics(start, batteries, usage)


def calculate_total_operational_costs(start, battery, days=1, print_flag=True):
    total_costs, surplus_parts = [], []
    for day in range(days):
        current = start + day * default.ONE_DAY
        times, _, surplus, costs, prices, battery_costs = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(current)}.csv')
        total_costs += costs
        surplus_parts += surplus
    if print_flag:
        return get_scientific_notation(f'{sum(total_costs) / days:.4e}'), get_scientific_notation(f'{sum(surplus_parts) / days:.4e}')
    else:
        return sum(total_costs) / days, sum(surplus_parts) / days


def calculate_payment(start, battery, days=1, print_flag=True):
    payment = 0
    for day in range(days):
        current = start + day * default.ONE_DAY
        times, _, _, _, prices, _ = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(current)}.csv')
        for t, p in zip(times, prices):
            # if 'reflective' in battery.usage:
            #     regional_prices = {k: [p] for k in ['NSW1', 'VIC1', 'TAS1', 'SA1', 'QLD1']}
            # else:
            regional_prices = read_dispatch_prices(t, 'dispatch', True, None, path_to_out=battery.bat_dir)
            units = read_costs(battery.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(t + default.FIVE_MIN)}.csv',battery)
            for unit in units.values():
                # if abs(regional_prices[unit.region_id][0] - p) > 1:
                #     print(battery.usage, t, unit.region_id, p, regional_prices[unit.region_id][0])
                if unit.duid == 'G':
                    payment += regional_prices[unit.region_id][0] * unit.total_cleared
                elif unit.duid == 'L':
                    payment -= regional_prices[unit.region_id][0] * unit.total_cleared
                elif unit.dispatch_type == 'GENERATOR':
                    payment += regional_prices[unit.region_id][0] * unit.total_cleared
                elif unit.dispatch_type == 'LOAD':
                    payment -= regional_prices[unit.region_id][0] * unit.total_cleared
                # if unit.duid == 'G':
                #     payment += p * unit.total_cleared
                # elif unit.duid == 'L':
                #     payment -= p * unit.total_cleared
                # elif unit.dispatch_type == 'GENERATOR':
                #     payment += p * unit.total_cleared
                # elif unit.dispatch_type == 'LOAD':
                #     payment -= p * unit.total_cleared
    if print_flag:
        return get_scientific_notation(f'{payment / days:.4e}')
    else:
        return payment / days


def calculate_profits(start, batteries):
    print('| Model | Battery Size | Generator | Load | Battery |')
    print('|-------|--------------|-----------|------|---------|')
    for battery in batteries:
        generator_profits, load_profits, battery_profits = 0, 0, 0
        times, _, surplus_parts, total_costs, prices, battery_costs = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
        for t, p in zip(times, prices):
            # if 'reflective' in battery.usage:
            #     regional_prices = {k: [p] for k in ['NSW1', 'VIC1', 'TAS1', 'SA1', 'QLD1']}
            # else:
            regional_prices = read_dispatch_prices(t, 'dispatch', True, None, path_to_out=battery.bat_dir)
            units = read_costs(battery.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(t + default.FIVE_MIN)}.csv', battery)
            for unit in units.values():
                if unit.duid == 'G':
                    battery_profits += regional_prices[unit.region_id][0] * unit.total_cleared - unit.cost
                elif unit.duid == 'L':
                    battery_profits -= regional_prices[unit.region_id][0] * unit.total_cleared - unit.cost
                elif unit.dispatch_type == 'GENERATOR':
                    generator_profits += regional_prices[unit.region_id][0] * unit.total_cleared - unit.cost
                elif unit.dispatch_type == 'LOAD':
                    load_profits -= regional_prices[unit.region_id][0] * unit.total_cleared - unit.cost
        print(f'| {get_label(battery.usage, battery.size)} | {battery.load.max_capacity}MW/{battery.size}MWh | {generator_profits:.4e} | {load_profits:.4e} | {battery_profits:.4e} |')


def calculate_battery_revenue(start, battery, days=1, print_flag=True):
    if battery.size == 0:
        return 0, 0
    revenue = 0
    for day in range(days):
        current = start + day * default.ONE_DAY
        times, _, surplus_parts, total_costs, prices, battery_costs = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(current)}.csv')
        for t, p in zip(times, prices):
            units = read_costs(battery.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(t + default.FIVE_MIN)}.csv', battery)
            for unit in units.values():
                if unit.duid == 'G':
                    revenue += p * unit.total_cleared
                elif unit.duid == 'L':
                    revenue -= p * unit.total_cleared
    if print_flag:
        return get_scientific_notation(f'{revenue / days:.4e}'), f'{(revenue / days / battery.size):.2f}'
    else:
        return revenue / days, revenue / days / battery.size


def get_scientific_notation(number: str) -> str:
    if number == '0.0000e+00':
        return '0'
    return '$' + '\\times 10^'.join(number.split(('e+0' if 'e+0' in number else 'e-0'))) + '$'


def get_color(label: str) -> str:
    # if 'Perfect' in label:
    if 'Single-period' in label and 'No Storage' in label:
        return default.BROWN
    elif 'Single-period' in label and 'Inflexible' in label:
        return default.INDIGO
    elif 'Look-ahead' in label and 'No Storage' in label and 'Perfect' in label:
        return default.BROWN
    elif 'Look-ahead' in label and 'No Storage' in label and 'Renewable' in label:
        return default.BROWN
    elif 'Look-ahead' in label and 'No Storage' in label:
        return default.GREEN
    elif 'Look-ahead' in label and 'Integrated' in label:
        return default.PURPLE
    elif 'Look-ahead' in label and 'Strategic' in label:
        return default.BLUE


def get_label(usage, size):
    label = 'Look-ahead' if 'DER' in usage else 'Single-period'
    if size == 30:
        label += ' + Small'
    elif size == 3000:
        label += ' + Medium'
    elif size == 15000:
        label += ' + Large'
    if size == 0:
        label += ' + No Storage'
    elif 'taker' in usage:
        label += ' Inflexible'
    elif 'Integrated' in usage:
        label += ' Integrated'
    else:
        label += ' Strategic'
    label += ' + Perfect' if 'Perfect' in usage else ''
    label += ' + High Renewable' if 'Renewable' in usage else ''
    return label
    # if size == 0:
    #     if 'Perfect' in usage and 'Integrated' in usage:
    #         return 'Look-ahead + Perfect'
    #     if 'DER' in usage:
    #         return 'Look-ahead + No Storage'
    #     else:
    #         return 'Single-period + No Storage'
    # if 'Perfect' in usage and 'Integrated' in usage:
    #     return 'Look-ahead + Integrated + Perfect'
    # elif 'Perfect' in usage:
    #     return 'Look-ahead + Strategic + Perfect'
    # if 'Renewable' in usage and 'Integrated' in usage:
    #     return 'Look-ahead + Integrated + Renewable'
    # elif 'Renewable' in usage and 'taker' in usage:
    #     return 'Single-period + Price-taker + Renewable'
    # elif 'Renewable' in usage:
    #     return 'Look-ahead + Strategic + Renewable'
    # if 'Integrated' in usage:
    #     # return 'Integrated'
    #     return 'Look-ahead + Integrated'
    # elif 'Inelastic' in usage:
    #     # return 'Price-inelastic'
    #     # return 'Strategic'
    #     return 'Look-ahead + Strategic'
    # elif 'Elastic' in usage:
    #     return 'Look-ahead + Strategic'
    # elif 'taker' in usage:
    #     return 'Single-period + Price-taker'
    # elif 'reflective' in usage:
    #     return 'Single-period + Cost-reflective'
    # else:
    #     print('Usage Error!!!')


def calculate_price_volatility(start, battery, days=1, print_flag=True):
    prices = []
    for day in range(days):
        current = start + day * default.ONE_DAY
        times, _, _, _, price, _ = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(current)}.csv')
        prices += price
    if print_flag:
        return f'{np.mean(prices):.2f}', f'{np.std(prices):.2f}'
    else:
        return np.mean(prices), np.std(prices)


def plot_prices(start, batteries, path_to_dir, filename=None, days=1, ylim_flag=True):
    # fig, ax1 = plt.subplots()
    fig, ax1 = plt.subplots(figsize=(6, 2))
    # ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # ax1.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    # ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
    if ylim_flag:
        ax1.set_ylim([-35, 130])
    ax1.set_xlabel('Time (Hour)')
    ax1.set_ylabel('Price ($/MWh)')

    # battery = batteries[0]
    # times, _, _, _, price, _ = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
    # non_time_stepped_prices = []
    # for t in times:
    #     rrp, _, _, _ = read_dispatch_prices(t, 'dispatch', True, battery.region_id,
    #                                         path_to_out=(default.OUT_DIR / 'Non-Look-ahead No-losses'))
    #     non_time_stepped_prices.append(rrp)
    # ax1.plot(times, non_time_stepped_prices, label='Single-period', alpha=0.4, linewidth=2.5, color=default.BROWN)
    # print(f'Single-period & {np.mean(non_time_stepped_prices):.2f} & {np.std(non_time_stepped_prices):.2f}')
    # label = 'No battery'
    # label = 'Price-taker'
    # ax1.plot(times, price, label=label, alpha=0.6, linewidth=2, color=default.GREEN)
    # print(f'{label} & {np.mean(price):.2f} & {np.std(price):.2f}')

    ncol = 0
    for battery, color in zip(batteries, default.COLOR_LIST):
        prices = []
        for day in range(days):
            current = start + day * default.ONE_DAY
            times, _, _, _, price, _ = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(current)}.csv')
            prices += price
        label = get_label(battery.usage, battery.size)
        ncol += 1
        # if 'Renewable' in label:
        #     if 'Integrated' in label:
        #         label = label.replace('Integrated', 'Strategic')
        #     elif 'Strategic' in label:
        #         label = label.replace('Strategic', 'Integrated')
        ax1.plot(range(1, len(prices) + 1), prices, label=label, color=get_color(label))

    ax1.legend(frameon=True)
    # ax1.legend(loc='lower center', bbox_to_anchor=(0.5, 1), ncol=ncol, fontsize=8)
    # plt.show()
    path_to_fig = path_to_dir / (f'Price_{battery.size}.jpg' if filename is None else filename)
    plt.savefig(path_to_fig)
    plt.close(fig)


def plot_socs(start, batteries, path_to_dir, filename=None, days=1):
    # from matplotlib.pyplot import figure
    fig, ax1 = plt.subplots(figsize=(6, 2))
    # fig, ax1 = plt.subplots()
    # ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # ax1.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    # ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
    ax1.set_ylim([0, 100])

    ncol = 0
    for battery, color in zip(batteries, default.COLOR_LIST):
        if battery.size != 0:
            socs = []
            for day in range(days):
                current = start + day * default.ONE_DAY
                times, soc, _, _, _, _ = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(current)}.csv')
                socs += soc
            label = get_label(battery.usage, battery.size)
            ncol += 1
            # if 'Renewable' in label:
            #     if 'Integrated' in label:
            #         label = label.replace('Integrated', 'Strategic')
            #     elif 'Strategic' in label:
            #         label = label.replace('Strategic', 'Integrated')
            ax1.plot(range(1, len(socs) + 1), socs, label=label, color=get_color(label))

    ax1.set_xlabel('Time (Hour)')
    ax1.set_ylabel('SOC (%)')

    ax1.legend(frameon=True)
    # ax1.legend(loc='lower center', bbox_to_anchor=(0.5, 1), ncol=(ncol if ncol == 3 else 2), fontsize='small')
    # plt.show()
    path_to_fig = path_to_dir / (f'SOC_{battery.size}.jpg' if filename is None else filename)
    plt.savefig(path_to_fig)
    plt.close(fig)


def print_table(battery_list, start, days):
    for battery in battery_list:
        if battery is None:
            print('\\hline')
            continue
        average, deviation = calculate_price_volatility(start, battery, days)
        obj, cost = calculate_total_operational_costs(start, battery, days)
        payment = calculate_payment(start, battery, days)
        revenue, rate = calculate_battery_revenue(start, battery, days)
        print(f'{get_label(battery.usage, battery.size)} & ${average}$ & ${deviation}$ & {obj} & {cost} & {revenue} \\\\')
    print()
    

def plot_table(case, battery_list, start, days):
    average_list, deviation_list, obj_list, cost_list, revenue_list = [], [], [], [], []
    for batteries in battery_list:
        averages, deviations, objs, costs, revenues = [], [], [], [], []
        for battery in batteries:
            if battery is None:
                average, deviation, obj, cost, revenue = 0, 0, 0, 0, 0
            else:
                average, deviation = calculate_price_volatility(start, battery, days, False)
                obj, cost = calculate_total_operational_costs(start, battery, days, False)
                payment = calculate_payment(start, battery, days, False)
                revenue, rate = calculate_battery_revenue(start, battery, days, False)
            averages.append(average)
            deviations.append(deviation)
            objs.append(obj)
            costs.append(cost)
            revenues.append(revenue)
        average_list.append(averages)
        deviation_list.append(deviations)
        obj_list.append(objs)
        cost_list.append(costs)
        revenue_list.append(revenues)
    ylabels = ['Average Price (\$/MWh)', 'Standard Deviation', 'Total Objective (\$)', 'Total Cost (\$)']
    names = ['Price', 'Deviation', 'Objective', 'Cost']
    sequences = [average_list, deviation_list, obj_list, cost_list]
    ylims = [66, 63, 4.5 * 10e8, 3.2 * 10e6]
    categories = ['Small', 'Meidum', 'Large']
    types = ['Inflexible', 'Integrated', 'Strategic'] if case == 'Current' else ['Integrated', 'Strategic']
    colors = [default.BROWN, default.PURPLE, default.BLUE] if case == 'Current' else [default.PURPLE, default.BLUE]
    for ylabel, name, sequence, ylim in zip(ylabels, names, sequences, ylims):
        path_to_fig = default.EXPERIMENT_DIR / 'bilevel' / f'{name}_{case}.jpg'
        plot_grouped_bar(np.array(sequence[1:]).transpose(), types, ylabel, categories, None, path_to_fig, colors, None, sequence[0])


def experiments():
    days = 3
    check_sign = ''
    # check_sign = ' Ramp'
    renewable_no = ' 571'
    elastic_flag = True
    # path_to_dir = default.EXPERIMENT_DIR / 'PESGM2023'
    path_to_dir = default.EXPERIMENT_DIR / 'bilevel'
    u1 = f'DER None Integrated Hour No-losses{check_sign}'
    # u2 = 'DER None Elastic Bilevel Hour No-losses'
    u4 = 'Cost-reflective Hour Test'
    u3 = f'Price-taker Hour{check_sign}'
    # u3 = 'Price-taker 5MIN'
    # u4 = 'Cost-reflective 5MIN'
    u2 = f'DER None Elastic Bilevel Hour No-losses{check_sign}' if elastic_flag else f'DER None Inelastic Bilevel Hour No-losses{check_sign}'
    u5 = f'DER None Integrated Hour No-losses Perfect{check_sign}'
    u6 = f'DER None Elastic Bilevel Hour No-losses Perfect{check_sign}' if elastic_flag else f'DER None Inelastic Bilevel Hour No-losses Perfect{check_sign}'
    u7 = f'DER None Integrated Hour No-losses Renewable{renewable_no}{check_sign}'
    u8 = f'DER None Elastic Bilevel Hour No-losses Renewable{renewable_no}{check_sign}' if elastic_flag else f'DER None Inelastic Bilevel Hour No-losses Renewable{renewable_no}{check_sign}'
    u9 = 'Price-taker Hour Renewable'
    start = datetime.datetime(2021, 7, 18, 4, 30)
    # start = datetime.datetime(2021, 9, 12, 4, 5)
    # start = datetime.datetime(2022, 1, 2, 4, 30)
    # start = datetime.datetime(2020, 9, 1, 4, 30)
    # start = datetime.datetime(2021, 9, 12, 4, 30)
    energies = [0, 30, 300, 3000, 15000]
    # energies = [0, 30]
    integrated = generate_batteries_by_energies(energies, u1)
    strategic = generate_batteries_by_energies(energies, u2)
    price_taker = generate_batteries_by_energies(energies, u3)
    cost_reflective = generate_batteries_by_energies(energies, u4)
    integrated_perfect = generate_batteries_by_energies(energies, u5)
    strategic_perfect = generate_batteries_by_energies(energies, u6)
    integrated_renewable = generate_batteries_by_energies(energies, u7)
    strategic_renewable = generate_batteries_by_energies(energies, u8)
    price_taker_renewable = generate_batteries_by_energies(energies, u9)

    # # Plot figures:
    # # Case I: No Storage
    no_storage_list = [[price_taker[0], integrated[0]], [integrated[0], integrated_perfect[0]], [integrated[0], integrated_renewable[0]]]
    for batteries, case in zip(no_storage_list, ['', 'Perfect', 'Renewable']):
        plot_prices(start, batteries, path_to_dir, f'PriceNoStorage{case}.jpg', days)
    # Case II: Small Storage Capacity
    small_storage_list = [[integrated[0], integrated[1], strategic[1], price_taker[1]]]
    for batteries in small_storage_list:
        plot_prices(start, batteries, path_to_dir, 'PriceSmallStorage.jpg', days)
    for batteries in small_storage_list:
        plot_socs(start, batteries, path_to_dir, 'SOCSmallStorage.jpg', days)
    # Case III: Large Storage Capacity
    large_storage_list = [[integrated[3], strategic[3], price_taker[3]]]
    for batteries in large_storage_list:
        plot_prices(start, batteries, path_to_dir, 'PriceLargeStorage.jpg', days, ylim_flag=False)
    for batteries in large_storage_list:
        plot_socs(start, batteries, path_to_dir, 'SOCLargeStorage.jpg', days)
    # # Case IV: Perfect Demand Forecast
    perfect_list = [[integrated[0], integrated[1], strategic[1], integrated_perfect[1], strategic_perfect[1]], [integrated[0], integrated[3], strategic[3], integrated_perfect[3], strategic_perfect[3]]]
    perfect_only_list = [[integrated_perfect[0], integrated_perfect[1], strategic_perfect[1]], [integrated_perfect[0], integrated_perfect[3], strategic_perfect[3]]]
    for batteries, capacity in zip(perfect_only_list, ['SmallStorage', 'LargeStorage']):
        plot_prices(start, batteries, path_to_dir, f'Price{capacity}Perfect.jpg', days)
    for batteries, capacity in zip(perfect_only_list, ['SmallStorage', 'LargeStorage']):
        plot_socs(start, batteries, path_to_dir, f'SOC{capacity}Perfect.jpg', days)
    # Case V: High Renewable Penetration
    # renewable_list = [[integrated[0], integrated_renewable[1], strategic_renewable[1], price_taker_renewable[1]], [integrated[0], integrated_renewable[3], strategic_renewable[3], price_taker_renewable[3]]]
    renewable_list = [[integrated_renewable[0], integrated_renewable[1], strategic_renewable[1]], [integrated_renewable[0], integrated_renewable[3], strategic_renewable[3]], [integrated_renewable[0], integrated_renewable[4], strategic_renewable[4]]]
    for batteries, capacity in zip(renewable_list, ['SmallStorage', 'LargeStorage']):
        plot_prices(start, batteries, path_to_dir, f'Price{capacity}Renewable.jpg', days)
    for batteries, capacity in zip(renewable_list, ['SmallStorage', 'LargeStorage']):
        plot_socs(start, batteries, path_to_dir, f'SOC{capacity}Renewable.jpg', days)
    # renewable_list = [[integrated[0], integrated_renewable[0], integrated_renewable[1]], [integrated[0], integrated_renewable[0], integrated_renewable[3]]]
    # for batteries in renewable_list:
    #     calculate_total_operational_costs(start, batteries, {}, {})
    #     calculate_payment(start, batteries, {})
    # Case VI: Extra Large Storage Capacity
    extra = [[integrated[0], integrated[4], strategic[4]], [integrated_perfect[0], integrated_perfect[4], strategic_perfect[4]], [integrated_renewable[0], integrated_renewable[4], strategic_renewable[4]]]
    for batteries, case_type in zip(extra, ['', 'Perfect', 'Renewable']):
        plot_prices(start, batteries, path_to_dir, f'PriceExtraLargeStorage{case_type}', days)
        plot_socs(start, batteries, path_to_dir, f'SOCExtraLargeStorage{case_type}', days)

    # Formulate tables:
    # Current market settings
    current_list = [integrated[0], integrated[1], strategic[1], None,
                    price_taker[0], price_taker[1], None,
                    integrated[3], strategic[3], price_taker[3], None,
                    integrated[4], strategic[4]
                    ]
    print_table(current_list, start, days)
    # Perfect demand forecast
    perfect_list = [integrated_perfect[0], None,
                    integrated_perfect[1], strategic_perfect[1], None,
                    integrated_perfect[3], strategic_perfect[3], None,
                    integrated_perfect[4], strategic_perfect[4]]
    print_table(perfect_list, start, days)
    # High renewable penetration
    renewable_list = [integrated_renewable[0], None,
                      integrated_renewable[1], strategic_renewable[1], None,
                      integrated_renewable[3], strategic_renewable[3], None,
                      integrated_renewable[4], strategic_renewable[4]]
    print_table(renewable_list, start, days)

    # current_list = [[integrated[0], price_taker[0]],
    #                 [price_taker[1], integrated[1], strategic[1]],
    #                 [price_taker[3], integrated[3], strategic[3]],
    #                 [None, integrated[4], strategic[4]]]
    # plot_table('Current', current_list, start, days)
    # perfect_list = [integrated_perfect[0], None,
    #                 integrated_perfect[1], strategic_perfect[1], None,
    #                 integrated_perfect[3], strategic_perfect[3], None,
    #                 integrated_perfect[4], strategic_perfect[4]]
    # plot_table('Perfect', perfect_list, start, days)
    # renewable_list = [integrated_renewable[0], None,
    #                   integrated_renewable[1], strategic_renewable[1], None,
    #                   integrated_renewable[3], strategic_renewable[3], None,
    #                   integrated_renewable[4], strategic_renewable[4]]
    # plot_table('Renewable', renewable_list, start, days)
    


def check():
    start = datetime.datetime(2021, 7, 18, 4, 30)
    u1 = 'DER None Integrated Hour No-losses Renewable'
    u5 = 'DER None Integrated Hour No-losses Renewable 0'
    # u2 = 'DER None Elastic Bilevel Hour No-losses'
    u4 = 'Cost-reflective Hour Test'
    u3 = 'Price-taker Hour'
    u2 = 'DER None Inelastic Bilevel Hour No-losses'
    b1 = Battery(0, 0, usage=u1)
    b2 = Battery(0, 0, usage=u5)


def plot_grouped_bar(values, types, ylabel, categories=None, filename=None, path_to_fig=None, colors=None, ylim=None, hline=None):
    # Sample data
    if categories is None:
        categories = ['LMP', 'TLMP', 'TDLMP']
    # types = scales
    # values = np.array([[10, 15, 12], [8, 10, 14], [13, 9, 11]])

    # Determine the width of each bar
    bar_width = 0.2

    # Create a figure and axes
    # fig, ax = plt.subplots()
    fig, ax = plt.subplots(figsize=(4, 2))

    # Generate the x-axis positions for each category and type
    x_positions = np.arange(len(categories))

    if colors is None:
        colors = [default.BLUE, default.PURPLE, default.BROWN]

    if ylim is not None:
        if type(ylim) == list:
            ax.set_ylim(ylim)
        else:
            plt.ylim(0, ylim)

    formatter = ticker.ScalarFormatter(useMathText=True)
    formatter.set_powerlimits((-3, 3))  # Adjust the power limits as needed
    plt.gca().yaxis.set_major_formatter(formatter)

    if hline:
        if type(hline) == list:
            ax.axhline(hline[0], linestyle='--', label='Look-ahead + No Storage', color=default.GREEN)
            ax.axhline(hline[1], linestyle='dotted', label='Single-period + No Storage', color=default.RED)
        else:
            ax.axhline(hline, linestyle='--', label='No Storage', color=default.GREEN)
        # ax.text(1.02, hline, "No Storage", va='center', ha="left", bbox=dict(facecolor="w", alpha=0.5), transform=ax.get_yaxis_transform())
    if ylabel == 'Small Storage Revenue (\$)':
        ax2 = ax.twinx()
        ax2.set_ylabel('Medium/large Storage Revenue (\$)')
        ax2.set_ylim([-0.5 * 10e4, 4 * 10e4])
        ax2.yaxis.set_major_formatter(formatter)
        ax.axvline(x=0.65)

    # Plot the bars for each type
    for i in range(len(types)):
        if ylabel == 'Small Storage Revenue (\$)':
            ax.bar(x_positions + i * bar_width, values[0][:, i], width=bar_width, label=types[i], color=colors[i], alpha=0.65)
            ax2.bar(x_positions + i * bar_width, values[1][:, i], width=bar_width, label=types[i], color=colors[i], alpha=0.65)
        else:
            bars = ax.bar(x_positions + i * bar_width, values[:, i], width=bar_width, label=types[i], color=colors[i], alpha=0.65)
        # for rect in bars:
        #     height = rect.get_height()
        #     plt.text(rect.get_x() + rect.get_width() / 2.0, height, '%d' % int(height), ha='center', va='bottom')

    # Customize the plot
    # ax.set_xlabel('Categories')
    ax.set_ylabel(ylabel)
    ax.set_xticks(x_positions + (len(types) - 1) * bar_width / 2)
    ax.set_xticklabels(categories)
    # ax.legend()
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), ncol=(4 if len(types) == 4 else 3), fontsize='small')
    # Display the plot
    if filename is None:
        if path_to_fig is None:
            plt.show()
        else:
            # plt.show()
            plt.savefig(path_to_fig)
    else:
        plt.savefig(default.EXPERIMENT_DIR / 'pricing' / f'{filename}.jpg')
        plt.close(fig)


def bar(case, ylabel, sequence, name, ylim, scale):
    if case == 'Current':
        values = [
            [sequence[4], sequence[7], 0],
            [sequence[1], sequence[5], sequence[8]],
            [sequence[2], sequence[6], sequence[9]]
        ]
        categories = ['Small', 'Meidum', 'Large']
        hline = [sequence[0] * scale, sequence[3] * scale]
    else:
        values = [
            [sequence[1], sequence[3], sequence[5]],
            [sequence[2], sequence[4], sequence[6]]
        ]
        categories = ['Small', 'Meidum', 'Large']
        hline = sequence[0] * scale
    values = [[element * scale for element in row] for row in values]
    types = ['Inflexible', 'Integrated', 'Strategic'] if case == 'Current' else ['Integrated', 'Strategic']
    colors = [default.BROWN, default.PURPLE, default.BLUE] if case == 'Current' else [default.PURPLE, default.BLUE]
    path_to_fig = default.EXPERIMENT_DIR / 'bilevel' / f'{name}_{case}.jpg'
    plot_grouped_bar(np.array(values).transpose(), types, ylabel, categories, None, path_to_fig, colors, ylim, hline)


def bar_experiments(table, case):
    # ylabel = 'Average Price'
    # name = 'Average_Price'
    #
    # case = 'Current'
    # sequence = [52.86, 52.86, 52.86, 52.53, 52.53, 52.52, 51.40, 63.25, 52.62, 51.11]
    # bar(case, ylabel, sequence, name)
    #
    # case = 'Perfect'
    # sequence = [52.86, 52.87, 52.86, 52.94, 51.84, 49.26, 51.59]
    # bar(case, ylabel, sequence, name)
    average_prices, standard_deviation, total_obj, total_cost, storage_revenue = [], [], [], [], []
    for line in table.split('\n'):
        line_list = line.split(' & ')
        average_prices.append(float(line_list[1][1:-1]))
        standard_deviation.append(float(line_list[2][1:-1]))
        total_obj.append(float(line_list[3][1:7]))
        total_cost.append(float(line_list[4][1:7]))
        storage_revenue.append(float(line_list[5][1:7]))
    ylabels = ['Average Price (\$/MWh)', 'Standard Deviation', 'Total Objective (\$)', 'Total Cost (\$)']
    names = ['Price', 'Deviation', 'Objective', 'Cost']
    sequences = [average_prices, standard_deviation, total_obj, total_cost]
    ylims = [66, 63, 4.5 * 10e8, 4 * 10e6]
    scales = [1, 1, 10e8, 10e6]
    for ylabel, name, sequence, ylim, scale in zip(ylabels, names, sequences, ylims, scales):
        bar(case, ylabel, sequence, name, ylim, scale)

    name = 'Revenue'
    ylabel = 'Small Storage Revenue (\$)'
    ylim = [-0.5 * 10e2, 4 * 10e2]
    sequence = storage_revenue
    # if case == 'Current':
    #     values = [
    #         [sequence[4], sequence[7], 0],
    #         [sequence[1], sequence[5], sequence[8]],
    #         [sequence[2], sequence[6], sequence[9]]
    #     ]
    # else:
    #     values = [
    #         [sequence[1], sequence[3], sequence[5]],
    #         [sequence[2], sequence[4], sequence[6]]
    #     ]
    if case == 'Current':
        values1 = [
            [sequence[4], 0, 0],
            [sequence[1], 0, 0],
            [sequence[2], 0, 0]
        ]
        values2 = [
            [0, sequence[7], 0],
            [0, sequence[5], sequence[8]],
            [0, sequence[6], sequence[9]]
        ]
    else:
        values1 = [
            [sequence[1], 0, 0],
            [sequence[2], 0, 0]
        ]
        values2 = [
            [0, sequence[3], sequence[5]],
            [0, sequence[4], sequence[6]]
        ]
    values1 = [[element * 10e2 for element in row] for row in values1]
    values2 = [[element * 10e4 for element in row] for row in values2]
    types = ['Inflexible', 'Integrated', 'Strategic'] if case == 'Current' else ['Integrated', 'Strategic']
    colors = [default.BROWN, default.PURPLE, default.BLUE] if case == 'Current' else [default.PURPLE, default.BLUE]
    categories = ['Small', 'Meidum', 'Large']
    path_to_fig = default.EXPERIMENT_DIR / 'bilevel' / f'{name}_{case}.jpg'
    plot_grouped_bar([np.array(values1).transpose(), np.array(values2).transpose()], types, ylabel, categories, None, path_to_fig, colors, ylim)

    name = 'Normalised_Revenue'
    ylabel = 'Normalised Storage Revenue (\$/MWh)'
    # ylim = [-0.5 * 10e2, 4 * 10e2]
    sequence = storage_revenue
    if case == 'Current':
        values = [
            [sequence[4] * 10e2 / 30, sequence[7] * 10e4 / 300, 0],
            [sequence[1] * 10e2 / 30, sequence[5] * 10e4 / 300, sequence[8] * 10e4 / 3000],
            [sequence[2] * 10e2 / 30, sequence[6] * 10e4 / 300, sequence[9] * 10e4 / 3000]
        ]
        categories = ['Small', 'Meidum', 'Large']
    else:
        values = [
            [sequence[1] * 10e2 / 30, sequence[3] * 10e4 / 300, sequence[5] * 10e4 / 3000],
            [sequence[2] * 10e2 / 30, sequence[4] * 10e4 / 300, sequence[6] * 10e4 / 3000]
        ]
        categories = ['Small', 'Meidum', 'Large']
    types = ['Inflexible', 'Integrated', 'Strategic'] if case == 'Current' else ['Integrated', 'Strategic']
    colors = [default.BROWN, default.PURPLE, default.BLUE] if case == 'Current' else [default.PURPLE, default.BLUE]
    path_to_fig = default.EXPERIMENT_DIR / 'bilevel' / f'{name}_{case}.jpg'
    plot_grouped_bar(np.array(values).transpose(), types, ylabel, categories, None, path_to_fig, colors, [-200, 800])


def process_table():
    table = """Look-ahead + No Storage & $52.86$ & $35.60$ & $2.3031\times 10^9$ & $2.8127\times 10^7$ & $0.0000000000000$
		Look-ahead + Small Integrated & $52.86$ & $35.60$ & $2.3031\times 10^9$ & $2.8127\times 10^7$ & $0.85851\times 10^3$
		Look-ahead + Small Strategic & $52.86$ & $35.60$ & $2.3031\times 10^9$ & $2.8127\times 10^7$ & $2.2295\times 10^3$
		Single-period + No Storage & $52.53$ & $35.41$ & $3.8677\times 10^9$ & $2.7955\times 10^7$ & $0.0000000000000$
		Single-period + Small Price-taker & $52.53$ & $35.41$ & $3.8672\times 10^9$ & $2.7955\times 10^7$ & $0.5838\times 10^3$
		Look-ahead + Medium Integrated & $52.52$ & $30.85$ & $2.3028\times 10^9$ & $2.7208\times 10^7$ & $1.9764\times 10^5$
		Look-ahead + Medium Strategic & $52.40$ & $32.47$ & $2.3028\times 10^9$ & $2.7733\times 10^7$ & $2.0698\times 10^5$
		Single-period + Medium Price-taker & $63.25$ & $59.61$ & $4.3890\times 10^9$ & $3.9044\times 10^7$ & $-0.4557\times 10^5$
		Look-ahead + Large Integrated & $52.62$ & $15.25$ & $2.3028\times 10^9$ & $2.6765\times 10^7$ & $0.40167\times 10^5$
		Look-ahead + Large Strategic & $53.11$ & $26.64$ & $2.3030\times 10^9$ & $2.6874\times 10^7$ & $1.8591\times 10^5$"""
    case = 'Current'
    bar_experiments(table, case)

    table ="""Look-ahead + No Storage + Perfect & $52.86$ & $35.60$ & $2.3031\times 10^9$ & $2.8127\times 10^7$ & $0.0000000000000$
		Look-ahead + Small Integrated + Perfect & $52.87$ & $35.60$ & $2.3031\times 10^9$ & $2.8129\times 10^7$ & $2.9454\times 10^3$
		Look-ahead + Small Strategic + Perfect & $52.86$ & $35.60$ & $2.3031\times 10^9$ & $2.8127\times 10^7$ & $3.1346\times 10^3$
		Look-ahead + Medium Integrated + Perfect & $52.94$ & $27.80$ & $2.3028\times 10^9$ & $2.7410\times 10^7$ & $1.9601\times 10^5$
		Look-ahead + Medium Strategic + Perfect & $51.84$ & $31.52$ & $2.3028\times 10^9$ & $2.7760\times 10^7$ & $2.3140\times 10^5$
		Look-ahead + Large Integrated + Perfect & $49.26$ & $11.12$ & $2.3028\times 10^9$ & $2.5009\times 10^7$ & $0.2301\times 10^5$
		Look-ahead + Large Strategic + Perfect & $51.59$ & $25.94$ & $2.3029\times 10^9$ & $2.6987\times 10^7$ & $2.1819\times 10^5$"""
    case = 'Perfect'
    bar_experiments(table, case)

    table ="""Look-ahead + No Storage + Renewable & $25.26$ & $28.58$ & $2.3532\times 10^9$ & $1.3759\times 10^7$ & $0.0000000000000$
		Look-ahead + Small Integrated + Renewable & $25.26$ & $28.58$ & $2.3532\times 10^9$ & $1.3759\times 10^7$ & $2.5365\times 10^3$
		Look-ahead + Small Strategic + Renewable & $25.26$ & $28.58$ & $2.3532\times 10^9$ & $1.3759\times 10^7$ & $2.6365\times 10^3$
		Look-ahead + Medium Integrated + Renewable & $20.37$ & $18.96$ & $2.3531\times 10^9$ & $1.0867\times 10^7$ & $0.70037\times 10^5$
		Look-ahead + Medium Strategic + Renewable & $21.89$ & $21.88$ & $2.3531\times 10^9$ & $1.1806\times 10^7$ & $1.3630\times 10^5$
		Look-ahead + Large Integrated + Renewable & $17.03$ & $14.55$ & $2.3528\times 10^9$ & $0.89354\times 10^7$ & $2.9063\times 10^5$
		Look-ahead + Large Strategic + Renewable & $18.01$ & $18.75$ & $2.3528\times 10^9$ & $0.97022\times 10^7$ & $3.7964\times 10^5$"""
    case = 'Renewable'
    bar_experiments(table, case)


def plot_obj():
    fig, ax = plt.subplots(figsize=(4, 2))
    formatter = ticker.ScalarFormatter(useMathText=True)
    formatter.set_powerlimits((-3, 3))  # Adjust the power limits as needed
    plt.gca().yaxis.set_major_formatter(formatter)

    categories = ['Look-ahead', 'Single-period']
    data1 = [2.3031 * pow(10, 9), 0]  # Data for the first bar
    data2 = [0, 3.8677 * pow(10, 9)]  # Data for the second bar
    bar_width = 0.4
    # Plotting the first bar with blue color
    plt.bar(categories, data1, color=default.GREEN, width=bar_width, alpha=0.65)

    # Plotting the second bar with green color
    plt.bar(categories, data2, color=default.BROWN, width=bar_width, alpha=0.65)

    # plt.xlabel('Categories')
    plt.ylabel('Total Objecitve (\$)')
    # plt.title('Comparison of total objective.')
    # plt.legend()
    # plt.show()
    path_to_fig = default.EXPERIMENT_DIR / 'bilevel' / f'ObjectiveNoStorage.jpg'
    plt.savefig(path_to_fig)
    plt.close()

def plot_week():
    initial = datetime.datetime(2021, 7, 18, 4, 30)
    energies = [0, 30, 3000, 15000]
    u1 = 'DER None Integrated Hour No-losses'
    u2 = 'DER None Inelastic Bilevel Hour No-losses'
    integrated = generate_batteries_by_energies(energies, u1)
    strategic = generate_batteries_by_energies(energies, u2)
    strategic_batt = strategic[1]
    small_storage_list = [[integrated[0], integrated[1], strategic[1]]]
    # small_storage_list = [[integrated[0], integrated[1]]]
    for batteries in small_storage_list:
        fig, ax1 = plt.subplots(figsize=(6, 2))
        # ax1.set_ylim([-5, 130])
        ax1.set_xlabel('Time (Hour)')
        ax1.set_ylabel('Price ($/MWh)')

        for battery, color in zip(batteries, default.COLOR_LIST):
            prices = []
            for i in range(7):
                start = initial + i * default.ONE_DAY
                times, _, _, _, price, _ = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
                prices += price
            label = get_label(battery.usage, battery.size)
            ax1.plot(range(1, len(prices) + 1), prices, label=label, color=get_color(label))

        ax1.legend(frameon=True)
        plt.show()
        # path_to_fig = path_to_dir / (f'Price_{battery.size}.jpg' if filename is None else filename)
        # plt.savefig(path_to_fig)
        # plt.close(fig)
    for batteries in small_storage_list:
        fig, ax1 = plt.subplots(figsize=(6, 2))
        ax1.set_ylim([0, 100])

        for battery, color in zip(batteries, default.COLOR_LIST):
            if battery.size != 0:
                socss = []
                for i in range(7):
                    start = initial + i * default.ONE_DAY
                    times, socs, _, _, _, _ = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
                    socss += socs
                label = get_label(battery.usage, battery.size)
                ax1.plot(range(1, len(socss) + 1), socss, label=label, color=get_color(label))

        # times, socs1, _, _, _, _ = read_battery_optimisation(strategic_batt.bat_dir / f'{default.get_case_datetime(initial)}.csv')
        # times, socs2, _, _, _, _ = read_battery_optimisation(strategic_batt.bat_dir / f'{default.get_case_datetime(initial + default.ONE_DAY)}.csv')
        # label = get_label(strategic_batt.usage, strategic_batt.size)
        # ax1.plot(range(1, len(socss) + 1), (socs1 + socs2 + socs1 + socs2 + socs1 + socs2 + socs1), label=label, color=get_color(label))
        #
        ax1.set_xlabel('Time (Hour)')
        ax1.set_ylabel('SOC (%)')

        ax1.legend(frameon=True)
        plt.show()
        # path_to_fig = path_to_dir / (f'SOC_{battery.size}.jpg' if filename is None else filename)
        # plt.savefig(path_to_fig)
        # plt.close(fig)


def plot_pie_chart():
    # Example data
    # labels = ['Coal 64.67%', 'Biomass 0.09%', 'Gas 6.57%', 'Grid-scale Solar 3.85%', 'Distributed PV 7.09%', 'Energy Storage 0.05%', 'Wind 10.45%', 'Hydro 7.21%']
    labels = ['Coal 131.27TWh', 'Biomass 0.18TWh', 'Gas 13.33TWh', 'Grid-scale Solar 7.81TWh', 'Distributed PV 14.39TWh', 'Energy Storage 0.11TWh', 'Wind 21.2TWh', 'Hydro 14.64TWh']
    y = np.array([131.27, 0.18, 13.33, 7.81, 14.39, 0.11, 21.2, 14.64])

    # def autopct_format(values):
    #     def my_format(pct):
    #         total = sum(values)
    #         val = int(round(pct * total / 100.0))
    #         return '{v:.1f} TWh'.format(v=val)
    #     return my_format

    plt.pie(y, labels=labels)
    # plt.show()
    path_to_fig = default.EXPERIMENT_DIR / 'fuel.jpg'
    plt.savefig(path_to_fig)
    plt.close()


if __name__ == '__main__':
    # experiments()
    # check()
    # plot_cost_reflective_bands()
    # plot_week()
    # plot_obj()
    # plot_pie_chart()
    isgt2022_experiments()