import csv
import datetime
import preprocess


labels = {'DUID', 'DALNTH01', 'DALNTHL1'}


def simplify_bid(t):
    bids_dir = preprocess.download_bidmove_complete(t)
    with bids_dir.open() as f:
        reader = csv.reader(f)
        rows = [row for row in reader if len(row) > 5 and row[5] in labels]
    result_dir = preprocess.DATA_DIR / f"BIDS_{t.strftime('%Y%m%d')}.csv"
    with result_dir.open(mode='w') as f:
        writer = csv.writer(f, delimiter=',')
        for row in rows:
            writer.writerow(row)


def simplify_next_day_dispatch(t):
    record_dir = preprocess.download_next_day_dispatch(t)
    with record_dir.open() as f:
        reader = csv.reader(f)
        rows = [row for row in reader if len(row) > 6 and row[6] in labels]
    result_dir = preprocess.DATA_DIR / f"NEXT_DAY_DISPATCH_{t.strftime('%Y%m%d')}.csv"
    with result_dir.open(mode='w') as f:
        writer = csv.writer(f, delimiter=',')
        for row in rows:
            writer.writerow(row)


def main():
    time = datetime.datetime(2019, 7, 19, 4, 5, 0)
    simplify_next_day_dispatch(time)


if __name__ == '__main__':
    main()