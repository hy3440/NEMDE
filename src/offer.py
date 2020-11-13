import csv
import logging
import pathlib
import pandas as pd
import preprocess
import xlrd

log = logging.getLogger(__name__)
intervention = '0'


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
        value (float): Dispatch value
        offers (list): Bid offer
        upper_slope_coeff (float)
        lower_slop_coeff (float)
        enablement_status (int): 1 if the FCAS service is enabled for the unit, otherwise 0
        enablement_min (int): Minimum Energy Output (MW) at which this ancillary service becomes available
        enablement_max (int): Maximum Energy Output (MW) at which this ancillary service becomes available
        low_breakpoint (int): Minimum Energy Output (MW) at which the unit can provide the full availability (MAXAVAIL) for this ancillary service
        high_breakpoint (int): Maximum Energy Output (MW) at which the unit can provide the full availability (MAXAVAIL) for this ancillary service
        flag (int): A flag exists for each ancillary service type such that a unit trapped or stranded in one or more service type can be immediately identified
    """
    def __init__(self, row):
        super().__init__(row)
        self.value = 0.0
        self.offers = None
        self.upper_slope_coeff = None
        self.lower_slope_coeff = None
        self.enablement_status = 0
        # Period bids
        self.enablement_min = None
        self.enablement_max = None
        self.low_breakpoint = None
        self.high_breakpoint = None
        # Dispatch lod
        self.flag = 0


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
        # self.region_id = None
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
        self.origin = None
        self.forecast_priority = None
        self.offer_datetime = None
        self.forecast_poe50 = None
        # Dispatch
        self.energy = None
        self.total_cleared = 0.0
        # self.lower5min = None
        # self.lower60sec = None
        # self.lower6sec = None
        # self.raise5min = None
        # self.raise60sec = None
        # self.raise6sec = None
        self.marginal_value = None
        self.lowerreg = None
        self.raisereg = None
        self.fcas_bids = {}
        # self.raise_reg_fcas = None
        # self.lower_reg_fcas = None
        # self.raise_con_fcas = {}
        # self.lower_con_fcas = {}
        # Dispatch load
        self.agc_status = None
        self.initial_mw = None
        self.total_cleared_record = None
        self.ramp_down_rate = None
        self.ramp_up_rate = None
        self.target_record = {}
        # self.lower5min_record = None
        # self.lower60sec_record = None
        # self.lower6sec_record = None
        # self.raise5min_record = None
        # self.raise60sec_record = None
        # self.raise6sec_record = None
        self.marginal_value_record = {}
        self.violation_degree_record = {}
        # self.lowerreg_record = None
        # self.raisereg_record = None
        self.availability = None
        self.flags = {}
        self.raisereg_availability = None
        self.raisereg_enablement_max = None
        self.raisereg_enablement_min = None
        self.lowerreg_availability = None
        self.lowerreg_enablement_max = None
        self.lowerreg_enablement_min = None
        self.actual_availability_record = {}
        # SCADA
        self.scada_value = None


# class Generator(Unit):
#     def __init__(self, duid, region_id, classification, station, reg_cap, max_cap, max_roc, source=None):
#         super().__init__(duid)
#         self.forecast = None
#         self.priority = 0
#
#
# class Load(Unit):
#     pass


def add_unit_bids(units, t, fcas_flag):
    """ Add unit bids.
    Args:
        units (dict): a dictionary of units
        t (datetime.datetime): i datetime

    Returns:
        None
    """
    bids_dir = preprocess.download_bidmove_complete(t)
    interval_datetime = preprocess.get_interval_datetime(t)
    with bids_dir.open() as f:
        reader = csv.reader(f)
        # logging.info('Read bid day offer.')
        for row in reader:
            if row[0] == 'D' and row[2] == 'BIDDAYOFFER_D':
                duid = row[5]
                unit = units.get(duid)
                if not unit:
                    unit = Unit(duid)
                    units[duid] = unit
                if row[6] == 'ENERGY':
                    unit.energy = EnergyBid(row)
                elif fcas_flag:
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
                elif fcas_flag:
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


def add_du_detail(units, t, connection_points={}):
    """ Add DU detail.

    Args:
        units (dict): a dictionary of units
        t (datetime.datetime): i datetime

    Returns:
        None
    """
    dd_dir = preprocess.download_dvd_data('DUDETAIL', t)
    # logging.info('Read du detail.')
    with dd_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and preprocess.extract_datetime(row[4]) <= t:
                unit = units.get(row[5])
                if unit:
                    if row[7] in connection_points and row[5] != connection_points[row[7]]:
                        log.error('Connection point ID {} has more than one unit.'.format(row[7]))
                    connection_points[row[7]] = row[5]
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
    return connection_points


def add_du_detail_summary(units, t):
    """ Add DU detail summary.

    Args:
        units (dict): a dictionary of units
        t (datetime.datetime): i datetime

    Returns:
        None
    """
    dds_dir = preprocess.download_dvd_data('DUDETAILSUMMARY', t)
    # logging.info('Read du detail summary.')
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
    # logging.info('Read registration information.')
    with pd.ExcelFile(generators_file) as xls:
        df = pd.read_excel(xls, 'Generators and Scheduled Loads')
        for index, row in df.iterrows():
            if row['DUID'] in units:
                unit = units[row['DUID']]
                unit.dispatch_type = row['Dispatch Type']
                unit.region_id = row['Region']
                unit.classification = row['Classification']
                unit.station = row['Station Name']
                unit.source = row['Fuel Source - Primary']
                # if row['Reg Cap (MW)'] != '-':
                #     unit.reg_cap = float(row['Reg Cap (MW)'])
                if row['Max Cap (MW)'] != '-':
                    unit.max_capacity = float(row['Max Cap (MW)'])
                # if row['Max ROC/Min'] != '-':
                #     unit.max_roc = float(row['Max ROC/Min'])
        df = pd.read_excel(xls, 'Ancillary Services')
        for index, row in df.iterrows():
            if row['DUID'] in units:
                unit = units[row['DUID']]
                unit.region_id = row['Region']


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
                        unit.transmission_loss_factor = sheet.cell_value(row_index, 5)


def add_intermittent_forecast(units, t):
    """ Add intermittent forecast.

    Args:
        units (dict): a dictionary of units
        t (datetime.datetime): i datetime

    Returns:
        None
    """
    intermittent_dir = preprocess.download_intermittent(t)
    interval_datetime = preprocess.get_interval_datetime(t)
    with intermittent_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'INTERMITTENT_FORECAST_TRK' and row[4] == interval_datetime:  # 4: SETTLEMENTDATE
                unit = units[row[5]]  # 5: DUID
                unit.origin = row[6]
                unit.forecast_priority = row[7]
                unit.offer_datetime = row[8]
    with intermittent_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'INTERMITTENT_DS_PRED' and row[4] == interval_datetime:
                unit = units[row[5]]
                if unit.origin == row[6] and unit.forecast_priority == row[7] and unit.offer_datetime == row[8]:
                    unit.forecast_poe50 = float(row[12])


def add_dispatchload_record(units, t, fcas_flag):
    """ Add AEMO dispatch record.

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): i datetime

    Returns:
        None
    """
    record_dir = preprocess.download_next_day_dispatch(t)
    interval_datetime = preprocess.get_interval_datetime(t)
    with record_dir.open() as f:
        reader = csv.reader(f)
        # logging.info('Read next day dispatch.')
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
                    unit.marginal_value_record['ENERGY'] = float(row[28]) if row[28] else None
                    unit.violation_degree_record['ENERGY'] = float(row[32]) if row[32] else None
                    unit.availability = float(row[36])
                    if fcas_flag:
                        # unit.lower5min_record = float(row[17])
                        # unit.lower60sec_record = float(row[18])
                        # unit.lower6sec_record = float(row[19])
                        # unit.raise5min_record = float(row[20])
                        # unit.raise60sec_record = float(row[21])
                        # unit.raise6sec_record = float(row[22])
                        # unit.lowerreg_record = float(row[34])
                        # unit.raisereg_record = float(row[35])
                        unit.target_record['LOWER5MIN'] = float(row[17])
                        unit.target_record['LOWER60SEC'] = float(row[18])
                        unit.target_record['LOWER6SEC'] = float(row[19])
                        unit.target_record['RAISE5MIN'] = float(row[20])
                        unit.target_record['RAISE60SEC'] = float(row[21])
                        unit.target_record['RAISE6SEC'] = float(row[22])
                        unit.marginal_value_record['5MIN'] = float(row[25]) if row[25] else None
                        unit.marginal_value_record['60SEC'] = float(row[26]) if row[26] else None
                        unit.marginal_value_record['6SEC'] = float(row[27]) if row[27] else None
                        unit.violation_degree_record['5MIN'] = float(row[29]) if row[29] else None
                        unit.violation_degree_record['60SEC'] = float(row[30]) if row[30] else None
                        unit.violation_degree_record['6SEC'] = float(row[31]) if row[31] else None
                        unit.target_record['LOWERREG'] = float(row[34])
                        unit.target_record['RAISEREG'] = float(row[35])
                        unit.flags['RAISE6SEC'] = int(row[37])
                        unit.flags['RAISE60SEC'] = int(row[38])
                        unit.flags['RAISE5MIN'] = int(row[39])
                        unit.flags['RAISEREG'] = int(row[40])
                        unit.flags['LOWER6SEC'] = int(row[41])
                        unit.flags['LOWER60SEC'] = int(row[42])
                        unit.flags['LOWER5MIN'] = int(row[43])
                        unit.flags['LOWERREG'] = int(row[44])
                        unit.raisereg_availability = float(row[45])
                        unit.raisereg_enablement_max = float(row[46])
                        unit.raisereg_enablement_min = float(row[47])
                        unit.lowerreg_availability = float(row[48])
                        unit.lowerreg_enablement_max = float(row[49])
                        unit.lowerreg_enablement_min = float(row[50])
                        unit.actual_availability_record['RAISE6SEC'] = float(row[51])
                        unit.actual_availability_record['RAISE60SEC'] = float(row[52])
                        unit.actual_availability_record['RAISE5MIN'] = float(row[53])
                        unit.actual_availability_record['RAISEREG'] = float(row[54])
                        unit.actual_availability_record['LOWER6SEC'] = float(row[55])
                        unit.actual_availability_record['LOWER60SEC'] = float(row[56])
                        unit.actual_availability_record['LOWER5MIN'] = float(row[57])
                        unit.actual_availability_record['LOWERREG'] = float(row[58])


def add_dispatchload(units, t, start, process):
    """ Add dispatch load record generated by our NEMDE

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): i datetime
        start (datetime.datetime): start datetime of the process
        process (str): 'dispatch', 'predispatch', or 'p5min'

    Returns:
        None
    """
    interval_datetime = preprocess.get_case_datetime(t)
    if process == 'dispatch':
        record_dir = preprocess.OUT_DIR / process / 'dispatch_{}.csv'.format(interval_datetime)
    else:
        record_dir = preprocess.OUT_DIR / process / '{}_{}'.format(process, preprocess.get_case_datetime(start)) / 'dispatchload_{}.csv'.format(interval_datetime)

    with record_dir.open() as f:
        reader = csv.reader(f)
        # logging.info('Read next day dispatch.')
        for row in reader:
            if row[0] == 'D':
                duid = row[1]
                if duid in units:
                    unit = units[duid]
                    unit.initial_mw = float(row[2])


def add_scada_value(units, t):
    """ Add SCADA values.

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): i datetime

    Returns:
        None
    """
    scada_dir = preprocess.download_dispatch_scada(t)
    with scada_dir.open() as f:
        reader = csv.reader(f)
        # logging.info('Read SCADA value.')
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
            units[duid].region_id = 'NSW1'
            units[duid].dispatch_type = 'Generator'
        duid = 'DG_NSW{}'.format(i)
        if duid in units:
            units[duid].region_id = 'NSW1'
            units[duid].dispatch_type = 'Generator'

    for i in range(1, 13):
        duid = 'RT_VIC{}'.format(i)
        if duid in units:
            units[duid].region_id = 'VIC1'
            units[duid].dispatch_type = 'Generator'
        duid = 'DG_VIC{}'.format(i)
        if duid in units:
            units[duid].region_id = 'VIC1'
            units[duid].dispatch_type = 'Generator'

    for i in range(1, 7):
        duid = 'RT_SA{}'.format(i)
        if duid in units:
            units[duid].region_id = 'SA1'
            units[duid].dispatch_type = 'Generator'
        duid = 'DG_SA{}'.format(i)
        if duid in units:
            units[duid].region_id = 'SA1'
            units[duid].dispatch_type = 'Generator'

    for i in range(1, 2):
        duid = 'RT_TAS{}'.format(i)
        if duid in units:
            units[duid].region_id = 'TAS1'
            units[duid].dispatch_type = 'Generator'
        duid = 'DG_TAS{}'.format(i)
        if duid in units:
            units[duid].region_id = 'TAS1'
            units[duid].dispatch_type = 'Generator'

    for i in range(1, 2):
        duid = 'RT_QLD{}'.format(i)
        if duid in units:
            units[duid].region_id = 'QLD1'
            units[duid].dispatch_type = 'Generator'
        duid = 'DG_QLD{}'.format(i)
        if duid in units:
            units[duid].region_id = 'QLD1'
            units[duid].dispatch_type = 'Generator'


def get_units(t, start, i, process, fcas_flag):
    """Get units.

    Args:
        t (datetime.datetime): Interval datetime
        fcas_flag (bool): Consider FCAS or not

    Returns:
        dict: A dictionary of units

    """
    units = {}
    add_unit_bids(units, t, fcas_flag)

    # add_registration_information(units)
    # add_marginal_loss_factors(units)
    # add_reserve_trader(units)

    connection_points = add_du_detail(units, t)
    add_du_detail_summary(units, t)

    add_intermittent_forecast(units, t)
    # add_dispatchload_record(units, t, fcas_flag)
    if process == 'predispatch':
        import datetime
        add_dispatchload_record(units, t - datetime.timedelta(minutes=25), fcas_flag)
    else:
        add_dispatchload_record(units, t, fcas_flag)
        # if process == 'dispatch':
        #     add_dispatchload_record(units, t, fcas_flag)
        # else:
        #     add_dispatchload(units, t, start, 'dispatch')
    # if i != 0:
    #     add_dispatchload(units, t, start, process)
    return units, connection_points


def test_forecast():
    import datetime
    t = datetime.datetime(2019, 9, 29, 7, 45, 0)
    units, connection_points = get_units(t, t, 0, 'dispatch', True)
    for unit in units.values():
        if unit.forecast_priority is not None and unit.forecast_poe50 is None:
            print('BAD')
        elif unit.forecast_poe50 is not None:
            print('GOOD')


# def verify_fcas_availability():
#     import datetime
#     t = datetime.datetime(2020, 1, 31, 4, 5, 0)
#     units, _ = get_units(t, t, 0, 'dispatch', True)
#     for duid, unit in units.items():
#        for fcas_type, avail in unit.actual_availability_record.items():
#             if avail != 0 and unit.total_cleared_record != 0:
#                 if fcas_type == 'RAISEREG':
#                     a = unit.fcas_bids['RAISEREG'].max_avail


if __name__ == "__main__":
    # verify_fcas_availability()
    test_forecast()
