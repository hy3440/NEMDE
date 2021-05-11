import csv
import datetime
import default
# import gurobipy
import logging
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
# import pandas as pd
import pathlib
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
    record_dir = default.OUT_DIR / 'dispatch' / f'DISPATCHIS_{interval_datetime}.csv'
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                price = float(row[9])
                record = float(row[10])
                if abs(price - record) > 10:
                    # print(f'{current} {price} AEMO: {record}')
                    region_times[row[6]].append(current)
                    region_price[row[6]].append(price)
                    region_price_record[row[6]].append(float(record))


def main():
    start = datetime.datetime(2020, 9, 1, 4, 5, 0)
    end = datetime.datetime(2020, 9, 2, 4, 5, 0)
    current = start
    while current < end:
        read_dispatchis(start, current)
        current += default.FIVE_MIN

    for index, region in enumerate(region_gen):
        fig = plt.figure()
        # fig, axs = plt.subplots(5, 1, constrained_layout=True)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
        plt.gca().xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))
        plt.scatter(region_times[region], region_price[region], color='red', label='Simulator Result')
        plt.scatter(region_times[region], region_price_record[region], color='blue', label='AEMO Record')
        # axs[index].plot(times, region_price[region], color='red', label='Result')
        # axs[index].plot(times, region_price_record[region], color='blue', label='Record')
        plt.legend()
        plt.xlabel("Interval")
        plt.ylabel("Price ($/MW)")
        # plt.show()
        # axs[index].set_title(region)
        path_to_save = default.OUT_DIR / f'prices_{default.get_case_datetime(start)}'
        path_to_save.mkdir(parents=True, exist_ok=True)
        plt.savefig(path_to_save / f'{region}.png')
        plt.close()

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


if __name__ == '__main__':
    main()
