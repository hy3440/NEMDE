import datetime
import default
import difflib
from helpers import generate_batteries_by_energies, generate_batteries_by_usages
import os


def vimdiff(file1, file2):
    path1 = f'{file1}'.replace(' ', '\ ')
    path2 = f'{file2}'.replace(' ', '\ ')
    os.system(f"vimdiff {path1} {path2}")


def compare_summary(start, battery1, battery2):
    file1 = battery1.bat_dir / f'{default.get_case_datetime(start)}.csv'
    file2 = battery2.bat_dir / f'{default.get_case_datetime(start)}.csv'
    vimdiff(file1, file2)


def compare_dispatchload(battery1, battery2, current):
    file1 = battery1.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(current)}.csv'
    file2 = battery2.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(current)}.csv'
    vimdiff(file1, file2)


def command():
    # check_sign = ' Check'
    check_sign = ''
    renewable_no = ' 571'
    elastic_flag = True
    # path_to_dir = default.EXPERIMENT_DIR / 'PESGM2023'
    path_to_dir = default.EXPERIMENT_DIR / 'temp'
    u1 = f'DER None Integrated Hour No-losses{check_sign}'
    # u2 = 'DER None Elastic Bilevel Hour No-losses'
    u4 = 'Cost-reflective Hour Test'
    u3 = f'Price-taker Hour{check_sign}'
    # u3 = 'Price-taker 5MIN'
    # u4 = 'Cost-reflective 5MIN'
    u2 = f'DER None Elastic Bilevel Hour No-losses{check_sign}' if elastic_flag else f'DER None Inelastic Bilevel Hour No-losses{check_sign}'
    u5 = f'DER None Integrated Hour No-losses Perfect{check_sign}'
    u6 = f'DER None Elastic Bilevel Hour No-losses Perfect{check_sign}' if elastic_flag else f'DER None Inelastic Bilevel Hour No-losses Perfect{check_sign}'
    u7 = f'DER None Integrated Hour No-losses Renewable{renewable_no}{check_sign}'
    u8 = f'DER None Elastic Bilevel Hour No-losses Renewable{renewable_no}{check_sign}' if elastic_flag else f'DER None Inelastic Bilevel Hour No-losses Renewable{renewable_no}{check_sign}'
    u9 = 'Price-taker Hour Renewable'
    start = datetime.datetime(2021, 7, 18, 4, 30)
    # start = datetime.datetime(2021, 9, 12, 4, 5)
    # start = datetime.datetime(2022, 1, 3, 4, 30)
    # start = datetime.datetime(2020, 9, 1, 4, 30)
    # start = datetime.datetime(2021, 9, 12, 4, 30)
    energies = [0, 30, 300, 3000, 15000]
    # energies = [0, 30]
    integrated = generate_batteries_by_energies(energies, u1)
    strategic = generate_batteries_by_energies(energies, u2)
    price_taker = generate_batteries_by_energies(energies, u3)
    cost_reflective = generate_batteries_by_energies(energies, u4)
    integrated_perfect = generate_batteries_by_energies(energies, u5)
    strategic_perfect = generate_batteries_by_energies(energies, u6)
    integrated_renewable = generate_batteries_by_energies(energies, u7)
    strategic_renewable = generate_batteries_by_energies(energies, u8)
    price_taker_renewable = generate_batteries_by_energies(energies, u9)

    pairs = generate_batteries_by_usages(0, ['DER None Integrated Hour No-losses Ramp', 'DER None Integrated Hour No-losses Ramp new'])
    compare_summary(start, pairs[0], pairs[1])

    # compare_summary(start, integrated[0], price_taker[0])
    # current = datetime.datetime(2021, 7, 18, 10, 35)
    # compare_dispatchload(integrated[0], price_taker[0], current)


def check():
    filename = 'check2.out'
    with open(filename) as f:
        lines = f.readlines()
        for line in lines:
            if not '(value 0.0)' in line and ('Deficit' in line or 'Surplus' in line):
                print(line)

# command()
check()
