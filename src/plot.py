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
            label1 = 'Predispatch Price'
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
    e = 30
    u1 = 'DER Price-taker Dual'
    u1 = 'DER Price-taker Combo'
    battery = Battery(e, int(e / 3 * 2), usage=u1)
    start = datetime.datetime(2020, 9, 1, 4, 5)
    # times, socs, prices = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
    # battery = Battery(e, int(e / 3 * 2), usage='Price-taker500 Dual')
    # _, socs2, prices2 = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
    # prices2 = [p if p <= 600 else 0 for p in prices2]
    path_to_fig = None
    Es = [13.03921568627451, 11.07843137254902, 9.117647058823529, 7.156862745098039, 5.196078431372548, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5]
    socs = [e / 30 for e in Es]
    prices = [39.007811706513166, 39.79013595730066, 39.00781170837581, 38.402579233050346, 36.01768417470157, 49.2560287322849, 39.007811706513166, 35.47363572753966, 37.294043093919754, 35.73970513418317, 34.39576178044081, 39.885714288800955, 37.294043090194464, 39.852590054273605, 39.885714285075665, 37.29404309205711, 35.63964695110917, 44.99083318002522, 40.42661249265075, 46.53198375366628, 44.90708490461111, 40.42661249451339, 46.75562356039882, 47.98390636779368, 41.39811357110739, 40.42661249637604, 45.36857046186924, 44.75680839270353, 55.84665596857667, 59.37156328186393, 44.46617702767253, 44.56292777508497, 45.85099860280752, 50.411315612494946, 46.65971092134714, 49.08073720894754, 42.54533553868532, 41.64971859008074, 40.467717334628105, 40.467717334628105, 40.42661249265075, 40.42661249637604, 42.02882334217429, 40.42661249637604, 40.467717334628105, 40.42661249265075, 39.85725395381451, 39.00764827989042, 40.06616226583719, 39.750047117471695, 38.54707019403577, 38.14174726605415, 35.73970513418317, 35.73970513418317, 39.1230070181191, 38.76848716288805, 35.73970513418317, 35.70340274274349, 407.99958580732346, 35.70340274274349, 38.16699709929526, 35.70340274274349, 35.70340274274349, 35.70340274274349, 33.65194805338979, 33.28945729508996, 66.62410941720009, 42.8937916867435, 35.739705136045814, 35.739705136045814, 35.70340274274349, 35.70340274274349, 37.294043093919754, 35.70340274274349, 35.73970513418317, 35.63964695110917, 37.29404309205711, 79.5195779222995, 38.69659109227359, 37.294043093919754, 38.285216610878706, 37.294043093919754, 37.29404309205711, 71.14808915182948, 40.42661249451339, 37.29404309205711, 35.70340274274349, 37.2940430957824, 35.73970513418317, 35.63964695110917, 35.73970513418317, 34.4083233717829, 34.141474552452564, 33.894520150497556, 32.971492340788245, 37.294043097645044, 32.971492340788245, 29.273145793005824, 33.398082787171006, 33.052389055490494, 31.29512334242463, 31.294118486344814, -536.9723828136921, 31.752701565623283, 37.61979206651449, 31.53742753714323, 30.839605890214443, 29.27363103069365, 80.30067289061844, -227.87172013148665, 23.70840190909803, 134.20984669588506, 14.99761207588017, 11.06342645548284, -774.5800147634, -101.91615318134427, 21.996856350451708, 10.963791016489267, 10.728878267109394, -931.0830718912184, 10.387600302696228, -340.9324655532837, -225.01165010035038, 956.8530925996602, 10.638085450977087, 23.006324533373117, 22.90867569297552, 28.524101309478283, 28.092551305890083, 28.227474071085453, 28.720930751413107, 30.23590322956443, 26.206196039915085, 35.73970513418317, 26.206196036189795, 26.206196039915085, 30.394121445715427, 30.838133834302425, 32.97149234265089, 35.70340274274349, 32.854417253285646, 37.294043090194464, 35.73970513418317, 37.294043093919754, 35.70340274274349, 32.97149234265089, 32.496115278452635, 37.294043090194464, 38.795692920684814, 52.60243583843112, 32.97149234265089, 36.20026248879731, 34.853720005601645, 37.294043093919754, 50.5488892570138, 39.48216661810875, 35.70340274274349, 39.852590054273605, 36.44011766463518, 46.98528911918402, 39.885714285075665, 46.42853349633515, 38.750815000385046, 57.02071237564087, 45.53547126054764, 62.74064460396767, 62.740644600242376, 323.9238589666784, 121.4813813380897, 65.24761627241969, 100.18511851131916, 144.56201787292957, 77.78779301792383, 204.42230490595102, 91.68404631316662, -216.97862977907062, 62.74064460396767, 62.740644600242376, 55.167829502373934, 49.66414833441377, 62.74064460396767, 56.043465334922075, 48.992704562842846, 49.20361164584756, 49.00544520094991, 47.67152388393879, 62.74064460210502, 56.1053543202579, 49.203611647710204, 48.75091131776571, 48.45421395264566, 44.22357074171305, 62.74064460210502, 55.75418755412102, 49.4413947314024, 47.9311128500849, 61.634481554850936, 50.22435435466468, 51.40651188790798, 58.99910510703921, 51.031678633764386, 46.33991722390056, 45.0363588873297, 40.821540009230375, 61.25897760875523, 59.32839606329799, 45.42258773557842, 45.76551667228341, 40.42661249265075, 39.85259005613625, 40.14339664578438, 39.885714285075665, 39.52962347492576, 39.67421863786876, 37.31602296233177, 37.29404309205711, 46.62075214087963, 40.467717334628105, 40.42661249265075, 40.42661249637604, 39.88571428693831, 37.93090896680951, 40.42661249265075, 39.885714285075665, 37.403898349031806, 37.29404309205711, 35.73970513418317, 35.70340274274349, 38.60516723617911, 37.29404309205711, 39.904794327914715, 41.9760358966887, 40.096099738031626, 40.42661249451339, 40.467717334628105, 40.467717334628105, 40.46771733649075, 40.42661249265075, 40.42661249265075, 40.42661249265075, 40.42661249637604, 40.42661249451339, 40.42661249451339, 40.42661249637604, 40.42661249451339, 40.467717342078686, 43.600752690806985, 40.467717334628105, 40.42661249637604, 40.42661249451339, 40.42661249451339, 40.42661249451339, 46.01721563376486, 40.467717334628105, 40.42661249637604, 40.42661249451339, 40.42661249451339, 40.42661249451339, 50.38961038924754, 44.865306003019214, 40.46771733649075, 40.42661249265075, 40.42661249265075, -347.6236020885408, 39.007811706513166, 50.38961038924754, 40.42661249451339, 40.42661249451339, 40.42661249451339, -98.98229407332838, 39.34289814159274, 27.180424546822906, 38.78175677917898, -22.339292399585247, 38.67492834664881, -647.0562835317105, -36.94959638081491, 37.58226386271417, 37.5911819729954, -316.80844549275935, -204.24359197169542, -507.39385011047125, 39.87621028162539, 37.38961745239794, 37.02938769198954, 245.1008870434016, 36.31037851050496, 37.396449849009514]
    times = [start + i * default.FIVE_MIN for i in range(288)]
    # plot_soc(times, [prices, prices2[:len(prices)]], [socs, socs2[:len(socs)]], path_to_fig, price_flag=True, soc_flag=True)
    plot_soc(times, prices, socs, path_to_fig, price_flag=True, soc_flag=True)