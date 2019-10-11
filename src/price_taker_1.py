import csv
import datetime
import gurobipy
import logging
import math
import pathlib
import preprocess
import xlrd

log = logging.getLogger(__name__)

# Base directory
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

# Data directory
DATA_DIR = BASE_DIR.joinpath('data')

FIVE_MIN = datetime.timedelta(minutes=5)
THIRTY_MIN = datetime.timedelta(minutes=30)

i_r1 = 2  # Number of trading intervals for R1
i_r2 = 2  # Number of trading intervals for R2
n_r1 = i_r1 * 6  # Number of dispatch intervals for R1

bs = 1  # Battery size
soc_min = 0.3  # Minimum SoC
soc_max = 0.8  # Maximum SoC
re = 0.8  # Round trip efficiency
re_root = math.sqrt(re)


class Battery:
    def __init__(self, rrp, raise_reg_rrp, lower_reg_rrp):
        self.rrp = rrp
        self.raise_reg_rrp = raise_reg_rrp
        self.lower_reg_rrp = lower_reg_rrp
    # def __init__(self, tni, generator_mlf, load_mlf, region):
    #     self.tni = tni
    #     self.generator_mlf = generator_mlf
    #     self.load_mlf = load_mlf
    #     self.region = region

    def __str__(self):
        return "{}: {}, {}".format(self.tni, self.load_mlf, self.generator_mlf)


def init_batteries():
    return {'NKUR': Battery('NKUR', 0.9948, 0.9948, 'NSW1'),
            'NSHN': Battery('NSHN', 0.9778, 9964, 'NSW1'),
            'NLTS': Battery('NLTS', 0.9304, 1.0012, 'NSW1'),
            'SSNN': Battery('SSNN', 1.0002, 1.0169, 'SA1')
            }


# def add_marginal_loss_factors():
#     mlf_file = DATA_DIR.joinpath('MLF.xls')
#     if not mlf_file.is_file():
#         preprocess.download_mlf()
#     units = set()
#     loads = {}
#     with xlrd.open_workbook(mlf_file) as xlsx:
#         for sheet_index in range(xlsx.nsheets):
#             sheet = xlsx.sheet_by_index(sheet_index)
#             for row_index in range(sheet.nrows):
#                 if sheet.cell_type(row_index, 6) == 2:
#                     tni = sheet.cell_value(row_index, 4)
#                     if tni in loads:
#                         load_mlf = loads[tni]
#                         generator_mlf = sheet.cell_value(row_index, 5)
#                         battery = Battery(tni, load_mlf, generator_mlf)
#                         units.add(battery)
#                 elif sheet.cell_type(row_index, 4) == 2:
#                     tni = sheet.cell_value(row_index, 2)
#                     if tni in loads:
#                         print(tni)
#                     loads[tni] = sheet.cell_value(row_index, 3)
#     for unit in units:
#         print(unit)


def extract_fcas_price(i, t, rrp, batteries):
    t += FIVE_MIN
    for n in range(6):
        dispatch_dir = preprocess.download_dispatch_summary(t)
        with dispatch_dir.open() as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row[0] == 'D' and row[2] == 'PRICE' and row[6] == 'NSW1':
                    battery = Battery(rrp, float(row[24]), float(row[36]))
                    batteries[i * 6 + n] = battery
                    break
        t += FIVE_MIN


def extract_spot_price(t):
    trading_dir = preprocess.download_trading(t + THIRTY_MIN)
    with trading_dir.open() as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row[0] == 'D' and row[2] == 'PRICE' and row[6] == 'NSW1':
                return float(row[8])

def estimate_revenue():


def estimate_r1_cost():


def estimate_r2_cost():


def calculate_first_stage(model, n_0, i_0, n, i):
    if n == n_0 + n_r1:
        return calculate_second_stage(model, i_0, n, i)
    elif n_0 <= n <= n_0 + n_r1 - 1:
        o1 = estimate_revenue() - estimate_r1_cost()
        o2 = calculate_first_stage(model, n_0, i_0, n + 1, i)
        model.setObjectiveN(o1 + o2, n)
    else:
        return None


def calculate_second_stage(model, i_0, n, i):


if __name__ == '__main__':
    logging.basicConfig(filename='price_taker.log', filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)
    t = datetime.datetime(2019, 7, 3, 4, 0, 0)
    batteries = {}
    for i in range(3):
        rrp = extract_spot_price(t)
        extract_fcas_price(i, t, rrp, batteries)
        t += THIRTY_MIN

    n_0 = 0
    i_0 = 0
    model = gurobipy.Model('price_taker')


