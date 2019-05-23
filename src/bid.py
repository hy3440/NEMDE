import csv
import logging
import pathlib
import pandas as pd
import pickle
import preprocess

log = logging.getLogger(__name__)

# Base directory
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

# Data directory
DATA_DIR = BASE_DIR.joinpath('data')

# Raw directory
RAW_DIR = BASE_DIR.joinpath('raw')


class Unit:
    def __init__(self, duid, region, classification, station, reg_cap, max_cap, max_roc):
        self.duid = duid
        self.region = region
        self.classification = classification
        self.station = station
        # self.reg_cap = float(reg_cap)
        # self.max_cap = float(max_cap)
        # self.max_roc = int(max_roc)

    def set_bid_day_offer(self, row):
        self.daily_energy_constraint = float(row[11])
        self.price_band = [float(price) for price in row[13:23]]

    def set_bid_per_offer(self, row):
        self.max_avail = float(row[11])
        self.roc_up = int(row[13])
        self.roc_down = int(row[14])
        self.band_avail = [int(avail) for avail in row[19:29]]


class Generator(Unit):
    pass


class Load(Unit):
    pass


def save_generators_and_loads():
    logging.info('Save generators and loads.')
    all_generators = {}
    all_loads = {}
    generators_file = RAW_DIR.joinpath('GENERATORS/NEM Registration and Exemption List.xls')
    with pd.ExcelFile(generators_file) as xls:
        df = pd.read_excel(xls, 'Generators and Scheduled Loads')
        for index, row in df.iterrows():
            if row['DUID'] != '-':
                if row['Dispatch Type'] == 'Generator':
                    generator = Generator(row['DUID'], row['Region'], row['Classification'], row['Station Name'], row['Reg Cap (MW)'], row['Max Cap (MW)'], row['Max ROC/Min'])
                    if generator.duid not in all_generators:
                        all_generators[generator.duid] = generator
                else:
                    load = Load(row['DUID'], row['Region'], row['Classification'], row['Station Name'], row['Reg Cap (MW)'], row['Max Cap (MW)'], row['Max ROC/Min'])
                    if load.duid not in all_loads:
                        all_loads[load.duid] = load
    with DATA_DIR.joinpath('generators.pkl').open(mode='wb') as f:
        pickle.dump(all_generators, f)
    with DATA_DIR.joinpath('loads.pkl').open(mode='wb') as f:
        pickle.dump(all_loads, f)


def extract_generators():
    logging.info('Extract generators.')
    generators_dir = DATA_DIR.joinpath('generators.pkl')
    all_generators = pickle.load(generators_dir.open(mode='rb'))
    return all_generators


def extract_loads():
    logging.info('Extract loads.')
    loads_dir = DATA_DIR.joinpath('loads.pkl')
    all_loads = pickle.load(loads_dir.open(mode='rb'))
    return all_loads


def bid_day_offer(case_date):
    all_generators = extract_generators()
    all_loads = extract_loads()
    logging.info('Get bid day offer.')
    generators = {}
    loads = {}
    reserve_trader = set()
    bids_dir = preprocess.download_bidmove_complete(case_date)
    with bids_dir.open() as csvfile:
        reader = csv.reader(csvfile)
        logging.info('Read bid day offer.')
        for row in reader:
            if row[0] == 'D' and row[2] == 'BIDDAYOFFER_D' and row[6] == 'ENERGY':
                if row[5] in all_generators:
                    generator = all_generators[row[5]]
                    generator.set_bid_day_offer(row)
                    generators[generator.duid] = generator
                elif row[5] in all_loads:
                    load = all_loads[row[5]]
                    load.set_bid_day_offer(row)
                    loads[load.duid] = load
                else:
                    reserve_trader.add(row[5])
        return generators, loads, reserve_trader, bids_dir


def bid_per_offer(generators, loads, bids_dir, interval_datatime):
    logging.info('Get bid per offer.')
    with bids_dir.open() as csvfile:
        reader = csv.reader(csvfile)
        logging.info('Read bid per offer.')
        for row in reader:
            if row[0] == 'D' and row[2] == 'BIDPEROFFER_D' and row[6] == 'ENERGY' and row[31] == interval_datatime:
                if row[5] in generators:
                    generators[row[5]].set_bid_per_offer(row)
                elif row[5] in loads:
                    loads[row[5]].set_bid_per_offer(row)


def add_scada_value(generators, loads, case_datetime):
    scada_dir = preprocess.download_dispatch_scada(case_datetime)
    with scada_dir.open() as csvfile:
        reader = csv.reader(csvfile)
        logging.info('Read bid day offer.')
        for row in reader:
            if row[0] == 'D':
                if row[5] in generators:
                    generators[row[5]].scada_value = float(row[6])
                elif row[5] in loads:
                    loads[row[5]].scada_value = float(row[6])


def main(case_date='20190521', interval_datatime='2019/05/21 04:05:00'):
    save_generators_and_loads()
    # generators, loads, reserve_trader, bids_dir = bid_day_offer(case_date)
    # bid_per_offer(generators, loads, bids_dir, interval_datatime)


if __name__ == '__main__':
    main()
