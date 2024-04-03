import csv
import datetime
import default
import matplotlib.pyplot as plt
plt.style.use(['science', 'ieee', 'no-latex'])
import matplotlib.dates as mdates
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
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


def compare_with_record():
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


def read_unit_total_cleared(path_to_csv, duid):
    with path_to_csv.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[1] == duid:
                return float(row[2])


def compare_specific_units():
    from helpers import Battery
    import datetime
    duids = ['GSTONE3', 'ER02', 'BW03', 'BW04', 'ER02', 'GSTONE5', 'TUMUT3']
    es = [0.03, 0.06]
    usage = 'Cost-reflective + multiple FCAS'
    start = datetime.datetime(2021, 9, 12, 4, 5)
    batteries = [Battery(e, int(e * 2 / 3) if type(e) == int else (e * 2 / 3), usage=usage) for e in es]
    for n, duid in enumerate(duids):
        print(f'## {n + 1}. Unit ID: {duid}\n')
        print('Datetime  | Battery 1 | Battery 2 | Difference | Without Battery')
        print('----------|-----------|-----------|------------|----------------')
        for i in range(288):
            current = start + (i + 1) * default.FIVE_MIN
            powers = [read_unit_total_cleared(
                b.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(current)}.csv', duid) for b in
                batteries]
            if powers[0] != powers[1] and abs(powers[0] - powers[1]) > 1:
                p = read_unit_total_cleared(
                    default.RECORD_DIR / 'dispatch' / f'dispatchload_{default.get_case_datetime(current)}.csv', duid)
                print(f'`{current}` | {powers[0]:.2f} | {powers[1]:.2f} | {(powers[0] - powers[1]):.2f} | {p:.2f}')
        print('\n')


def read_all_units(path_to_csv, units, no):
    with path_to_csv.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                if row[1] not in units:
                    units[row[1]] = [[], [], []]
                units[row[1]][no].append(float(row[2]))


def plot_unit(duid, times, p1, p2, p0):
    fig = plt.figure()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=6))
    plt.gca().xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
    plt.xlabel("Interval")
    plt.plot(times, p1, color=default.PURPLE, label='Batt1')
    plt.plot(times, p2, color=default.BROWN, label='Batt2')
    if p0:
        plt.plot(times, p0, color=default.BLUE, label='No batt')
    plt.legend()
    plt.ylabel("Price (\$/MWh)")
    if '/' in duid:
        duid = duid.replace('/', '-')
    plt.savefig(default.OUT_DIR / 'units' / f'{duid}.jpg')
    plt.close()


def compare_all_units(sign):
    from helpers import Battery
    import datetime
    es = [0.03, 0.06]
    usage = 'Cost-reflective + multiple FCAS'
    start = datetime.datetime(2021, 9, 12, 4, 5)
    batteries = [Battery(e, int(e * 2 / 3) if type(e) == int else (e * 2 / 3), usage=usage) for e in es]
    units, times = {}, []
    # for n, duid in enumerate(duids):
    #     print(f'## {n + 1}. Unit ID: {duid}\n')
    #     print('Datetime  | Battery 1 | Battery 2 | Difference | Without Battery')
    #     print('----------|-----------|-----------|------------|----------------')
    for i in range(288):
        current = start + (i + 1) * default.FIVE_MIN
        times.append(current)
        for no, battery in enumerate(batteries):
            path_to_csv = battery.bat_dir / f'dispatch{sign}' / f'dispatchload_{default.get_case_datetime(current)}.csv'
            read_all_units(path_to_csv, units, no)
        path_to_csv = default.OUT_DIR / 'sequence' / 'dispatch' / f'dispatchload_{default.get_case_datetime(current)}.csv'
        read_all_units(path_to_csv, units, 2)
    different_units = set()
    path_to_out = default.OUT_DIR / f'units{sign}.csv'
    different_times = {}
    with path_to_out.open('w') as f:
        writer = csv.writer(f)
        writer.writerow('ID, Interval, Dispatch Result - batt1, Dispatch Result - batt2, Dispatch Result - no batt, Difference'.split(', '))
        for duid, (p1, p2, p0) in units.items():
            for t, pp1, pp2, pp0 in zip(times, p1, p2, p0):
                if abs(pp1 - pp2) > 0.001:
                    writer.writerow(f'{duid}, {t}, {pp1:.2f}, {pp2:.2f}, {pp0:.2f}, {pp1 - pp2:.2f}'.split(', '))
                    different_units.add(duid)
                    if t not in different_times:
                        different_times[t] = 0
                    different_times[t] += (pp1 - pp2)
                if abs(pp1 - pp2) > 0.01:
                   print(f'{duid}, {t}, {pp1:.2f}, {pp2:.2f}, {pp0:.2f}, {pp1 - pp2:.2f}')
    # for duid, (p1, p2, p0) in units.items():
    #     if duid in different_units:
    #         plot_unit(duid, times, p1, p2, p0)
    # print(f'{len(different_units)} units have different results ({len(units)} in total).')
    print('Interval, Total difference')
    for t in sorted(different_times.keys()):
        print(f'{t}, {different_times[t]:.2f}')
    path_to_out = default.OUT_DIR / f'all_units{sign}.csv'
    with path_to_out.open('w') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Battery'] + times)
        for duid, (p1, p2, p0) in units.items():
            writer.writerow([duid, 'batt1'] + p1)
            writer.writerow([duid, 'batt2'] + p2)
            writer.writerow([duid, 'no batt'] + p0)


def compare_obj():
    current = datetime.datetime(2021, 9, 12, 6, 35)
    path_to_batt11 = default.DEBUG_DIR / f'obj_{default.get_case_datetime(current)}-batt11.csv'
    path_to_batt22 = default.DEBUG_DIR / f'obj_{default.get_case_datetime(current)}-batt22.csv'
    var11, var22, coe11, coe22 = {}, {}, {}, {}
    for p, v, c in [(path_to_batt11, var11, coe11), (path_to_batt22, var22, coe22)]:
        with p.open() as f:
            reader = csv.reader(f)
            for row in reader:
                v[row[0]] = float(row[1])
                c[row[0]] = float(row[2])
    print('Var Name, Coefficient, Value1, Value2, Difference in objective')
    for k in var11.keys():
        if var11[k] != var22[k]:
            print(f'{k}, {coe11[k]}, {var11[k]}, {var22[k]}, {(var11[k] - var22[k]) * coe22[k]}')


def compare_given_unit():
    duid = 'YARWUN_1'
    from helpers import Battery
    import datetime
    u1 = 'Price-taker Hour Temp'
    u2 = 'DER None Integrated Hour No-losses Check'
    start = datetime.datetime(2021, 7, 18, 4, 35)
    e = 0
    p1, p2 = [], []
    batteries = [Battery(e, int(e * 2 / 3) if type(e) == int else (e * 2 / 3), usage=u) for u in [u1, u2]]
    for i in range(24):
        current = start + i * default.ONE_HOUR
        print(current)
        powers = [read_unit_total_cleared(b.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(current)}.csv', duid) for b in batteries]
        p1.append(powers[0])
        p2.append(powers[1])
    fig = plt.figure()
    plt.xlabel("Period")
    plt.plot(range(24), p1, color=default.PURPLE, label=u1)
    plt.plot(range(24), p2, color=default.BROWN, label=u2)
    plt.legend()
    plt.ylabel("MW")
    if '/' in duid:
        duid = duid.replace('/', '-')
    # plt.savefig(default.OUT_DIR / 'units' / f'{duid}.jpg')
    plt.show()
    plt.close()


if __name__ == '__main__':
    # compare_all_units('-tiebreak')
    # compare_obj()
    compare_given_unit()