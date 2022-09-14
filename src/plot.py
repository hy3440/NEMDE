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


def plot_soc(times, prices, socs, path_to_fig, price_flag=True, soc_flag=True, labels=None):
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
            lns1 = ax1.plot([times[0] - default.ONE_HOUR] + list(times), [50] + list(socs), label='SOC', color=default.BROWN)
            # lns1 = ax1.plot(([] if len(times) == len(socs) else [times[0] - default.FIVE_MIN]) + times, socs, label='SOC', color=default.BROWN)
            lns = lns1
    if price_flag:
        ax2 = ax1.twinx() if soc_flag else ax1
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
        # ax2.set_ylim([0, 500])
        if len(prices) == 2:
            # label1 = 'Historical Record'
            if labels is not None:
                label1, label0 = labels[1], labels[0]
            lns3 = ax2.plot(times, prices[1], label=label1, color=default.PURPLE, alpha=0.4, linewidth=2)
            # label2 = 'Cost-reflective' if 'reflective' in str(path_to_fig) else 'Price-taker'
            lns2 = ax2.plot(times, prices[0], '-', label=label0, color=default.BLUE, linewidth=0.3)
            # lns2 = ax2.plot([t for t, p in zip(times, prices[0]) if p < 1000], [p for p in prices[0] if p < 1000], '-', label=usage_type, color=default.BLUE, linewidth=0.5)
            lns += lns2 + lns3
        else:
            lns2 = ax2.plot(times, prices, label='Price', color=default.PURPLE)
            lns += lns2
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, loc=0)
    if path_to_fig is None:
        plt.show()
    else:
        plt.savefig(path_to_fig)
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
    from read import read_battery_optimisation, read_der, read_dispatch_prices, read_predispatch_prices, read_bilevel_der
    e = 30
    # u1 = 'DER Price-taker Dual'
    # u1 = 'Cost-reflective Hour'
    # u1 = 'Cost-reflective 5MIN'
    # u1 = 'DER None Integration Hour'
    u1 = 'DER None Bilevel Test Hour new'
    # u1 = 'DER None Simplified Integration Test Hour'
    battery = Battery(e, int(e / 3 * 2), usage=u1)
    start = datetime.datetime(2021, 7, 18, 4, 30)
    times, socs, _, _, prices = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')  # Rolling horizon
    # times, socs, prices, socs_record = read_der(e, start, battery.bat_dir)  # First horizon
    # times, socs, prices, _ = read_bilevel_der(e, start, battery.bat_dir)  # First horizon
    # prices2 = [41.015176398565764, 41.84406830917762, 57.162162176447886, 58.8892273493908, 48.991353391439034, 44.26845366440248, 9.093515457271218, 2e-08, 2e-08, 2e-08, 1e-08, 36.988152151319895, 39.693649841836944, 61.37247246965451, 97.92457169426443, 136.47121592818638, 154.89076395967453, 111.85304236209463, 77.64326069410815, 65.91038424773429, 84.95635572509536, 58.88922733672413, 58.88922733672413, 58.83546357811494]
    # prices2 = [41.37998005767471, 41.37126349892904, 34.91274494524382, 44.228038127325156, 42.30977757084921, 41.015176376478664, 45.29203907711494, 41.866778358692834, 40.50040652418428, 44.228038127325156, 45.30145531322, 44.228038127325156, 45.301455289690594, 41.96352342350462, 67.00215418740558, 64.37656684457761, 45.301455289690594, 45.30145531322, 47.621698247553184, 44.228038127325156, 45.30145531322, 44.228038127325156, 44.228038127325156, 65.87358410220881, 52.413975240228424, 64.98468316576493, 66.29641455432836, 63.280771902613694, 57.16216214787645, 57.162162176447886, 58.83546357518454, 63.95714338473344, 63.96048640936987, 57.162162176447886, 64.23804088641108, 57.16216214787645, 57.162162176447886, 52.60036636277192, 62.025019115363854, 58.8892273493908, 58.8892273493908, 58.8892273493908, 61.44741002550427, 60.74233088624072, 60.72112880929878, 58.88922733748604, 58.83546357811494, 58.835463587638756, 57.162162176447886, 46.8168775057921, 58.83546357573399, 46.287071375449656, 47.99005917624562, 52.6986718554629, 57.150280606942424, 57.150280606942424, 52.842729972326595, 47.992122705973806, 45.3014553114553, 47.44593946008203, 58.83546358287685, 58.00855529136618, 50.078300657973784, 44.26845366440248, 44.228038127325156, 46.574969372763924, 44.26845366440248, 44.228038127325156, 44.22803815589659, 36.99584197917533, 39.693649834694085, 39.729921826616916, 36.4589759507773, 36.22438629953628, 33.2922064469196, 42.69444444748328, 33.2922064669196, 24.8490443677544, 36.25748806985481, 36.22438627096484, 33.2922064469196, 33.2922064669196, 33.2922064669196, 5e-08, 1e-08, 2e-08, 1e-08, 1e-08, 1e-08, 1e-08, 5e-08, 1e-08, -6.591639871382637, -6.591639871382637, -28.353238401469913, -28.353238401469913, 2e-08, 1.111111111111111e-08, -6.591639871382637, 2e-08, -1.1127678274760309, -28.353238401469913, -81.84051544835945, -6.591639871382637, -6.591639871382637, 1e-08, -6.591639871382637, -28.353238401469913, -39.30170378623171, -28.353238401469913, -6.591639871382637, -6.591639871382637, 1e-08, 1e-08, -6.591639871382637, 2e-08, 2e-08, 3.3333333333333334e-08, 5e-08, 1.4285714285714284e-08, 1e-08, 1e-08, 5e-08, 1.2644619817842362e-08, 3.3333333333333334e-08, 8.841767643926996, 24.421132277111408, 36.995842035842, 55.08296671296502, 77.71200093396713, 39.729921833759775, 36.25748806985481, 36.995841973619775, 46.272058847586244, 33.2922064669196, 32.15137064962979, 102.02667425556231, 101.270195476291, 33.64165454167532, 47.50533889065707, 36.22438629953628, 50.032914546229826, 149.88938655425113, 164.75639033134303, 49.28598670856468, 39.729921833759775, 39.69364981326551, 75.7666673091279, 50.45961765571729, 44.22803815589659, 45.342001099503385, 55.957754282307235, 39.729921833759775, 79.29178114304433, 121.68753934622117, 118.02793003981378, 39.69364981326551, 77.64326069410815, 88.1159420414855, 40.20924607035322, 88.1159420164855, 77.64326069410815, 88.1159420414855, 88.90408669519535, 88.1159420164855, 86.51837052300995, 92.4159978027884, 88.11594204327122, 88.11594204327122, 88.11594204327122, 107.89818300358984, 98.67205288371528, 118.04437702357261, 120.20371443463955, 326.2425231103861, 326.2425231103861, 326.2425231103861, 326.2425231103861, 316.0387236446142, 288.02296918914993, 326.2425231103861, 285.75947741802685, 168.69565217993713, 168.69565217993713, 168.69565217993713, 137.48960008779508, 168.69565217993713, 135.41992491493568, 146.6377387000421, 148.20956033541748, 107.49689655345874, 113.78486421091363, 155.72451191368208, 115.31594202898549, 132.07192591975266, 230.7246376871835, 109.62511724766799, 154.89076395967453, 230.7246376751353, 125.29999480606355, 167.22729867144187, 123.42246011194615, 121.74079472331559, 139.78113146543947, 273.9894889315127, 122.5139560438496, 346.0451746989921, 124.41691502160624, 114.34872159239569, 113.60653291964672, 324.22811679225373, 116.12072676487072, 113.96367257201857, 106.50627807999297, 98.64430852018786, 107.909604519774, 107.909604519774, 115.78579602109265, 106.41095955309902, 104.96517448708919, 97.61009126921537, 89.33651990913617, 83.61640781364463, 107.909604519774, 103.67140060762338, 87.50032697278135, 90.63835709219315, 63.99066013848179, 107.909604519774, 89.67684746316051, 107.909604519774, 98.64430852018786, 100.75697392315476, 94.43752579119358, 110.16399825271728, 102.16343538666763, 112.29240903018159, 100.81990039164346, 94.61499924050203, 65.56577744248396, 111.78799878160218, 111.78799878160218, 82.26004967240718, 87.7581067586258, 84.01387828244572, 65.29431474582938, 102.3715583332031, 110.34709875062129, 104.15560544081768, 69.0228382332057, 68.64595009898635, 58.88922733672413, 66.15280631895972, 66.38175459116276, 67.36882748415462, 67.4161942168357, 64.99229382966543, 64.26408094918193, 79.79949920047689, 92.90464177763604, 89.7517095867692, 90.88511052707432, 66.47836545160659, 58.88922733672413, 83.34732916192203, 88.3167023662081, 82.29404656669976, 64.43439398609571, 58.88922733672413, 58.88922733672413, 88.39333358051852, 84.24124470488897, 64.12230126022936, 58.88922733986699, 60.74200525089239, 58.83546357811494, 58.88922733986699, 58.88922733986699, 58.83546357811494, 87.08219815304713, 86.12866519404193, 58.83546357811494, 93.20244255666348, 85.53612327653198, 67.40502237972686, 58.88922734700985, 58.88922734700985, 58.83546357573399]
    # prices2 = [0 for _ in times]
    # u2 = 'DER None Integration Hour'
    # u2 = 'DER None Simplified Integration Test Hour'
    u2 = 'DER None Bilevel Test Hour new'
    battery = Battery(0, int(0 / 3 * 2), usage=u2)
    # _, _, prices2, _ = read_der(0, start, battery.bat_dir)  # First horizon
    _, _, _, _, prices2 = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
    from price import process_prices_by_period
    # _, original_prices, predispatch_time, _, _, _, _, _, extended_times = process_prices_by_period(start, True, battery, 0, False)
    path_to_fig = None
    # prices, prices2 = [], []
    # prices2 = []
    # for t in times:
    #     rrp, _, _, _ = read_dispatch_prices(t, 'dispatch', True, battery.region_id, path_to_out=(default.OUT_DIR / 'non-time-stepped 30min Perfect'))
    #     prices2.append(rrp)
    #     record, _, _, _ = read_dispatch_prices(t, 'dispatch', True, battery.region_id, path_to_out=(default.OUT_DIR / 'non-time-stepped 5min link'))
    #     prices2.append(record)
    #     print(t, rrp, record)
    # _, prices2, _, _, _ = read_predispatch_prices(start, 'predispatch', True, battery.region_id, path_to_out=(default.DEBUG_DIR))

    # times = [start + i * default.FIVE_MIN for i in range(288)]
    # plot_soc(times, [prices, prices2[:len(prices)]], socs, path_to_fig, price_flag=True, soc_flag=True)
    # prices2 = [0 for _ in prices]
    for t, p1, p2 in zip(times, prices, prices2):
        print(t, f'{p1:.2f}', f'{p2:.2f}')
    plot_soc(times, [prices, prices2], socs, path_to_fig, price_flag=True, soc_flag=True, labels=['Bilevel time-stepped+batt', 'Bilevel time-stepped no batt'])