import csv
import pathlib
import pandas as pd
import pickle

# Base directory
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

# Data directory
DATA_DIR = BASE_DIR.joinpath('data')

# Raw directory
RAW_DIR = BASE_DIR.joinpath('raw')


class Unit:
    def __init__(self, duid, region, classification, reg_cap, max_cap, max_roc, station):
        self.duid = duid
        self.region = region
        self.classification = classification
        self.reg_cap = float(reg_cap)
        self.max_cap = float(max_cap)
        self.max_roc = int(max_roc)
        self.station = station

    def set_bid_day_offer(self, row):
        self.daily_energy_constraint = float(row[11])
        self.price_band = [float(price) for price in row[13:23]]
        # self.price_band_1 = float(row[13])
        # self.price_band_2 = float(row[14])
        # self.price_band_3 = float(row[15])
        # self.price_band_4 = float(row[16])
        # self.price_band_5 = float(row[17])
        # self.price_band_6 = float(row[18])
        # self.price_band_7 = float(row[19])
        # self.price_band_8 = float(row[20])
        # self.price_band_9 = float(row[21])
        # self.price_band_10 = float(row[22])

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
    all_generators = {}
    all_loads = {}
    generators_file = RAW_DIR.joinpath('GENERATORS/NEM Registration and Exemption List.xls')
    with pd.ExcelFile(generators_file) as xls:
        df = pd.read_excel(xls, 'Generators and Scheduled Loads')
        for index, row in df.iterrows():
            if row['DUID'] != '-':
                if row['Dispatch Type'] == 'Generator':
                    generator = Generator(row['DUID'], row['Region'], row['Classification'], row['Reg Cap (MW)'], row['Max Cap (MW)'], row['Max ROC/Min'], row['Station Name'])
                    if generator.duid not in all_generators:
                        all_generators[generator.duid] = generator
                else:
                    load = Load(row['DUID'], row['Region'], row['Classification'], row['Reg Cap (MW)'], row['Max Cap (MW)'], row['Max ROC/Min'], row['Station Name'])
                    if load.duid not in all_loads:
                        all_loads[load.duid] = load
    with DATA_DIR.joinpath('generators.pkl').open(mode='wb') as f:
        pickle.dump(all_generators, f)
    with DATA_DIR.joinpath('loads.pkl').open(mode='wb') as f:
        pickle.dump(all_loads, f)


def extract_generators():
    generators_dir = DATA_DIR.joinpath('generators.pkl')
    all_generators = pickle.load(generators_dir.open(mode='rb'))
    return all_generators


def extract_loads():
    loads_dir = DATA_DIR.joinpath('loads.pkl')
    all_loads = pickle.load(loads_dir.open(mode='rb'))
    return all_loads


def bid_day_offer(all_generators, all_loads):
    init_generators = {}
    init_loads = {}
    reserve_trader= set()
    bids_file = DATA_DIR.joinpath('PUBLIC_BIDMOVE_COMPLETE_20190516_0000000307979321.CSV')
    with bids_file.open() as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row[0] == 'D' and row[2] == 'BIDDAYOFFER_D' and row[6] == 'ENERGY':
                if row[5] in all_generators:
                    generator = all_generators[row[5]]
                    generator.set_bid_day_offer(row)
                    init_generators[generator.duid] = generator
                elif row[5] in all_loads:
                    load = all_loads[row[5]]
                    load.set_bid_day_offer(row)
                    init_loads[load.duid] = load
                else:
                    reserve_trader.add(row[5])
        return init_generators, init_loads, reserve_trader


def bid_per_offer(init_generators, init_loads, interval_datatime):
    generators = {}
    loads = {}
    bids_file = DATA_DIR.joinpath('PUBLIC_BIDMOVE_COMPLETE_20190516_0000000307979321.CSV')
    with bids_file.open() as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row[0] == 'D' and row[2] == 'BIDPEROFFER_D' and row[6] == 'ENERGY' and row[31] == interval_datatime:
                if row[5] in init_generators:
                    generator = init_generators[row[5]]
                    generator.set_bid_per_offer(row)
                    generators[generator.duid] = generator
                elif row[5] in init_loads:
                    load = init_loads[row[5]]
                    load.set_bid_per_offer(row)
                    loads[load.duid] = load
        return generators, loads


def main():
    # save_generators_and_loads()
    all_generators = extract_generators()
    all_loads = extract_loads()
    generators, loads, reserve_trader = bid_day_offer(all_generators, all_loads)
    g, l = bid_per_offer(generators, loads, '2019/05/16 04:05:00')
    print(g)

if __name__ == '__main__':
    main()
