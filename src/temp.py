import csv
import datetime
import default
import matplotlib.pyplot as plt
# plt.style.use(['science', 'ieee', 'bright'])
plt.style.use(['science', 'ieee', 'no-latex'])
import matplotlib.dates as mdates
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
from pylab import mpl
mpl.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus']=False

line_flag = False
region_id = 'QLD1'
start = datetime.datetime(2021, 9, 12, 4, 5)
end = datetime.datetime(2021, 9, 19, 4, 5)
present = datetime.datetime(2021,7,18,4,5)

region_price = {
    'NSW': [],
    'QLD': [],
    'SA': [],
    'TAS': [],
    'VIC': []
}
region_price_record = {
    'NSW': [],
    'QLD': [],
    'SA': [],
    'TAS': [],
    'VIC': []
}

def read_price(current):
    file_dir = default.OUT_DIR / 'Cost-reflective' / 'Battery 0.03MWh 0.02MW NSW1 Method 2' / 'dispatch' / f'DISPATCHIS_{default.get_case_datetime(current)}.csv'
    with file_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[6] == region_id and line_flag:
                return float(row[9]), float(row[10])
            if row[0] == 'D':
                # region_price[row[6]].append(max(0, float(row[9])))
                # region_price_record[row[6]].append(max(0, float(row[10])))
                region_price[row[6][:-1]].append(float(row[9]))
                region_price_record[row[6][:-1]].append(float(row[10]))
    return None, None


current = start
times, prices, records = [], [], []
while current < end:
    price, record = read_price(current)
    times.append(present)
    if line_flag:
        prices.append(0 if price < -200 else price)
        records.append(0 if record < -200 else record)
        # prices.append(price)
        # records.append(record)
    # print(current, price, record)
    present += default.FIVE_MIN
    current += default.FIVE_MIN


def plot_lineplot(times, prices, records):
    fig = plt.figure()
    # plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    # plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=6))
    # plt.gca().xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
    # plt.xlabel("Interval")

    fig, ax1 = plt.subplots(figsize=(8, 4))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d'))
    ax1.xaxis.set_major_locator(mdates.DayLocator())
    ax1.xaxis.set_minor_locator(mdates.DayLocator())
    ax1.set_xlabel('Date')

    plt.plot(times, records, color=default.PURPLE, label='AEMO Record', alpha=0.4, linewidth=2)
    plt.plot(times, prices, '-', color=default.BLUE, label='Simulator Result', linewidth=0.3)
    plt.legend()
    plt.ylabel("Price (\$/MWh)")

    plt.savefig(default.OUT_DIR / 'thesis' / 'line.jpg')
    plt.close()


def plot_region_boxplot(start):
    import numpy as np
    fig = plt.figure()

    # print(region_price_record)

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
    set_box_color(bpr, default.BLUE)

    # draw temporary red and blue lines and use them to create a legend
    # plt.plot([], c='#D7191C', label='AEMO Record')
    # plt.plot([], c='#2C7BB6', label='Simulator Result')
    plt.plot([], c=default.PURPLE, label='AEMO Record')
    plt.plot([], c=default.BLUE, label='Simulator Result', linestyle='-')
    plt.legend()

    plt.xticks(range(0, len(ticks) * 2, 2), ticks)
    plt.xlim(-2, len(ticks) * 2)
    # plt.ylim(0, 8)
    plt.tight_layout()
    # plt.show()

    plt.savefig(default.OUT_DIR / 'thesis' / 'box.jpg')
    plt.close()

if line_flag:
    plot_lineplot(times, prices, records)
else:
    for k, v in region_price.items():
        print(k, len(v))
    for k, v in region_price_record.items():
        print(k, len(v))
    plot_region_boxplot(start)