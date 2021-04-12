import csv
import datetime
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pathlib
import preprocess
from price_taker_2 import extract_trading
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
# Battery
region = 'VIC1'
# Datetime
interval_time = []
period_time = []
# Price
period_rrp_record = []
interval_rrp_record = []
period_prices = []


def extract_dispatch(t):
    dispatch_dir = preprocess.download_dispatch_summary(t)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'PRICE' and row[6] == region and row[8] == intervention:
                interval_rrp_record.append(float(row[9]))  # RRP of i
                return None


def extract_predispatch(t):
    predispatch_time = []
    predispatch_prices = []
    dispatch_dir = preprocess.download_predispatch(t)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGION_PRICES' and row[6] == region and row[8] == intervention:
                predispatch_time.append(preprocess.extract_datetime(row[28]))
                predispatch_prices.append(float(row[9]))
    return predispatch_time, predispatch_prices


def extract_5min_predispatch(t):
    fivemin_time = []
    fivemin_prices = []
    dispatch_dir = preprocess.download_5min_predispatch(t)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and row[7] == region and row[5] == intervention:
                fivemin_time.append(preprocess.extract_datetime(row[6]))
                fivemin_prices.append(float(row[8]))
    return fivemin_time, fivemin_prices


def plot_prices(i, current, predispatch_time, predispatch_prices, fivemin_time, fivemin_prices, result_dir):
    plt.figure()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    if datetime.time(4, 5) <= current.time() <= datetime.time(12, 30):
        # plt.plot(interval_time[i:288], interval_rrp_record[i:288], label='Interval get_prices')
        # plt.plot(period_time[(i // 6):48], period_rrp_record[(i // 6):48], label='Period get_prices')
        plt.plot(interval_time[:288], interval_rrp_record[:288], label='Interval (5min) price')
        plt.plot(interval_time[:288], period_prices[:288], label='Period (30min) price')
        # plt.plot(period_time[:48], period_rrp_record[:48], label='Trading get_prices')
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
        plt.gca().xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))
    else:
        plt.plot(interval_time, interval_rrp_record, label='Interval (5min) price')
        plt.plot(interval_time, period_prices, label='Period (30min) price')
        # plt.plot(period_time, period_rrp_record, label='Trading get_prices')
        # plt.plot(interval_time[i:], interval_rrp_record[i:], label='Interval get_prices')
        # plt.plot(period_time[(i//6):], period_rrp_record[(i//6):], label='Period get_prices')
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=8))
        plt.gca().xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 8)))
    plt.plot(predispatch_time, predispatch_prices, label='30min predispatch price')
    plt.plot(fivemin_time, fivemin_prices, label='5min predispatch price')
    plt.xlabel('Datetime')
    plt.ylabel('Price')
    plt.legend()
    plt.savefig(result_dir / preprocess.get_result_datetime(current))
    plt.close()


def main():
    time = datetime.datetime(2019, 7, 19, 4, 0, 0)
    result_dir = OUT_DIR / f'get_prices-{region}-{time.year}-{time.month}-{time.day}'
    result_dir.mkdir(parents=True, exist_ok=True)
    for i in range(TOTAL_INTERVALS * 2):
        interval_time.append(time + FIVE_MIN)
        if i % 6 == 0:
            rrp = extract_trading(time + THIRTY_MIN, region)  # Get spot price for period
            period_rrp_record.append(rrp)
            period_time.append(time + THIRTY_MIN)
        extract_dispatch(time + FIVE_MIN)
        if i % 6 == 5:
            period_price = sum(interval_rrp_record[-6:]) / 6
            for _ in range(5, -1, -1):
                period_prices.append(period_price)
        time += FIVE_MIN

    time = datetime.datetime(2019, 7, 19, 4, 0, 0)
    for i in range(TOTAL_INTERVALS):
    # for i in range(5):
        if i % 6 == 0:
            predispatch_time, predispatch_prices = extract_predispatch(time + THIRTY_MIN)
        fivemin_time, fivemin_prices = extract_5min_predispatch(time + FIVE_MIN)
        plot_prices(i, time + FIVE_MIN, predispatch_time, predispatch_prices, fivemin_time, fivemin_prices, result_dir)
        time += FIVE_MIN


if __name__ == '__main__':
    main()