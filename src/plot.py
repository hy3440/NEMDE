import default
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from helpers import Battery


def plot_forecasts(custom_flag, time, item, label, times, energy_prices, aemo_energy_prices, battery, end=None, k=0, forecast_dir=None, process_type='predispatch', title=None):
    fig, ax1 = plt.subplots()
    # ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    # ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax1.set_xlabel('Datetime')
    # col = 'tab:green'
    ax1.set_ylabel(label, color='tab:orange')
    ax1.plot(times, item, label=label, color='tab:orange')
    ax1.tick_params(axis='y', labelcolor='tab:orange')
    if end is not None:
        plt.axvline(end, 0, 100, c="r")
    if label == 'SOC (%)':
        ax1.set_ylim([0, 100])

    ax2 = ax1.twinx()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax2.set_ylabel('Price ($/MWh)', color='black')
    # ax2.plot(energy_times, [price_dict[t] for t in energy_times], label='Actual price')
    # ax2.plot(predispatch_times, predispatch_energy_prices, label='30min Predispatch')
    # ax2.plot(p5min_times, p5min_energy_prices, label='5min predispatch')
    ax2.plot(times, energy_prices, label=f'Our {process_type} Price', color='tab:blue')
    if custom_flag and aemo_energy_prices is not None:
        ax2.plot(times, aemo_energy_prices, label=f'AEMO {process_type} Price', color='tab:green')

    plt.legend()
    if title:
        plt.title(battery.name)
    if forecast_dir is None:
        forecast_dir = battery.bat_dir / ('forecast' if k == 0 else f'forecast_{k}')
        forecast_dir.mkdir(parents=True, exist_ok=True)
        plt.savefig(forecast_dir / f'{title} {default.get_result_datetime(time)}')
    else:
        plt.savefig(forecast_dir / f'{title} {battery.name}')
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


def plot_revenues(items, revenues, xlabel, ylabel, region_id, method):
    fig, ax1 = plt.subplots()
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel(ylabel)
    ax1.plot(items, revenues)
    plt.title(f'revenue {region_id} method {method}')
    plt.savefig(default.OUT_DIR / f'revenue {region_id} method {method}')