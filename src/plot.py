import default
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
import matplotlib.pyplot as plt
plt.style.use(['science', 'ieee', 'bright', 'no-latex'])
import matplotlib.dates as mdates
from helpers import Battery


def plot_forecasts(custom_flag, time, item, label, times, energy_prices, aemo_energy_prices, battery, end=None, k=0, forecast_dir=None, process_type='predispatch', title=None):
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
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax2.set_ylabel('Price ($/MWh)')
    # ax2.plot(energy_times, [price_dict[t] for t in energy_times], label='Actual price')
    # ax2.plot(predispatch_times, predispatch_energy_prices, label='30min Predispatch')
    # ax2.plot(p5min_times, p5min_energy_prices, label='5min predispatch')
    lns2 = ax2.plot(times, energy_prices, label=f'Price', color='red')
    lns1 = ax1.plot(times, item, label='SOC', color='blue')

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


def plot_price_comparison(times, p1, p2):
    fig, ax1 = plt.subplots()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))
    ax1.set_xlabel('Datetime')
    # col = 'tab:green'
    ax1.set_ylabel('Price')
    ax1.tick_params(axis='y')
    ax1.plot(times, p1, label='small')
    ax1.plot(times, p2, label='large')
    plt.legend()
    plt.show()
    # plt.savefig(battery.bat_dir / f'{ylabel} {battery.Emax}MWh {battery.generator.max_capacity}MW {default.get_result_datetime(current)}')
    # plt.close(fig)


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


def plot_revenues(items, revenues, xlabel, ylabel, region_id, method, original=None):
    fig, ax1 = plt.subplots()
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel(ylabel)
    ax1.plot(items, revenues, 'o-', color='blue', label=None if original is None else 'Influenced')
    if original is not None:
        ax1.plot(items, original, color='red', label='Original')
        plt.legend()
    # plt.title(f'Revenue {region_id} Method {method}')
    plt.show()
    # plt.savefig(default.OUT_DIR / 'revenue' / f'{ylabel} - {xlabel} {region_id} Method {method}')


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


def plot_optimisation_with_bids(b, method, k):
    import read
    times, socs, prices, original_prices = read.read_optimisation_with_bids(b, method, k)
    fig, ax1 = plt.subplots()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax1.set_xlabel('Datetime')
    # col = 'tab:green'
    ax1.set_ylabel('SOC (%)')
    lns1 = ax1.plot(times, socs, label='SOC', color='blue')
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
    # lns3 = ax2.plot(times, original_prices, label=f'Dispatch Price', color='green')

    # plt.legend()
    lns = lns1 + lns2
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, loc=0)
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


if __name__ == '__main__':
    region_id, method = 'NSW1', 2
    # import read
    # capacity_label, capacities, power_label, powers, revenue_label, revenues = read.read_revenues(region_id, method)
    # plot_revenues(capacities, revenues, capacity_label, revenue_label, region_id, method)
    # plot_revenues(powers, revenues, power_label, revenue_label, region_id, method)
    import helpers
    # start = datetime.datetime(2020, 9, 1, 12, 35)
    # end = datetime.datetime(2020, 9, 1, 18, 0)
    # for e, p in zip([240, 210], [160, 140]):
    # for a in range(1, 27):
    #     if a > 14 and a % 2 == 1:
    #         continue
    # for a in range(32, 50, 2):
    #     e = 15 * a
    #     p = 10 * a
    #     b = helpers.Battery(e, p, region_id, method)
    #     # plot_optimise_with_bids_old(start, end, b, 0)
    #     plot_optimisation_with_bids(b, method, 1)
    #     plot_prices_with_bids(b, method, 1)
    b = helpers.Battery(1500, 1000, region_id, method)
    plot_prices_with_bids(b, method, 1)