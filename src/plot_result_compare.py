# Plot comparison between NEMDE simulato and AEMO record
import csv
import datetime
import default
import matplotlib.pyplot as plt
# plt.style.use(['science', 'ieee', 'bright'])
plt.style.use(['science', 'ieee', 'no-latex'])
import matplotlib.dates as mdates
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

times = []
region_times = {
    'NSW1': [],
    'QLD1': [],
    'SA1': [],
    'TAS1': [],
    'VIC1': []
}
region_gen = {
    'NSW1': [],
    'QLD1': [],
    'SA1': [],
    'TAS1': [],
    'VIC1': []
}
region_gen_record = {
    'NSW1': [],
    'QLD1': [],
    'SA1': [],
    'TAS1': [],
    'VIC1': []
}
interconnector_target = {
    'N-Q-MNSP1': [],
    'NSW1-QLD1': [],
    'VIC1-NSW1': [],
    'T-V-MNSP1': [],
    'V-SA': [],
    'V-S-MNSP1': []
}
interconnector_record = {
    'N-Q-MNSP1': [],
    'NSW1-QLD1': [],
    'VIC1-NSW1': [],
    'T-V-MNSP1': [],
    'V-SA': [],
    'V-S-MNSP1': []
}
region_price = {
    'NSW1': [],
    'QLD1': [],
    'SA1': [],
    'TAS1': [],
    'VIC1': []
}
region_price_record = {
    'NSW1': [],
    'QLD1': [],
    'SA1': [],
    'TAS1': [],
    'VIC1': []
}


def read_dispatch(start, current):
    # current = start + interval * preprocess.FIVE_MIN
    times.append(current)
    interval_datetime = default.get_case_datetime(current)
    record_dir = default.OUT_DIR / f'dispatch_{default.get_case_datetime(start)}-result' / f'dispatch_{interval_datetime}.csv'
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'REGIONSUM' and row[1] != 'Region ID':
                region_gen[row[1]].append(float(row[2]))
                region_gen_record[row[1]].append(float(row[3]))
            elif row[0] in interconnector_record.keys():
                interconnector_target[row[0]].append(float(row[1]))
                interconnector_record[row[0]].append(float(row[2]))


def read_dispatchis(start, current):
    times.append(current)
    # current = start + interval * preprocess.FIVE_MIN
    interval_datetime = default.get_case_datetime(current)
    record_dir = default.DEBUG_DIR / 'dispatch' / f'DISPATCHIS_{interval_datetime}.csv'
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                price = float(row[9])
                # record = float(row[10])
                region_times[row[6]].append(current)
                region_price[row[6]].append(price)
                # region_price_record[row[6]].append(float(record))

    # record_dir = default.DEBUG_DIR / 'dispatch-sos' / f'DISPATCHIS_{interval_datetime}.csv'
    record_dir = default.OUT_DIR / 'tiebreak' / 'dispatch' / f'DISPATCHIS_{interval_datetime}.csv'
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                # price = float(row[9])
                record = float(row[10])
                # region_times[row[6]].append(current)
                # region_price[row[6]].append(price)
                region_price_record[row[6]].append(record)
                # if price < 0 and row[6] == 'NSW1':
                #     print(current, region_price['NSW1'][-1], record, price)


def plot_region_lineplot(start):
    for region in region_times.keys():
        if region != 'NSW1':
            continue
        # fig, axs = plt.subplots(5, 1, constrained_layout=True)
        if len(times) <= 288:
            fig = plt.figure()
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=6))
            plt.gca().xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
            plt.xlabel("Interval")
        else:
            fig, ax1 = plt.subplots(figsize=(8, 4))
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d'))
            ax1.xaxis.set_major_locator(mdates.DayLocator())
            ax1.xaxis.set_minor_locator(mdates.DayLocator())
            ax1.set_xlabel('Date')
        # plt.plot(region_times[region], region_price_record[region], label='AEMO Record')
        # plt.plot(region_times[region], region_price[region], label='Simulator Result')
        plt.plot(times, region_price_record[region], color=default.PURPLE, label='AEMO Record', alpha=0.4, linewidth=2)
        plt.plot(times, region_price[region], '-', color=default.BLUE, label='Simulator Result', linewidth=0.3)
        plt.legend()
        plt.ylabel("Price (\$/MWh)")
        # plt.axvline(datetime.datetime(2020, 9, 1, 16, 30), 0, 100, c="r")
        # plt.axvline(datetime.datetime(2020, 9, 1, 20, 0), 0, 100, c="r")

        # path_to_save = default.OUT_DIR / f'prices_{default.get_case_datetime(start)}'
        # path_to_save.mkdir(parents=True, exist_ok=True)
        # plt.savefig(path_to_save / f'{region}.png')
        plt.show()
        plt.close()


def plot_region_boxplot(start):
    import numpy as np
    fig = plt.figure()

    data_a = list(region_price_record.values())
    data_b = list(region_price.values())
    ticks = list(region_price.keys())

    def set_box_color(bp, color):
        plt.setp(bp['boxes'], color=color)
        plt.setp(bp['whiskers'], color=color)
        plt.setp(bp['caps'], color=color)
        plt.setp(bp['medians'], color=color)

    plt.figure()

    bpl = plt.boxplot(data_a, positions=np.array(range(len(data_a))) * 2.0 - 0.4, sym='', widths=0.6)
    bpr = plt.boxplot(data_b, positions=np.array(range(len(data_b))) * 2.0 + 0.4, sym='', widths=0.6)
    set_box_color(bpl, default.PURPLE)  # colors are from http://colorbrewer2.org/
    set_box_color(bpr, default.BROWN)

    # draw temporary red and blue lines and use them to create a legend
    # plt.plot([], c='#D7191C', label='AEMO Record')
    # plt.plot([], c='#2C7BB6', label='Simulator Result')
    plt.plot([], c=default.PURPLE, label='AEMO Record')
    plt.plot([], c=default.BROWN, label='Simulator Result')
    plt.legend()

    plt.xticks(range(0, len(ticks) * 2, 2), ticks)
    plt.xlim(-2, len(ticks) * 2)
    # plt.ylim(0, 8)
    plt.tight_layout()
    # plt.show()
    path_to_save = default.OUT_DIR / f'prices_{default.get_case_datetime(start)}'
    path_to_save.mkdir(parents=True, exist_ok=True)
    plt.savefig(path_to_save / f'boxplot.png')
    plt.close()


def plot_region():
    # start = datetime.datetime(2020, 9, 1, 4, 5)
    # end = datetime.datetime(2020, 9, 2, 4, 5)
    start = datetime.datetime(2021, 9, 12, 4, 5)
    end = datetime.datetime(2021, 9, 13, 4, 5)
    current = start
    while current < end:
        read_dispatchis(start, current)
        current += default.FIVE_MIN
    plot_region_lineplot(start)
    # plot_region_boxplot(start)

    # for index, region in enumerate(region_gen):
    #     # plt.subplot(5, 1, index + 1)
    #     axs[index].plot(times, region_gen[region], color='red', label='Result')
    #     axs[index].plot(times, region_gen_record[region], color='blue', label='Record')
    #     axs[index].legend()
    #     # plt.xlabel("Interval")
    #     # plt.ylabel("Dispatch Target")
    #     # plt.show()
    #     axs[index].set_title(region)
    # plt.savefig(default.OUT_DIR / 'plots' / 'regions')
    # plt.close()
    #
    # for ic in interconnector_target.keys():
    #     plt.plot(times, interconnector_target[ic], color='red', label='Result')
    #     plt.plot(times, interconnector_record[ic], color='blue', label='Record')
    #     plt.legend()
    #     plt.xlabel("Interval")
    #     plt.ylabel("Dispatch Target")
    #     # plt.show()
    #     plt.savefig(default.OUT_DIR / 'plots' / ic)
    #     plt.close()


def compare_prices():
    from read import read_dispatch_prices
    start = datetime.datetime(2021, 9, 12, 4, 5)
    end = datetime.datetime(2021, 9, 13, 4, 5)
    current = start
    path_to_tiebreak = default.OUT_DIR / 'tiebreak'
    path_to_sequence = default.OUT_DIR / 'sequence'
    region_id = 'NSW1'
    while current < end:
        p1, rrp_record, _, _ = read_dispatch_prices(current, 'dispatch', True, region_id, path_to_out=path_to_tiebreak, fcas_flag=True)
        p2, _, _, _ = read_dispatch_prices(current, 'dispatch', True, region_id, path_to_out=path_to_sequence, fcas_flag=True)
        print(current, p1, p2, rrp_record)
        current += default.FIVE_MIN


if __name__ == '__main__':
    plot_region()