import datetime
import default
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
import matplotlib.pyplot as plt
plt.style.use(['science', 'ieee', 'no-latex'])
import matplotlib.dates as mdates
import matplotlib.ticker
from helpers import Battery
import numpy as np


def plot_soc(times, prices, socs, path_to_fig, price_flag=True, soc_flag=True):
    if len(times) <= 288:
        fig, ax1 = plt.subplots()
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax1.xaxis.set_major_locator(mdates.HourLocator(interval=6))
        ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
        ax1.set_xlabel('Interval')
    else:
        fig, ax1 = plt.subplots(figsize=(8, 4))
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d'))
        ax1.xaxis.set_major_locator(mdates.DayLocator())
        ax1.xaxis.set_minor_locator(mdates.DayLocator())
        ax1.set_xlabel('Date')

    lns = []
    if soc_flag:
        ax1.set_ylabel('SOC (%)')
        ax1.set_ylim([0, 100])
        if len(socs) == 2:
            lns1 = ax1.plot(([] if len(times) == len(socs[1]) else [times[0] - default.FIVE_MIN]) + times, socs[1], label='Time-stepped SOC', color=default.RED, linewidth=0.3)
            lns4 = ax1.plot(([] if len(times) == len(socs[0]) else [times[0] - default.FIVE_MIN]) + times, socs[0], '-', label='Non-time-stepped SOC',color=default.BROWN, alpha=0.4, linewidth=2)
            lns = lns1 + lns4
        else:
            lns1 = ax1.plot(([] if len(times) == len(socs) else [times[0] - default.FIVE_MIN]) + times, socs, label='SOC', color=default.BROWN)
            lns = lns1
    if price_flag:
        ax2 = ax1.twinx()
        if len(times) <= 288:
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax2.xaxis.set_major_locator(mdates.HourLocator(interval=6))
            ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
            ax2.set_xlabel('Interval')
        else:
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d'))
            ax2.xaxis.set_major_locator(mdates.DayLocator())
            ax2.xaxis.set_minor_locator(mdates.DayLocator())
            ax2.set_xlabel('Date')

        ax2.set_ylabel('Price ($/MWh)')
        # ax2.set_yscale('symlog')
        if len(prices) == 2:
            # label1 = 'Historical Record'
            label1 = 'Non-time stepped Price'
            lns3 = ax2.plot(times, prices[1], label=label1, color=default.PURPLE, alpha=0.4, linewidth=2)
            # label2 = 'Cost-reflective' if 'reflective' in str(path_to_fig) else 'Price-taker'
            label2 = 'Time-stepped Price'
            lns2 = ax2.plot(times, prices[0], '-', label=label2, color=default.BLUE, linewidth=0.3)
            # lns2 = ax2.plot([t for t, p in zip(times, prices[0]) if p < 1000], [p for p in prices[0] if p < 1000], '-', label=usage_type, color=default.BLUE, linewidth=0.5)
            lns += lns2 + lns3
        else:
            lns2 = ax2.plot(times, prices, label='Price', color=default.PURPLE)
            lns += lns2
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, loc=0)
    plt.show()
    # plt.savefig(path_to_fig)
    plt.close(fig)


def plot_power(times, prices, powers, bid_type, path_to_fig):
    fig, ax1 = plt.subplots()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))

    ax1.set_xlabel('Interval')
    ax1.set_ylabel('Power (MW)')
    if len(powers) == 2:
        lns1 = ax1.plot(times, powers[0], label='Gen', color=default.BLUE)
        lns4 = ax1.plot(times, powers[1], label='Load', color=default.CYAN)
        lns = lns1 + lns4
    else:
        lns1 = ax1.plot(times, powers, label=bid_type, color=default.BLUE)
        lns = lns1

    ax2 = ax1.twinx()
    # ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    # ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax2.set_ylabel('Price ($/MWh)')
    if len(prices) == 2:
        lns2 = ax2.plot(times, prices[0], label='Model', color=default.RED)
        lns3 = ax2.plot(times, prices[1], label='Record', color=default.PURPLE)
        lns += lns2 + lns3
    else:
        lns2 = ax2.plot(times, prices, label='Price', color='red')
        lns += lns2
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs)
    plt.savefig(path_to_fig)
    plt.close(fig)


def plot_forecasts(custom_flag, time, item, label, times, energy_prices, aemo_energy_prices, battery, end=None, k=0, forecast_dir=None, process_type='predispatch', title=None, band=None, soc_initial=50):
    fig, ax1 = plt.subplots()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax1.set_xlabel('Interval')
    # col = 'tab:green'
    ax1.set_ylabel(label)
    # ax1.tick_params(axis='y', labelcolor='blue')
    # if end is not None:
    #     plt.axvline(end, 0, 100, c="r")
    if label == 'SOC (%)':
        ax1.set_ylim([0, 100])
    ax2 = ax1.twinx()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))

    ax2.set_ylabel('Price ($/MWh)')
    # ax2.plot(energy_times, [price_dict[t] for t in energy_times], label='Actual price')
    # ax2.plot(predispatch_times, predispatch_energy_prices, label='30min Predispatch')
    # ax2.plot(p5min_times, p5min_energy_prices, label='5min predispatch')
    lns2 = ax2.plot(times, energy_prices, label=f'Price', color='red')
    lns1 = ax1.plot([times[0] - default.FIVE_MIN] + times, [soc_initial] + item, label='SOC', color='blue')

    # if custom_flag and aemo_energy_prices is not None:
    #     ax2.plot(times, aemo_energy_prices, label=f'AEMO {process_type} Price', color='tab:green')

    lns = lns1 + lns2
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, loc=0)
    # if title:
    #     plt.title(battery.name)
    if forecast_dir is None:
        forecast_dir = battery.bat_dir / ('forecast' if k == 0 else f'forecast_{k}')
        forecast_dir.mkdir(parents=True, exist_ok=True)
        band = '' if band is None else f'_{band}'
        plt.savefig(forecast_dir / f'{title} {default.get_case_datetime(time)}{band}.jpg')
    else:
        plt.savefig(forecast_dir / f'{title} {battery.name}.jpg')
    plt.close(fig)


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


def plot_price_comparison(times, p1, p2, p1label='small', p2label='large', path_to_fig=None):
    fig, ax1 = plt.subplots()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))
    ax1.set_xlabel('Datetime')
    # col = 'tab:green'
    ax1.set_ylabel('Price')
    ax1.tick_params(axis='y')
    ax1.plot(times, p1, label=p1label, color=default.PURPLE, alpha=0.4, linewidth=2)
    ax1.plot(times, p2, '-', label=p2label, color=default.BLUE, linewidth=0.3)
    plt.legend()
    plt.savefig(path_to_fig)
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
    # for e, p in zip([65, 429, 1000], [50, 200, 500]):
    for e, p in zip([12, 65, 129, 429, 1000, 2800, 4000], [30, 50, 100, 200, 500, 700, 1000]):
        battery = Battery(e, p)
        times, items = extract_func(current, battery, k)
        ax1.plot(times, items, label=f'{battery.Emax}MWh {battery.generator.max_capacity}MW')

    plt.legend()
    plt.savefig(default.OUT_DIR / f'{ylabel} k = {k} {default.get_result_datetime(current)}')
    plt.close(fig)


def plot_revenues(items, revenues, xlabel, ylabel, usage, title=None, com_items=None, com_revenues=None, com_usage=None):
    # revenues = [r for _, r in sorted(zip(items, revenues))]
    # items = sorted(items)
    fig, ax1 = plt.subplots()
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel(ylabel)

    # ax1.set_xscale('log')
    # ax1.set_yscale('symlog')
    # # set y ticks
    # y_major = matplotlib.ticker.LogLocator(base=10.0)
    # ax1.yaxis.set_major_locator(y_major)
    # y_minor = matplotlib.ticker.LogLocator(base=10.0, subs=np.arange(-10.0, 10.0, 2) * 0.1)
    # ax1.yaxis.set_minor_locator(y_minor)
    # ax1.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())

    ax1.plot(items, revenues, 'o-', color=default.BROWN, label=usage if com_items else None)
    if com_items:
        # com_revenues = [r for _, r in sorted(zip(com_items, com_revenues))]
        # com_items = sorted(com_items)
        if 'Revenue' in title:
            ax1.plot([i for i, r in zip(com_items, com_revenues) if r > -500], [r for i, r in zip(com_items, com_revenues) if r > -500], 'o-', color=default.PURPLE, label=com_usage)
        elif 'Standard' in title:
            ax1.plot([i for i, r in zip(com_items, com_revenues) if r < 100], [r for r in com_revenues if r < 100], 'o-', color=default.PURPLE, label=com_usage)
        else:
            ax1.plot([i for i, r in zip(com_items, com_revenues) if r < 70], [r for r in com_revenues if r < 70], 'o-', color=default.PURPLE, label=com_usage)


        plt.legend()
        plt.savefig(default.OUT_DIR / 'revenue' / f'{title}.jpg')
    else:
        plt.savefig(default.OUT_DIR / 'revenue' / f'{title} {usage}.jpg')
    # plt.show()
    plt.close(fig)


def plot_optimise_with_bids_old(start, end, battery, k):
    import read
    times, prices, socs, original_prices = read.read_first_forecast(start, end, battery.load.region_id, battery.bat_dir, k)
    fig, ax1 = plt.subplots()
    # ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    # ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax1.set_xlabel('Datetime')
    # col = 'tab:green'
    ax1.set_ylabel('SOC (%)', color='tab:orange')
    ax1.plot(times, socs, label='SOC', color='tab:orange')
    ax1.tick_params(axis='y', labelcolor='tab:orange')
    ax1.set_ylim([0, 100])

    ax2 = ax1.twinx()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    # ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax2.set_ylabel('Price ($/MWh)', color='black')
    # ax2.plot(energy_times, [price_dict[t] for t in energy_times], label='Actual price')
    # ax2.plot(predispatch_times, predispatch_energy_prices, label='30min Predispatch')
    # ax2.plot(p5min_times, p5min_energy_prices, label='5min predispatch')
    ax2.plot(times, prices, label=f'Price with bids', color='tab:blue')
    ax2.plot(times, original_prices, label=f'Original Dispatch Price', color='tab:green')

    plt.legend()
    plt.savefig(battery.bat_dir / f'Optimisation with bids from {default.get_result_datetime(start)} to {default.get_result_datetime(end)}')
    plt.close(fig)


def plot_optimisation_with_bids(b, method, k, der_flag=False, e=None, t=None, bat_dir=None):
    import read
    if der_flag:
        times, socs, prices, socs_record = read.read_der(e, t, bat_dir)
        # predispatch_times, predispatch_prices, aemo_predispatch_prices, predispatch_fcas_prices, aemo_predispatch_fcas_prices = read.read_prices(predispatch_time, 'predispatch', True, region_id)
    else:
        times, socs, prices, original_prices = read.read_optimisation_with_bids(b, method, k)
    fig, ax1 = plt.subplots()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax1.set_xlabel('Datetime')
    # col = 'tab:green'
    ax1.set_ylabel('SOC (%)')
    lns1 = ax1.plot(times, socs, label='SOC', color='blue')
    # lns1 = ax1.plot(times, socs_record, label='SOC', color='blue')
    ax1.tick_params(axis='y')
    ax1.set_ylim([0, 100])

    ax2 = ax1.twinx()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax2.set_ylabel('Price ($/MWh)')
    # ax2.plot(energy_times, [price_dict[t] for t in energy_times], label='Actual price')
    # ax2.plot(predispatch_times, predispatch_energy_prices, label='30min Predispatch')
    # ax2.plot(p5min_times, p5min_energy_prices, label='5min predispatch')
    lns2 = ax2.plot(times, prices, label=f'Price', color='red')
    # lns3 = ax2.plot(times, original_prices, label=f'Original', color='green')

    # plt.legend()
    lns = lns1 + lns2
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, loc=0)
    if der_flag:
        plt.savefig(bat_dir / f'DER_{e}MWh_{default.get_case_datetime(t)}.jpg')
    else:
        plt.savefig(default.OUT_DIR / f'battery optimisation with bids {b.generator.region_id} method {method}' / f'optimisation with bids {b.plot_name}')
    plt.close(fig)


def plot_prices_with_bids(b, method, k):
    import read
    times, socs, prices, original_prices = read.read_optimisation_with_bids(b, method, k)
    fig, ax2 = plt.subplots()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax2.set_ylabel('Price ($/MWh)')
    ax2.set_xlabel('Datetime')
    # ax2.plot(energy_times, [price_dict[t] for t in energy_times], label='Actual price')
    # ax2.plot(predispatch_times, predispatch_energy_prices, label='30min Predispatch')
    # ax2.plot(p5min_times, p5min_energy_prices, label='5min predispatch')
    lns2 = ax2.plot(times, prices, label=f'with batt.', color='blue')
    lns3 = ax2.plot(times, original_prices, label=f'no batt.', color='red')

    # plt.legend()
    lns = lns3 + lns2
    labs = [l.get_label() for l in lns]
    ax2.legend(lns, labs, loc=1)
    plt.savefig(default.OUT_DIR / f'battery optimisation with bids {b.generator.region_id} method {method}' / f'prices with bids {b.name}')
    plt.close(fig)


def plot_der_prices(e, t, region_id, bat_dir):
    import read
    times, socs, prices, _ = read.read_der(e, t, bat_dir)
    p5min_times, p5min_prices, aemo_p5min_prices, p5min_fcas_prices, aemo_p5min_fcas_prices = read.read_prices(t, 'p5min', True, region_id)
    predispatch_time = default.get_predispatch_time(t)
    predispatch_times, predispatch_prices, aemo_predispatch_prices, predispatch_fcas_prices, aemo_predispatch_fcas_prices = read.read_prices(predispatch_time, 'predispatch', True, region_id)
    path_to_fig = bat_dir / f'Prices_{e}MWh_{default.get_case_datetime(t)}.jpg'
    plot_price_comparison(times, p5min_prices + predispatch_prices[2:], prices, p1label='NEMDE', p2label='Our Model', path_to_fig=path_to_fig)


if __name__ == '__main__':
    from helpers import Battery
    from read import read_battery_optimisation
    battery = Battery(30, 20, usage='DER Price-taker Dual')
    start = datetime.datetime(2020, 9, 1, 4, 5)
    times, socs, prices = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
    battery = Battery(30, 20, usage='Price-taker Dual')
    _, socs2, prices2 = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
    path_to_fig = None
    plot_soc(times, [prices, prices2[:len(prices)]], [socs, socs2[:len(socs)]], path_to_fig, price_flag=True, soc_flag=True)