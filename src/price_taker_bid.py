import csv
import datetime
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import preprocess

bid_type = 'ENERGY'
TOTAL_INTERVAL = 5
region = 'SA1'
gen_id = 'DALNTH01'
load_id = 'DALNTHL1'

avails = []


def extract_bids(t):
    bids_dir = preprocess.download_bidmove_complete(t)
    with bids_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'BIDDAYOFFER_D':
                if row[5] == gen_id and row[6] == bid_type:
                    price_band = [float(price) for price in row[13:23]]

            elif row[0] == 'D' and row[2] == 'BIDPEROFFER_D':
                if row[5] == gen_id and row[6] == bid_type:
                    band_avail = [int(avail) for avail in row[19:29]]
                    avails.append(band_avail)
                    if len(avails) == TOTAL_INTERVAL:
                        print(row[31])
                        return price_band


t = datetime.datetime(2019, 7, 24, 4, 5, 0)
price_band = extract_bids(t)
x = np.arange(TOTAL_INTERVAL)

labels = ['G1', 'G2', 'G3', 'G4', 'G5']
men_means = [20, 34, 30, 35, 27]
women_means = [25, 32, 34, 20, 25]

x = np.arange(len(labels))  # the label locations
width = 0.35  # the width of the bars

for i in range(TOTAL_INTERVAL):



fig, ax = plt.subplots()
rects1 = ax.bar(start1, price_band[1], width1, label='Price band 1')
rects2 = ax.bar(start2, price_band[2], width2, label='Price band 2')
rects3 = ax.bar(start3, price_band[3], width3, label='Price band 3')
rects4 = ax.bar(start4, price_band[4], width4, label='Price band 4')
rects5 = ax.bar(start5, price_band[5], width5, label='Price band 5')
rects6 = ax.bar(start6, price_band[6], width6, label='Price band 6')
rects7 = ax.bar(start7, price_band[7], width7, label='Price band 7')
rects8 = ax.bar(start8, price_band[8], width8, label='Price band 8')
rects9 = ax.bar(start9, price_band[9], width9, label='Price band 9')
rects10 = ax.bar(start10, price_band[10], width10, label='Price band 10')


# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Price')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend()

fig.tight_layout()
plt.savefig(preprocess.OUT_DIR / bid_type)
plt.show()

