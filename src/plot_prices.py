import csv
import datetime
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pathlib
import preprocess
from price_taker import Battery
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent  # Base directory
DATA_DIR = BASE_DIR.joinpath('data')  # Data directory
OUT_DIR = BASE_DIR.joinpath('out')  # Result directory
FIVE_MIN = datetime.timedelta(minutes=5)
THIRTY_MIN = datetime.timedelta(minutes=30)
ONE_DAY = datetime.timedelta(days=1)
TOTAL_INTERVALS = 288
intervention = '0'
# for b in ['']
battery = Battery('Ballarat')
# Datetime
interval_time = []
period_time = []
# Price
period_rrp_record = {
    'NSW1': [],
    'SA1': [],
    'VIC1': [],
    'TAS1': [],
    'QLD1': []
}
interval_rrp_record = {
    'NSW1': [],
    'SA1': [],
    'VIC1': [],
    'TAS1': [],
    'QLD1': []
}
fcas_price_record = {
    'Raisereg': [],
    'Raise5min': [],
    'Raise60sec': [],
    'Raise6sec': [],
    'Lowerreg': [],
    'Lower5min': [],
    'Lower60sec': [],
    'Lower6sec': []
}
region = 'VIC1'


def extract_next_day_dispatch(t):
    record_dir = preprocess.download_next_day_dispatch(t)
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'UNIT_SOLUTION' and row[6] == battery.gen_id and row[9] == intervention:
                # actual_gen_record.append(float(row[13]))  # Initial MW
                # energy_gen_record.append(float(row[14]))  # Total cleared
                battery.gen_fcas_record['Raise6sec'].append(float(row[22]))
                battery.gen_fcas_record['Raise60sec'].append(float(row[21]))
                battery.gen_fcas_record['Raise5min'].append(float(row[20]))
                battery.gen_fcas_record['Raisereg'].append(float(row[35]))
                battery.gen_fcas_record['Lower6sec'].append(float(row[19]))
                battery.gen_fcas_record['Lower60sec'].append(float(row[18]))
                battery.gen_fcas_record['Lower5min'].append(float(row[17]))
                battery.gen_fcas_record['Lowerreg'].append(float(row[34]))
            elif row[0] == 'D' and row[2] == 'UNIT_SOLUTION' and row[6] == battery.load_id and row[9] == intervention:
                # actual_load_record.append(float(row[13]))  # Initial MW
                # energy_load_record.append(float(row[14]))  # Total cleared
                battery.load_fcas_record['Raise6sec'].append(float(row[22]))
                battery.load_fcas_record['Raise60sec'].append(float(row[21]))
                battery.load_fcas_record['Raise5min'].append(float(row[20]))
                battery.load_fcas_record['Raisereg'].append(float(row[35]))
                battery.load_fcas_record['Lower6sec'].append(float(row[19]))
                battery.load_fcas_record['Lower60sec'].append(float(row[18]))
                battery.load_fcas_record['Lower5min'].append(float(row[17]))
                battery.load_fcas_record['Lowerreg'].append(float(row[34]))


def extract_trading(t):
    trading_dir = preprocess.download_trading(t)
    with trading_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'PRICE':
                period_rrp_record[row[6]].append(float(row[8]))  # RRP of period


def extract_dispatch(t):
    dispatch_dir = preprocess.download_dispatch_summary(t)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'PRICE' and row[8] == intervention:
                interval_rrp_record[row[6]].append(float(row[9]))  # RRP of interval
                if row[6] == region:
                    fcas_price_record['Raise6sec'].append(float(row[15]))
                    fcas_price_record['Raise60sec'].append(float(row[18]))
                    fcas_price_record['Raise5min'].append(float(row[21]))
                    fcas_price_record['Raisereg'].append(float(row[24]))
                    fcas_price_record['Lower6sec'].append(float(row[27]))
                    fcas_price_record['Lower60sec'].append(float(row[30]))
                    fcas_price_record['Lower5min'].append(float(row[33]))
                    fcas_price_record['Lowerreg'].append(float(row[36]))


# def extract_predispatch(t):
#     predispatch_time = []
#     predispatch_prices = []
#     dispatch_dir = preprocess.download_predispatch(t)
#     with dispatch_dir.open() as f:
#         reader = csv.reader(f)
#         for row in reader:
#             if row[0] == 'D' and row[2] == 'REGION_PRICES' and row[6] == region and row[8] == intervention:
#                 predispatch_time.append(preprocess.extract_datetime(row[28]))
#                 predispatch_prices.append(float(row[9]))
#     return predispatch_time, predispatch_prices


# def extract_5min_predispatch(t):
#     fivemin_time = []
#     fivemin_prices = []
#     dispatch_dir = preprocess.download_5min_predispatch(t)
#     with dispatch_dir.open() as f:
#         reader = csv.reader(f)
#         for row in reader:
#             if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and row[7] == region and row[5] == intervention:
#                 fivemin_time.append(preprocess.extract_datetime(row[6]))
#                 fivemin_prices.append(float(row[8]))
#     return fivemin_time, fivemin_prices


def plot_region_prices(date, prices, name):
    plt.figure()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # plt.plot(interval_time[:288], interval_rrp_record[:288], label='Interval (5min) price')
    # plt.plot(interval_time[:288], period_prices[:288], label='Period (30min) price')
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=8))
    plt.gca().xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 8)))

    for r, region_prices in prices.items():
        if name == 'interval':
            plt.plot(interval_time, region_prices, label=r)
        else:
            plt.plot(interval_time, [i for i in region_prices for _ in range(6)], label=r)
    
    plt.xlabel('Datetime')
    plt.ylabel('Price')
    plt.legend()
    plt.savefig(OUT_DIR / f'{name}-prices-{date}')
    plt.close()


def plot_fcas_prices(date):
    plt.figure()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # plt.plot(interval_time[:288], interval_rrp_record[:288], label='Interval (5min) price')
    # plt.plot(interval_time[:288], period_prices[:288], label='Period (30min) price')
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=8))
    plt.gca().xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 8)))

    plt.plot(interval_time, [i for i in period_rrp_record[region] for _ in range(6)], label='Energy')
    for fcas, prices in fcas_price_record.items():
        plt.plot(interval_time, prices, label=fcas)

    plt.xlabel('Datetime')
    plt.ylabel('Price')
    plt.legend()
    plt.savefig(OUT_DIR / f'{region}-prices-{date}')
    plt.close()


def plot_bat_fcas(fcas_type, date):
    fig, ax1 = plt.subplots()
    ax1.set_xlabel('Datetime')
    col = 'tab:green'
    ax1.set_ylabel('$/MW', color=col)
    ax1.plot(interval_time, fcas_price_record[fcas_type], label='Price', color=col)
    ax1.tick_params(axis='y', labelcolor=col)

    ax2 = ax1.twinx()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))

    ax2.set_ylabel('MW')
    if fcas_type in battery.gen_fcas_types:
        # print(battery.gen_fcas_record[fcas_type])
        ax2.plot(interval_time, battery.gen_fcas_record[fcas_type], label='Gen')
    if fcas_type in battery.load_fcas_types:
        ax2.plot(interval_time, battery.load_fcas_record[fcas_type], label='Load')

    plt.xlabel('Datetime')
    # plt.ylabel('Price')
    plt.legend()
    plt.savefig(battery.bat_dir / f'{fcas_type}-prices-{date}')
    plt.close()


def main():
    time = datetime.datetime(2019, 7, 19, 4, 0, 0)
    date = time.strftime('%Y-%m-%d')  # YY-mm-dd
    # result_dir.mkdir(parents=True, exist_ok=True)
    extract_next_day_dispatch(time+FIVE_MIN)
    for i in range(TOTAL_INTERVALS):
        interval_time.append(time + FIVE_MIN)
        # if i % 6 == 0:
        #     extract_trading(time + THIRTY_MIN)  # Get spot price for period
        extract_dispatch(time + FIVE_MIN)
        time += FIVE_MIN

    # plot_region_prices(date, interval_rrp_record, 'interval')
    # plot_region_prices(date, period_rrp_record, 'period')

    # plot_fcas_prices(date)
    for fcas_type in fcas_price_record.keys():
        plot_bat_fcas(fcas_type, date)


if __name__ == '__main__':
    main()