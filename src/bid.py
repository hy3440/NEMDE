import csv
import logging
import pathlib
import pandas as pd
import pickle
import preprocess
import xlrd

log = logging.getLogger(__name__)

# Base directory
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

# Data directory
DATA_DIR = BASE_DIR.joinpath('data')

# Raw directory
RAW_DIR = BASE_DIR.joinpath('raw')


class Unit:
    """Unit class.

    Attributes:
        duid (str): Dispatchable unit identifier
        region (str): Region ID the unit belongs to
        classification (str): Scheduled, Semi-Scheduled or Non-Scheduled
        station (str): Station name
        connection_point_id (str): Connection point ID
        tni (str): Transimission Node Identifier
        mlf (float): Marginal Loss Factor
        total_cleared (float): Target MW for end of period
        total_cleared_record (float): AEMO record for total cleared
        initial_mw (float): AEMO actual initial MW at start of period
        scada_value (float): AEMO actual generation SCADA value
        marginal_value (float): Marginal $ value for energy
        marginal_value_record (float): AEMO record for marginal value

    """
    def __init__(self, duid, region, classification, station, reg_cap, max_cap, max_roc, source=None, source_descriptor=None, tech=None, tech_descriptor=None):
        self.duid = duid
        self.region = region
        self.classification = classification
        self.station = station
        self.source = source
        self.source_descriptor = source_descriptor
        self.tech = tech
        self.tech_descriptor = tech_descriptor
        # self.reg_cap = float(reg_cap)
        # self.max_cap = float(max_cap)
        # self.max_roc = int(max_roc)
        self.connection_point_id = None
        self.tni = None
        self.mlf = None
        self.total_cleared = None
        self.total_cleared_record = None
        self.initial_mw = None
        self.scada_value = None
        self.marginal_value = None
        self.marginal_value_record = None

    def set_bid_day_offer(self, row):
        self.daily_energy_constraint = float(row[11])
        self.price_band = [float(price) for price in row[13:23]]

    def set_bid_per_offer(self, row):
        self.max_avail = float(row[11])
        self.roc_up = int(row[13])
        self.roc_down = int(row[14])
        self.band_avail = [int(avail) for avail in row[19:29]]


class Generator(Unit):
    def __init__(self, duid, region, classification, station, reg_cap, max_cap, max_roc, source=None, source_descriptor=None, tech=None, tech_descriptor=None):
        super().__init__(duid, region, classification, station, reg_cap, max_cap, max_roc, source, source_descriptor, tech, tech_descriptor)
        self.forecast = None
        self.priority = 0


class Load(Unit):
    pass


def add_marginal_loss_factors(all_generators, all_loads):
    mlf_file = RAW_DIR.joinpath('LOSS_FACTORS/2019-20 MLF Applicable from 01 July 2019 to 30 June 2020.xlsx')
    with xlrd.open_workbook(mlf_file) as xlsx:
        for sheet_index in range(xlsx.nsheets):
            sheet = xlsx.sheet_by_index(sheet_index)
            for row_index in range(sheet.nrows):
                if sheet.cell_type(row_index, 6) == 2:
                    duid = sheet.cell_value(row_index, 2)
                    if duid in all_generators:
                        generator = all_generators[duid]
                        generator.connection_point_id = sheet.cell_value(row_index, 3)
                        generator.tni = sheet.cell_value(row_index, 4)
                        generator.mlf = sheet.cell_value(row_index, 6)
                    elif duid in all_loads:
                        load = all_loads[duid]
                        load.connection_point_id = sheet.cell_value(row_index, 3)
                        load.tni = sheet.cell_value(row_index, 4)
                        load.mlf = sheet.cell_value(row_index, 6)
                    # else:
                    #     print(duid)


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
                    generator = Generator(row['DUID'], row['Region'], row['Classification'], row['Station Name'], row['Reg Cap (MW)'], row['Max Cap (MW)'], row['Max ROC/Min'], row['Fuel Source - Primary'], row['Fuel Source - Descriptor'], row['Technology Type - Primary'], row['Technology Type - Descriptor'])
                    if generator.duid not in all_generators:
                        all_generators[generator.duid] = generator
                else:
                    load = Load(row['DUID'], row['Region'], row['Classification'], row['Station Name'], row['Reg Cap (MW)'], row['Max Cap (MW)'], row['Max ROC/Min'])
                    if load.duid not in all_loads:
                        all_loads[load.duid] = load
    add_marginal_loss_factors(all_generators, all_loads)
    with DATA_DIR.joinpath('generators.pkl').open(mode='wb') as f:
        pickle.dump(all_generators, f)
    with DATA_DIR.joinpath('loads.pkl').open(mode='wb') as f:
        pickle.dump(all_loads, f)


def extract_generators_and_loads():
    generators_dir = DATA_DIR.joinpath('generators.pkl')
    loads_dir = DATA_DIR.joinpath('loads.pkl')
    if not generators_dir.is_file() or not loads_dir.is_file():
        save_generators_and_loads()
    logging.info('Extract generators and loads.')
    generators = pickle.load(generators_dir.open(mode='rb'))
    loads = pickle.load(loads_dir.open(mode='rb'))
    return generators, loads


def bid_day_offer(case_date):
    all_generators, all_loads = extract_generators_and_loads()
    logging.info('Get bid day offer.')
    generators = {}
    loads = {}
    reserve_trader = set()
    bids_dir = DATA_DIR.joinpath('PUBLIC_BIDMOVE_COMPLETE_{}.csv'.format(case_date))
    if not bids_dir.is_file():
        preprocess.download_bidmove_complete(case_date)
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
        return generators, loads, reserve_trader


def bid_per_offer(generators, loads, case_date, interval_datatime):
    logging.info('Get bid per offer.')
    bids_dir = DATA_DIR.joinpath('PUBLIC_BIDMOVE_COMPLETE_{}.csv'.format(case_date))
    if not bids_dir.is_file():
        preprocess.download_bidmove_complete(case_date)
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
    scada_dir = DATA_DIR.joinpath('PUBLIC_DISPATCHSCADA_{}.csv'.format(case_datetime))
    if not scada_dir.is_file():
        preprocess.download_dispatch_scada(case_datetime)
    with scada_dir.open() as csvfile:
        reader = csv.reader(csvfile)
        logging.info('Read bid day offer.')
        for row in reader:
            if row[0] == 'D':
                if row[5] in generators:
                    generators[row[5]].scada_value = float(row[6])
                elif row[5] in loads:
                    loads[row[5]].scada_value = float(row[6])


def add_intermittent_forecast(generators, report_date, interval_datetime):
    intermittent_dir = DATA_DIR.joinpath('PUBLIC_NEXT_DAY_INTERMITTENT_DS_{}.csv'.format(report_date))
    if not intermittent_dir.is_file():
        preprocess.download_intermittent(report_date)
    with intermittent_dir.open() as csvfile:
        reader = csv.reader(csvfile)
        logging.info('Read intermittent forecast.')
        for row in reader:
            if row[0] == 'D' and row[2] == 'INTERMITTENT_DS_PRED' and row[4] == interval_datetime:
                generator = generators[row[5]]
                priority = int(row[7])
                if generator.priority <= priority:
                    generator.priority = priority
                    generator.forecast = float(row[12])
            elif row[0] == 'D' and row[2] == 'INTERMITTENT_FORECAST_TRK' and row[4] == interval_datetime:
                priority = generators[row[5]].priority
                if priority != int(row[7]):
                    logging.error('{} forecast priority record is but we extract is {}'.format(row[5], row[7], priority))
    return intermittent_dir


def add_dispatch_record(generators, loads, case_date, interval_datetime):
    record_dir = DATA_DIR.joinpath('PUBLIC_NEXT_DAY_DISPATCH_{}.csv'.format(case_date))
    if not record_dir.is_file():
        preprocess.download_next_day_dispatch(case_date)
    with record_dir.open() as csvfile:
        reader = csv.reader(csvfile)
        logging.info('Read next day dispatch.')
        for row in reader:
            if row[0] == 'D' and row[2] == 'UNIT_SOLUTION' and row[4] == interval_datetime:
                duid = row[6]
                if duid in generators:
                    generator = generators[duid]
                    generator.initial_mw = float(row[13])
                    generator.total_cleared_record = float(row[14])
                    # generator.marginal_value_record = float(row[28])
                elif duid in loads:
                    load = loads[duid]
                    load.initial_mw = float(row[13])
                    load.total_cleared_record = float(row[14])
                    # load.marginal_value_record = float(row[28])