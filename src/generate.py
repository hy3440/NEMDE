import csv
import datetime
import default
import read


def extract_from_dvd():
    src = default.DATA_DIR / 'PUBLIC_DVD_PREDISPATCHPRICE_202008010000.CSV'
    dist = default.DATA_DIR / '20200901' / 'PUBLIC_PREDISPATCHIS_202009010400.CSV'

    with dist.open('w') as dist_file:
        writer = csv.writer(dist_file)
        with src.open('r') as src_file:
            reader = csv.reader(src_file)
            for row in reader:
                if row[0] == 'D' and row[4] != '2020083148':
                    continue
                writer.writerow(row)


t1 = datetime.datetime(2020, 9, 1, 4, 0)
times1, prices1, _, _, _ = read.read_predispatch_prices(t1, process='predispatch', custom_flag=False, region_id='NSW1', k=0, path_to_out=default.OUT_DIR, intervention='0', fcas_flag=False)
t2 = datetime.datetime(2020, 9, 1, 4, 30)
times2, prices2, _, _, _ = read.read_predispatch_prices(t2, process='predispatch', custom_flag=True, region_id='NSW1', k=0, path_to_out=default.OUT_DIR, intervention='0', fcas_flag=False)

# for tt1, p1, tt2, p2 in zip(times1[1:], prices1[1:], times2, prices2):
#     print(tt1, p1, tt2, p2)
print(max(prices1), max(prices2))
print(min(prices1), min(prices2))