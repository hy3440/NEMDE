import csv
import datetime
import default
import matplotlib.pyplot as plt

units = {}


def all_zeros(l):
    for element in l:
        if element != 0:
            return False
    return True


def read_results(start, interval):
    current = start + interval * default.FIVE_MIN
    interval_datetime = default.get_case_datetime(current)
    record_dir = default.OUT_DIR / 'dispatch' / f'dispatch_{interval_datetime}.csv'
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                duid = row[1]
                if interval == 0:
                    units[duid] = [[], []]
                units[duid][0].append(float(row[2]))
                units[duid][1].append(float(row[3]))


def main():
    start = datetime.datetime(2020, 6, 1, 4, 10, 0)
    for interval in range(5):
        read_results(start, interval)
    for duid, [results, records] in units.items():
        # if not all_zeros(results) and not all_zeros(records):
        if results != records:
            x = [1, 2, 3, 4, 5]
            plt.plot(x, results, marker='o', color='red', label='Result')
            plt.plot(x, records, marker='o', color='blue', label='Record')
            plt.legend()
            plt.xlabel("Interval No.")
            plt.ylabel("Dispatch Target")
            # plt.show()
            plt.savefig(default.OUT_DIR / 'plots' / duid)
            plt.close()


if __name__ == '__main__':
    main()