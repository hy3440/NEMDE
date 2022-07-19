# Download and plot weather data from government
# Source: http://www.bom.gov.au/climate/dwo/202106/html/IDCJDW2124.202106.shtml

import csv
import datetime
from dateutil.relativedelta import *
import default
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
import matplotlib.pyplot as plt
plt.style.use(['science', 'ieee', 'bright', 'no-latex'])
import matplotlib.dates as mdates
import requests


headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'}
times, min_temp, max_temp, rain = [], [], [], []


def get_url(url):
    result = requests.get(url, headers=headers)
    decoded_content = result.content.decode('latin1')
    cr = csv.reader(decoded_content.splitlines(), delimiter=',')
    my_list = list(cr)
    for row in my_list:
        # print(row)
        if len(row) > 2 and row[0] == '' and row[1] != 'Date':
            current = datetime.datetime.strptime(row[1], '%Y-%m-%d')
            times.append(current)
            min_temp.append(float(row[2]) if row[2] else None)
            max_temp.append(float(row[3]) if row[3] else 0)
            rain.append(float(row[4]) if row[4] else None)


t = datetime.datetime(2021, 9, 1)
end = datetime.datetime(2021, 10, 1)
while t < end:
    url = f'http://www.bom.gov.au/climate/dwo/{t.year}{t.month:02d}/text/IDCJDW2124.{t.year}{t.month:02d}.csv'
    get_url(url)
    t += relativedelta(months=1)

fig, ax2 = plt.subplots()
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d'))
# ax2.xaxis.set_major_locator(mdates.HourLocator(interval=4))
# ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))
ax2.set_ylabel('Temperature (°C)')
# ax2.plot(energy_times, [price_dict[t] for t in energy_times], label='Actual price')
# ax2.plot(predispatch_times, predispatch_energy_prices, label='30min Predispatch')
# ax2.plot(p5min_times, p5min_energy_prices, label='5min predispatch')
lns2 = ax2.plot(times, min_temp, label=f'Min')
lns3 = ax2.plot(times, max_temp, label=f'Max')

# ax1 = ax2.twinx()
# ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m'))
# ax1.set_ylabel('Rainfall (mm)')
# lns1 = ax1.plot(times, rain, label=f'Rain')

# plt.legend()
lns = lns3 + lns2
labs = [l.get_label() for l in lns]
ax2.legend(lns, labs, loc=0)
plt.savefig(default.OUT_DIR / 'weather' / '202109.png')
plt.show()
plt.close(fig)

# max_value = max(max_temp)
# max_index = max_temp.index(max_value)
# print(max_value)
# print(times[max_index])