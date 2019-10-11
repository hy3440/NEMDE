import csv
import logging
import pathlib
import pandas as pd
import preprocess
import xlrd

log = logging.getLogger(__name__)


class Bid:
    """Bid class.

    Attributes:
        bid_type (str): Energy or FCAS
        price_band (list): Ten price bands
        max_avail (float): Maximum availability for this BidType in this period
        band_avail (int): Availability at price bands

    """
    def __init__(self, row):
        self.bid_type = row[6]
        # Daily bids
        self.price_band = [float(price) for price in row[13:23]]
        # Period bids
        self.max_avail = 0
        self.band_avail = None


class EnergyBid(Bid):
    """Energy bid.

    Attributes:
        daily_energy_constraint (float): Maximum energy available from Energy Constrained Plant
        minimum_load (int): Minimum MW load fast START plant
        t1 (int): Time to synchronise in minutes
        t2 (int): Time to synchronise in minutes
        t3 (int): Time to synchronise in minutes
        t4 (int): Time to synchronise in minutes
        fixed_load (float): Fixed unit output MW
        roc_up (int): MW/min for raise
        roc_down (int): MW/min for lower

    """
    def __init__(self, row):
        super().__init__(row)
        # Daily bids
        self.daily_energy_constraint = float(row[11])
        self.minimum_load = int(row[23])
        self.t1 = int(row[24])
        self.t2 = int(row[25])
        self.t3 = int(row[26])
        self.t4 = int(row[27])
        # Period bids
        self.fixed_load = None
        self.roc_up = None
        self.roc_down = None


class FcasBid(Bid):
    """FCAS bid.

    Attributes:
        enablement_min (int): Minimum Energy Output (MW) at which this ancillary service becomes available
        enablement_max (int): Maximum Energy Output (MW) at which this ancillary service becomes available
        low_breakpoint (int): Minimum Energy Output (MW) at which the unit can provide the full availability (MAXAVAIL) for this ancillary service
        high_breakpoint (int): Maximum Energy Output (MW) at which the unit can provide the full availability (MAXAVAIL) for this ancillary service

    """
    def __init__(self, row):
        super().__init__(row)
        self.value = 0
        self.offers = None
        self.upper_slope_coeff = None
        self.lower_slope_coeff = None
        self.enablement_status = 0
        # Period bids
        self.enablement_min = None
        self.enablement_max = None
        self.low_breakpoint = None
        self.high_breakpoint = None


class Unit:
    """Unit class.

    Attributes:
        duid (str): Dispatchable unit identifier
        energy (EnergyBid): Energy bid
        fcas_bids (dict): A dictionary of FCAS bids

        connection_point_id (str): Unique ID of a connection point
        volt_level (str): Voltage level
        registered_capacity (int): Registered capacity for normal operations
        agc_capability (char): AGC capability flag
        dispatch_type (str): Identifies LOAD or GENERATOR
        max_capacity (int): Maximum Capacity as used for bid validation
        start_type (str): Identify unit as Fast, Slow or Non Dispatched
        normally_on_flag (char): For a dispatchable load indicates that the load is normally on or off.
        intermittent_flag (char): Indicate whether a unit is intermittent (e.g. a wind farm)
        semischedule_flag (char): Indicates if the DUID is a Semi-Scheduled Unit
        max_rate_of_change_up (int): Maximum ramp up rate for Unit (Mw/min)
        max_rate_of_change_down (int): Maximum ramp down rate for Unit (Mw/min)

        region_id (str): Region identifier that unit is in
        station_id (str): Station that unit is in
        transmission_loss_factor (float): The transmission level loss factor for currently assigned connection point.
        distribution_loss_factor (float): The distribution loss factor to the currently assigned connection point
        minimum_energy_price (float): Floored Offer/Bid Energy Price adjusted for TLF, DLF and MPF
        maximum_energy_price (float): Capped Offer/Bid Energy Price adjusted for TLF, DLF and VoLL
        schedule_type (str): Scheduled status of the unit: SCHEDULED, NON-SCHEDULED or SEMI-SCHEDULED
        min_ramp_rate_up (int): MW/Min. Calculated Minimum Ramp Rate Up value accepted for Energy Offers or Bids with explanation
        min_ramp_rate_down (int): MW/Min. Calculated Minimum Ramp Rate Down value accepted for Energy Offers or Bids with explanation
        max_ramp_rate_up (int): Maximum ramp up rate for Unit (Mw/min) - from DUDetail table
        max_ramp_rate_down (int): Maximum ramp down rate for Unit (Mw/min) - from DUDetail table

        forecast (float): Forecast 50% POE MW value for this interval_DateTime. Used in Dispatch.
        priority (int): Unsuppressed forecasts with higher priority values are used in Dispatch in preference to unsuppressed forecasts with lower priority values

        total_cleared (float): Target MW for end of period
        offers (list): A list of dispatch target at price bands
        total_cleared_record (float): AEMO record for total cleared
        initial_mw (float): AEMO actual initial MW at START of period
        marginal_value (float): Marginal $ value for energy
        marginal_value_record (float): AEMO record for marginal value

        scada_value (float): AEMO actual generation SCADA value

    """
    def __init__(self, duid):
        self.duid = duid
        self.energy = None
        self.raise_reg_fcas = None
        self.lower_reg_fcas = None
        self.raise_con_fcas = {}
        self.lower_con_fcas = {}
        # DU detail
        self.connection_point_id = None
        self.volt_level = None
        self.registered_capacity = None
        self.agc_capability = None
        self.dispatch_type = None
        self.max_capacity = None
        self.start_type = None
        self.normally_on_flag = None
        self.intermittent_flag = None
        self.semischedule_flag = None
        self.max_rate_of_change_up = None
        self.max_rate_of_change_down = None
        # DU detail summary
        self.region_id = None
        self.station_id = None
        self.transmission_loss_factor = None
        self.distribution_loss_factor = None
        self.minimum_energy_price = None
        self.maximum_energy_price = None
        self.schedule_type = None
        self.min_ramp_rate_up = None
        self.min_ramp_rate_down = None
        self.max_ramp_rate_up = None
        self.max_ramp_rate_down = None
        # # Registration
        # self.dispatch_type = None
        # self.region = None
        # self.classification = None
        # self.station = None
        # self.source = None
        # self.reg_cap = None
        # self.max_cap = None
        # self.max_roc = None
        # # MLF
        # self.connection_point_id = None
        # self.tni = None
        # self.mlf = None
        # UIGF
        self.forecast = None
        self.priority = 0
        # Dispatch
        self.total_cleared = 0.0
        self.offers = None
        self.lower5min = None
        self.lower60sec = None
        self.lower6sec = None
        self.raise5min = None
        self.raise60sec = None
        self.raise6sec = None
        self.marginal_value = None
        self.lowerreg = None
        self.raisereg = None
        self.fcas_bids = {}
        # Dispatch load
        self.agc_status = None
        self.initial_mw = None
        self.total_cleared_record = None
        self.ramp_down_rate = None
        self.ramp_up_rate = None
        self.lower5min_record = None
        self.lower60sec_record = None
        self.lower6sec_record = None
        self.raise5min_record = None
        self.raise60sec_record = None
        self.raise6sec_record = None
        self.marginal_value_record = None
        self.lowerreg_record = None
        self.raisereg_record = None
        self.raisereg_availability = None
        self.raisereg_enablement_max = None
        self.raisereg_enablement_min = None
        self.lowerreg_availability = None
        self.lowerreg_enablement_max = None
        self.lowerreg_enablement_min = None
        # SCADA
        self.scada_value = None


# class Generator(Unit):
#     def __init__(self, duid, region, classification, station, reg_cap, max_cap, max_roc, source=None):
#         super().__init__(duid)
#         self.forecast = None
#         self.priority = 0
#
#
# class Load(Unit):
#     pass


def add_unit_bids(units, t):
    """ Add unit bids.
    Args:
        units (dict): a dictionary of units
        t (datetime.datetime): interval datetime

    Returns:
        None
    """
    bids_dir = preprocess.download_bidmove_complete(t)
    interval_datetime = preprocess.get_interval_datetime(t)
    with bids_dir.open() as f:
        reader = csv.reader(f)
        logging.info('Read bid day offer.')
        for row in reader:
            if row[0] == 'D' and row[2] == 'BIDDAYOFFER_D':
                duid = row[5]
                if duid not in units:
                    units[duid] = Unit(duid)
                unit = units[duid]
                if row[6] == 'ENERGY':
                    unit.energy = EnergyBid(row)
                else:
                    unit.fcas_bids[row[6]] = FcasBid(row)
                    # if row[6] == 'RAISEREG':
                    #     unit.raise_reg_fcas = Fcas(row)
                    # elif row[6] == 'LOWERREG':
                    #     unit.lower_reg_fcas = Fcas(row)
                    # elif row[6][:5] == 'RAISE':
                    #     unit.raise_con_fcas[row[6]] = Fcas(row)
                    # elif row[6][:5] == 'LOWER':
                    #     unit.lower_con_fcas[row[6]] = Fcas(row)

            elif row[0] == 'D' and row[2] == 'BIDPEROFFER_D' and row[31] == interval_datetime:
                if row[6] == 'ENERGY':
                    energy = units[row[5]].energy
                    energy.max_avail = float(row[11])
                    energy.fixed_load = float(row[12])
                    energy.roc_up = int(row[13])
                    energy.roc_down = int(row[14])
                    energy.band_avail = [int(avail) for avail in row[19:29]]
                else:
                    # if row[6] == 'RAISEREG':
                    #     bid = units[row[5]].raise_reg_fcas
                    # elif row[6] == 'LOWERREG':
                    #     bid = units[row[5]].lower_reg_fcas
                    # elif row[6][:5] == 'RAISE':
                    #     bid = units[row[5]].raise_con_fcas[row[6]]
                    # elif row[6][:5] == 'LOWER':
                    #     bid = units[row[5]].lower_con_fcas[row[6]]
                    # else:
                    #     logging.warning('{} {} bid warning'.format(row[5], row[6]))
                    bid = units[row[5]].fcas_bids[row[6]]
                    bid.max_avail = float(row[11])
                    bid.enablement_min = int(row[15])
                    bid.enablement_max = int(row[16])
                    bid.low_breakpoint = int(row[17])
                    bid.high_breakpoint = int(row[18])
                    bid.band_avail = [int(avail) for avail in row[19:29]]


def add_du_detail(units, t):
    """ Add DU detail.

    Args:
        units (dict): a dictionary of units
        t (datetime.datetime): interval datetime

    Returns:
        None
    """
    dd_dir = preprocess.download_dvd_data('DUDETAIL')
    logging.info('Read du detail.')
    with dd_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and preprocess.extract_datetime(row[4]) <= t:
                unit = units.get(row[5])
                if unit:
                    unit.connection_point_id = row[7]
                    unit.volt_level = row[8]
                    unit.registered_capacity = int(row[9])
                    unit.agc_capability = row[10]
                    unit.dispatch_type = row[11]
                    unit.max_capacity = int(row[12])
                    unit.start_type = row[13]
                    unit.normally_on_flag = row[14]
                    unit.intermittent_flag = row[20]
                    unit.semischedule_flag = row[21]
                    unit.max_rate_of_change_up = int(row[22]) if row[22] else None
                    unit.max_rate_of_change_down = int(row[23]) if row[23] else None


def add_du_detail_summary(units, t):
    """ Add DU detail summary.

    Args:
        units (dict): a dictionary of units
        t (datetime.datetime): interval datetime

    Returns:
        None
    """
    dds_dir = preprocess.download_dvd_data('DUDETAILSUMMARY')
    logging.info('Read du detail summary.')
    with dds_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and preprocess.extract_datetime(row[5]) <= t < preprocess.extract_datetime(row[6]):
                unit = units.get(row[4])
                if unit:
                    unit.region_id = row[9]
                    unit.station_id = row[10]
                    unit.transmission_loss_factor = float(row[13])
                    unit.distribution_loss_factor = float(row[15])
                    unit.minimum_energy_price = float(row[16])
                    unit.maximum_energy_price = float(row[17])
                    unit.schedule_type = row[18]
                    unit.min_ramp_rate_up = int(row[19]) if row[19] else None
                    unit.min_ramp_rate_down = int(row[20]) if row[20] else None
                    unit.max_ramp_rate_up = int(row[21]) if row[21] else None
                    unit.max_ramp_rate_down = int(row[22]) if row[22] else None


def add_registration_information(units):
    """ Add registration information.

    Args:
        units (dict): a dictionary of units

    Returns:
        None
    """
    generators_file = preprocess.download_registration()
    logging.info('Read registration information.')
    with pd.ExcelFile(generators_file) as xls:
        df = pd.read_excel(xls, 'Generators and Scheduled Loads')
        for index, row in df.iterrows():
            if row['DUID'] in units:
                unit = units[row['DUID']]
                unit.dispatch_type = row['Dispatch Type']
                unit.region = row['Region']
                unit.classification = row['Classification']
                unit.station = row['Station Name']
                unit.source = row['Fuel Source - Primary']
                # if row['Reg Cap (MW)'] != '-':
                #     unit.reg_cap = float(row['Reg Cap (MW)'])
                if row['Max Cap (MW)'] != '-':
                    unit.max_cap = float(row['Max Cap (MW)'])
                # if row['Max ROC/Min'] != '-':
                #     unit.max_roc = float(row['Max ROC/Min'])
        df = pd.read_excel(xls, 'Ancillary Services')
        for index, row in df.iterrows():
            if row['DUID'] in units:
                unit = units[row['DUID']]
                unit.region = row['Region']


def add_marginal_loss_factors(units):
    """ Add marginal loss factors.

    Args:
        units (dict): a dictionary of units

    Returns:
        None
    """
    mlf_file = preprocess.download_mlf()
    with xlrd.open_workbook(mlf_file) as f:
        for sheet_index in range(f.nsheets):
            sheet = f.sheet_by_index(sheet_index)
            for row_index in range(sheet.nrows):
                if sheet.cell_type(row_index, 6) == 2:
                    duid = sheet.cell_value(row_index, 2)
                    if duid in units:
                        unit = units[duid]
                        unit.connection_point_id = sheet.cell_value(row_index, 3)
                        unit.tni = sheet.cell_value(row_index, 4)
                        # 2018-19 MLF applicable from 01 July 2018 to 30 June 2019
                        # generator.mlf = sheet.cell_value(row_index, 6)
                        # 2019-20 MLF applicable from 01 July 2019 to 30 June 2020
                        unit.mlf = sheet.cell_value(row_index, 5)


def add_intermittent_forecast(units, t):
    """ Add intermittent forecast.

    Args:
        units (dict): a dictionary of units
        t (datetime.datetime): interval datetime

    Returns:
        None
    """
    intermittent_dir = preprocess.download_intermittent(t)
    interval_datetime = preprocess.get_interval_datetime(t)
    with intermittent_dir.open() as f:
        reader = csv.reader(f)
        logging.info('Read intermittent forecast.')
        for row in reader:
            if row[0] == 'D' and row[2] == 'INTERMITTENT_DS_PRED' and row[4] == interval_datetime:
                generator = units[row[5]]
                priority = int(row[7])
                if generator.priority <= priority:
                    generator.priority = priority
                    generator.forecast = float(row[12])
            elif row[0] == 'D' and row[2] == 'INTERMITTENT_FORECAST_TRK' and row[4] == interval_datetime:
                priority = units[row[5]].priority
                if priority != int(row[7]):
                    logging.error('{} forecast priority record is {} but we extract is {}'.format(row[5], row[7], priority))


def add_dispatch_record(units, t):
    """ Add dispatch record.

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): interval datetime

    Returns:
        None
    """
    record_dir = preprocess.download_next_day_dispatch(t)
    interval_datetime = preprocess.get_interval_datetime(t)
    with record_dir.open() as f:
        reader = csv.reader(f)
        logging.info('Read next day dispatch.')
        for row in reader:
            if row[0] == 'D' and row[2] == 'UNIT_SOLUTION' and row[4] == interval_datetime:
                duid = row[6]
                if duid in units:
                    unit = units[duid]
                    unit.agc_status = int(row[12])
                    unit.initial_mw = float(row[13])
                    unit.total_cleared_record = float(row[14])
                    unit.ramp_down_rate = float(row[15])
                    unit.ramp_up_rate = float(row[16])
                    unit.lower5min_record = float(row[17])
                    unit.lower60sec_record = float(row[18])
                    unit.lower6sec_record = float(row[19])
                    unit.raise5min_record = float(row[20])
                    unit.raise60sec_record = float(row[21])
                    unit.raise6sec_record = float(row[22])
                    # generator.marginal_value_record = float(row[28])
                    unit.lowerreg_record = float(row[34])
                    unit.raisereg_record = float(row[35])
                    unit.raisereg_availability = float(row[45])
                    unit.raisereg_enablement_max = float(row[46])
                    unit.raisereg_enablement_min = float(row[47])
                    unit.lowerreg_availability = float(row[48])
                    unit.lowerreg_enablement_max = float(row[49])
                    unit.lowerreg_enablement_min = float(row[50])


def add_scada_value(units, t):
    """ Add SCADA values.

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): interval datetime

    Returns:
        None
    """
    scada_dir = preprocess.download_dispatch_scada(t)
    with scada_dir.open() as f:
        reader = csv.reader(f)
        logging.info('Read SCADA value.')
        for row in reader:
            if row[0] == 'D':
                if row[5] in units:
                    units[row[5]].scada_value = float(row[6])


def add_reserve_trader(units):
    """ Manually add reserve trader information.

    Args:
        units (dict): the dictionary of units

    Returns:
        None
    """
    for i in range(1, 7):
        duid = 'RT_NSW{}'.format(i)
        if duid in units:
            units[duid].region = 'NSW1'
            units[duid].dispatch_type = 'Generator'
        duid = 'DG_NSW{}'.format(i)
        if duid in units:
            units[duid].region = 'NSW1'
            units[duid].dispatch_type = 'Generator'

    for i in range(1, 13):
        duid = 'RT_VIC{}'.format(i)
        if duid in units:
            units[duid].region = 'VIC1'
            units[duid].dispatch_type = 'Generator'
        duid = 'DG_VIC{}'.format(i)
        if duid in units:
            units[duid].region = 'VIC1'
            units[duid].dispatch_type = 'Generator'

    for i in range(1, 7):
        duid = 'RT_SA{}'.format(i)
        if duid in units:
            units[duid].region = 'SA1'
            units[duid].dispatch_type = 'Generator'
        duid = 'DG_SA{}'.format(i)
        if duid in units:
            units[duid].region = 'SA1'
            units[duid].dispatch_type = 'Generator'

    for i in range(1, 2):
        duid = 'RT_TAS{}'.format(i)
        if duid in units:
            units[duid].region = 'TAS1'
            units[duid].dispatch_type = 'Generator'
        duid = 'DG_TAS{}'.format(i)
        if duid in units:
            units[duid].region = 'TAS1'
            units[duid].dispatch_type = 'Generator'

    for i in range(1, 2):
        duid = 'RT_QLD{}'.format(i)
        if duid in units:
            units[duid].region = 'QLD1'
            units[duid].dispatch_type = 'Generator'
        duid = 'DG_QLD{}'.format(i)
        if duid in units:
            units[duid].region = 'QLD1'
            units[duid].dispatch_type = 'Generator'


def get_units(t):
    """Get units.

    Args:
        t (datetime): Interval datetime

    Returns:
        dict: A dictionary of units

    """
    units = {}
    add_unit_bids(units, t)
    # add_registration_information(units)
    # add_marginal_loss_factors(units)
    add_du_detail(units, t)
    add_du_detail_summary(units, t)
    add_intermittent_forecast(units, t)
    add_dispatch_record(units, t)
    # add_reserve_trader(units)
    return units
