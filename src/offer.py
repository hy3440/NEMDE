import csv
import datetime
import default
import logging
import preprocess
import predefine


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
        self.max_avail = None
        self.band_avail = None


class EnergyBid(Bid):
    """Energy bid.

    Attributes:
        daily_energy_limit (float): Maximum energy available from Energy Constrained Plant
        minimum_load (int): Minimum MW load fast START plant
        t1 (int): Time to synchronise in minutes
        t2 (int): Time to minimum load in minutes
        t3 (int): Time at minimum load in minutes
        t4 (int): Time to shutdown in minutes
        normal_status (str): ON/OFF for loads

        fixed_load (float): Fixed unit output MW
        roc_up (int): MW/min for raise
        roc_down (int): MW/min for lower

    """
    def __init__(self, row):
        if row != []:
            super().__init__(row)
            # Daily bids
            self.daily_energy_limit = float(row[11])
            self.daily_energy = 0.0
            self.daily_energy_record = 0.0
            self.last_daily_energy = 0.0
            self.last_daily_energy_record = 0.0
            self.minimum_load = int(row[23])
            self.t1 = int(row[24])
            self.t2 = int(row[25])
            self.t3 = int(row[26])
            self.t4 = int(row[27])
            self.normal_status = row[28]
            # Period bids
            self.fixed_load = 0
            self.roc_up = None
            self.roc_down = None
        else:
            self.bid_type = 'ENERGY'
            # Daily bids
            self.price_band = None
            # Period bids
            self.max_avail = None
            self.band_avail = None
            # Daily bids
            self.daily_energy_limit = 0
            self.daily_energy = 0.0
            self.daily_energy_record = 0.0
            self.last_daily_energy = 0.0
            self.last_daily_energy_record = 0.0
            self.minimum_load = None
            self.t1 = None
            self.t2 = None
            self.t3 = None
            self.t4 = None
            # self.normal_status = None
            # Period bids
            self.fixed_load = 0
            self.roc_up = None
            self.roc_down = None


class FcasBid(Bid):
    """FCAS bid.

    Attributes:
        value (float): Dispatch value
        offers (list): Dispatch target for each band
        upper_slope_coeff (float): Upper slope coefficient
        lower_slop_coeff (float): Lower slope coefficient
        enablement_status (int): 1 if the FCAS service is enabled for the unit, otherwise 0
        enablement_min (int): Minimum Energy Output (MW) at which this ancillary service becomes available
        enablement_max (int): Maximum Energy Output (MW) at which this ancillary service becomes available
        low_breakpoint (int): Minimum Energy Output (MW) at which the unit can provide the full availability (MAXAVAIL) for this ancillary service
        high_breakpoint (int): Maximum Energy Output (MW) at which the unit can provide the full availability (MAXAVAIL) for this ancillary service
        flag (int): A flag exists for each ancillary service type such that a unit trapped or stranded in one or more service type can be immediately identified
    """
    def __init__(self, row):
        if row != []:
            super().__init__(row)
        else:
            self.bid_type = None
            # Daily bids
            self.price_band = None
            # Period bids
            self.max_avail = None
            self.band_avail = None
        self.value = 0.0
        self.offers = []
        self.upper_slope_coeff = 0.0
        self.lower_slope_coeff = 0.0
        self.enablement_status = 0
        # Period bids
        self.enablement_min = None
        self.enablement_max = None
        self.low_breakpoint = None
        self.high_breakpoint = None
        # Dispatch load
        self.flag = None


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
        dispatch_mode (int): Dispatch mode for fast start plant (0 to 4)
        initial_mw (float): AEMO actual initial MW at START of period
        marginal_value (float): Marginal $ value for energy
        marginal_value_record (float): AEMO record of marginal value

        violation_degree_record (dict): AEMO record of violation
        lowerreg_record (float): AEMO record of Lower Regulation reserve target
        raisereg_record (float): AEMO record of Raise Regulation reserve target
        availability (float): AEMO record of bid energy availability
        flags (dict): AEMO record of FCAS status flag
        raisereg_availability (float): AEMO record of RaiseReg availability
        raisereg_enablement_max (float): AEMO record of RaiseReg Enablement Max point
        raisereg_enablement_min (float): AEMO record of RaiseReg Enablemnt Min point
        lowerreg_availability (float): AEMO record of LowerReg availability
        lowerreg_enablement_max (float): AEMO record of LowerReg Enablement Max point
        lowerreg_enablement_min (float): AEMO record of LowerReg Enablement Min point
        actual_availability_record (dict): AEMO record of trapezium adjusted FCAS availability

        scada_value (float): AEMO actual generation SCADA value

        der_flag (bool): Whether the unit is a Custom DER unit

    """

    def __init__(self, duid):
        self.duid = duid
        # DU detail
        self.connection_point_id = None
        # self.volt_level = None
        # self.registered_capacity = None
        # self.agc_capability = None
        self.dispatch_type = None
        self.max_capacity = None
        self.start_type = 'NOT DISPATCHED'
        self.normally_on_flag = ''
        # self.intermittent_flag = None
        # self.semischedule_flag = None
        # self.max_rate_of_change_up = None
        # self.max_rate_of_change_down = None
        # DU detail summary
        self.region_id = None
        # self.station_id = None
        self.transmission_loss_factor = None
        # self.distribution_loss_factor = None
        # self.minimum_energy_price = None
        # self.maximum_energy_price = None
        # self.schedule_type = None
        # self.min_ramp_rate_up = None
        # self.min_ramp_rate_down = None
        # self.max_ramp_rate_up = None
        # self.max_ramp_rate_down = None
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
        self.offers = []
        self.total_cleared = 0.0
        # self.marginal_value = None
        self.lowerreg = None
        self.raisereg = None
        self.fcas_bids = {}
        # Dispatch load
        self.dispatch_mode = 0
        self.agc_status = None
        self.initial_mw = None
        self.total_cleared_record = None
        self.ramp_down_rate = None
        self.ramp_up_rate = None
        self.target_record = {}
        # self.marginal_value_record = {}
        # self.violation_degree_record = {}
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
        # Custom DER flag
        self.der_flag = False

    def set_duid(self, duid):
        self.duid = duid

    def set_initial_mw(self, initial_mw):
        self.initial_mw = initial_mw


# class Generator(Unit):
#     def __init__(self, duid, region_id, classification, station, reg_cap, max_cap, max_roc, source=None):
#         super().__init__(duid)
#         self.forecast = None
#         self.priority = 0
#
#
# class Load(Unit):
#     pass


def add_unit_bids(units, t, process, fcas_flag=True):
    """ Add unit bids.
    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): current datetime
        process (str): 'dispatch', 'p5min', or 'predispatch'
        fcas_flag (bool): whether to consider FCAS bids or not

    Returns:
        None
    """
    bids_dir = preprocess.download_bidmove_summary(t) if process == 'predispatch' else preprocess.download_bidmove_complete(t)
    interval_datetime = default.get_interval_datetime(t)
    with bids_dir.open() as f:
        reader = csv.reader(f)
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
            elif row[0] == 'D' and row[2] == 'BIDPEROFFER_D' and row[31] == interval_datetime:
                if row[6] == 'ENERGY':
                    energy = units[row[5]].energy
                    energy.max_avail = float(row[11])
                    energy.fixed_load = float(row[12])
                    energy.roc_up = int(row[13])
                    energy.roc_down = int(row[14])
                    energy.band_avail = [int(avail) for avail in row[19:29]]
                elif fcas_flag:
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
        units (dict): the dictionary of units
        t (datetime.datetime): current datetime

    Returns:
        A dictionary of connection points
    """
    connection_points = {}
    dd_dir = preprocess.download_dvd_data('DUDETAIL', t)
    with dd_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and default.extract_datetime(row[4]) <= t:
                unit = units.get(row[5])
                if unit:
                    if row[7] in connection_points and row[5] != connection_points[row[7]]:
                        logging.error(f'Connection point ID {row[7]} has more than one unit.')
                    connection_points[row[7]] = row[5]
                    unit.connection_point_id = row[7]
                    # unit.volt_level = row[8]
                    # unit.registered_capacity = int(row[9])
                    unit.agc_capability = row[10]
                    unit.dispatch_type = row[11]
                    # unit.max_capacity = int(row[12])
                    unit.start_type = row[13]
                    unit.normally_on_flag = row[14]
                    # unit.intermittent_flag = row[20]
                    # unit.semischedule_flag = row[21]
                    # unit.max_rate_of_change_up = int(row[22]) if row[22] else None
                    # unit.max_rate_of_change_down = int(row[23]) if row[23] else None
    return connection_points


def add_du_detail_summary(units, t):
    """ Add DU detail summary.

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): current datetime

    Returns:
        None
    """
    dds_dir = preprocess.download_dvd_data('DUDETAILSUMMARY', t)
    # logging.info('Read du detail summary.')
    with dds_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and default.extract_datetime(row[5]) <= t < default.extract_datetime(row[6]):
                unit = units.get(row[4])
                if unit:
                    unit.region_id = row[9]
                    # unit.station_id = row[10]
                    unit.transmission_loss_factor = float(row[13])
                    # unit.distribution_loss_factor = float(row[15])
                    # unit.minimum_energy_price = float(row[16])
                    # unit.maximum_energy_price = float(row[17])
                    # unit.schedule_type = row[18]
                    # unit.min_ramp_rate_up = int(row[19]) if row[19] else None
                    # unit.min_ramp_rate_down = int(row[20]) if row[20] else None
                    # unit.max_ramp_rate_up = int(row[21]) if row[21] else None
                    # unit.max_ramp_rate_down = int(row[22]) if row[22] else None


# def add_marginal_loss_factors(units):
#     """ Add marginal loss factors.
#
#     Args:
#         units (dict): a dictionary of units
#
#     Returns:
#         None
#     """
#     mlf_file = preprocess.download_mlf()
#     with xlrd.open_workbook(mlf_file) as f:
#         for sheet_index in range(f.nsheets):
#             sheet = f.sheet_by_index(sheet_index)
#             for row_index in range(sheet.nrows):
#                 if sheet.cell_type(row_index, 6) == 2:
#                     duid = sheet.cell_value(row_index, 2)
#                     if duid in units:
#                         unit = units[duid]
#                         unit.connection_point_id = sheet.cell_value(row_index, 3)
#                         unit.tni = sheet.cell_value(row_index, 4)
#                         # 2018-19 MLF applicable from 01 July 2018 to 30 June 2019
#                         # generator.mlf = sheet.cell_value(row_index, 6)
#                         # 2019-20 MLF applicable from 01 July 2019 to 30 June 2020
#                         unit.transmission_loss_factor = sheet.cell_value(row_index, 5)


def add_intermittent_forecast(units, t):
    """ Add intermittent forecast.

    Args:
        units (dict): a dictionary of units
        t (datetime.datetime): current datetime

    Returns:
        None
    """
    intermittent_dir = preprocess.download_intermittent(t)
    interval_datetime = default.get_interval_datetime(t)
    with intermittent_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'INTERMITTENT_FORECAST_TRK' and row[
                4] == interval_datetime:  # 4: SETTLEMENTDATE
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


def add_dispatchload_record(units, t, fcas_flag, debug_flag):
    """ Add AEMO dispatch record.

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): current datetime

    Returns:
        None
    """
    record_dir = preprocess.download_next_day_dispatch(t)
    interval_datetime = default.get_interval_datetime(t)
    with record_dir.open() as f:
        reader = csv.reader(f)
        # logging.info('Read next day dispatch.')
        for row in reader:
            if row[0] == 'D' and row[2] == 'UNIT_SOLUTION' and row[4] == interval_datetime:
                duid = row[6]
                if duid in units:
                    unit = units[duid]
                    unit.dispatch_mode = int(row[11])
                    unit.agc_status = int(row[12])
                    unit.initial_mw = float(row[13])
                    unit.total_cleared_record = float(row[14])
                    unit.ramp_down_rate = float(row[15])
                    unit.ramp_up_rate = float(row[16])
                    unit.raisereg_availability = float(row[45])
                    unit.raisereg_enablement_max = float(row[46])
                    unit.raisereg_enablement_min = float(row[47])
                    unit.lowerreg_availability = float(row[48])
                    unit.lowerreg_enablement_max = float(row[49])
                    unit.lowerreg_enablement_min = float(row[50])
                    if debug_flag:
                        # unit.marginal_value_record['ENERGY'] = float(row[28]) if row[28] else None
                        # unit.violation_degree_record['ENERGY'] = float(row[32]) if row[32] else None
                        unit.availability = float(row[36])
                        if fcas_flag:
                            unit.target_record['LOWER5MIN'] = float(row[17])
                            unit.target_record['LOWER60SEC'] = float(row[18])
                            unit.target_record['LOWER6SEC'] = float(row[19])
                            unit.target_record['RAISE5MIN'] = float(row[20])
                            unit.target_record['RAISE60SEC'] = float(row[21])
                            unit.target_record['RAISE6SEC'] = float(row[22])
                            # unit.marginal_value_record['5MIN'] = float(row[25]) if row[25] else None
                            # unit.marginal_value_record['60SEC'] = float(row[26]) if row[26] else None
                            # unit.marginal_value_record['6SEC'] = float(row[27]) if row[27] else None
                            # unit.violation_degree_record['5MIN'] = float(row[29]) if row[29] else None
                            # unit.violation_degree_record['60SEC'] = float(row[30]) if row[30] else None
                            # unit.violation_degree_record['6SEC'] = float(row[31]) if row[31] else None
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
                            unit.actual_availability_record['RAISE6SEC'] = float(row[51])
                            unit.actual_availability_record['RAISE60SEC'] = float(row[52])
                            unit.actual_availability_record['RAISE5MIN'] = float(row[53])
                            unit.actual_availability_record['RAISEREG'] = float(row[54])
                            unit.actual_availability_record['LOWER6SEC'] = float(row[55])
                            unit.actual_availability_record['LOWER60SEC'] = float(row[56])
                            unit.actual_availability_record['LOWER5MIN'] = float(row[57])
                            unit.actual_availability_record['LOWERREG'] = float(row[58])


def add_unit_solution(units, t, start, fcas_flag):
    """ Add AEMO P5MIN DISPATCHLOAD information.

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): current datetime
        start (datetime.datetime): start datetime
        fcas_flag (bool): whether consider FCAS or not

    Returns:
        None
    """
    record_dir = preprocess.read_p5min_unit_solution(start)
    interval_datetime = default.get_interval_datetime(t)
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[6] == interval_datetime:
                duid = row[7]
                if duid in units:
                    unit = units[duid]
                    unit.agc_status = int(row[10])
                    unit.initial_mw = float(row[11])
                    unit.total_cleared_record = float(row[12])
                    unit.ramp_down_rate = float(row[13])
                    unit.ramp_up_rate = float(row[14])
                    # unit.marginal_value_record['ENERGY'] = float(row[28]) if row[28] else None
                    # unit.violation_degree_record['ENERGY'] = float(row[32]) if row[32] else None
                    unit.availability = float(row[23])
                    if fcas_flag:
                        unit.target_record['LOWER5MIN'] = float(row[15])
                        unit.target_record['LOWER60SEC'] = float(row[16])
                        unit.target_record['LOWER6SEC'] = float(row[17])
                        unit.target_record['RAISE5MIN'] = float(row[18])
                        unit.target_record['RAISE60SEC'] = float(row[19])
                        unit.target_record['RAISE6SEC'] = float(row[20])
                        unit.target_record['LOWERREG'] = float(row[21])
                        unit.target_record['RAISEREG'] = float(row[22])
                        unit.flags['RAISE6SEC'] = int(row[24])
                        unit.flags['RAISE60SEC'] = int(row[25])
                        unit.flags['RAISE5MIN'] = int(row[26])
                        unit.flags['RAISEREG'] = int(row[27])
                        unit.flags['LOWER6SEC'] = int(row[28])
                        unit.flags['LOWER60SEC'] = int(row[29])
                        unit.flags['LOWER5MIN'] = int(row[30])
                        unit.flags['LOWERREG'] = int(row[31])


def add_predispatchload(units, t, start, i, fcas_flag):
    """ Add AEMO PREDISPATCH DISPACHLOAD information.

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): current datetime
        start (datetime.datetime): start datetime
        i (int): interval number
        fcas_flag (bool): whether consider FCAS or not

    Returns:
        None
    """
    interval_no = default.get_interval_no(start)
    record_dir = preprocess.read_predispatchload(start)
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'UNIT_SOLUTION' and int(row[8]) == i + 1 and row[4] == interval_no:
                duid = row[6]
                if duid in units:
                    unit = units[duid]
                    unit.dispatch_mode = int(row[12])
                    unit.agc_status = int(row[11])
                    unit.initial_mw = float(row[13])
                    unit.total_cleared_record = float(row[14])
                    unit.ramp_down_rate = float(row[21])
                    unit.ramp_up_rate = float(row[22])
                    unit.marginal_value_record['ENERGY'] = float(row[28]) if row[28] else None
                    unit.violation_degree_record['ENERGY'] = float(row[32]) if row[32] else None
                    unit.availability = float(row[37])
                    if fcas_flag:
                        unit.target_record['LOWER5MIN'] = float(row[15])
                        unit.target_record['LOWER60SEC'] = float(row[16])
                        unit.target_record['LOWER6SEC'] = float(row[17])
                        unit.target_record['RAISE5MIN'] = float(row[18])
                        unit.target_record['RAISE60SEC'] = float(row[19])
                        unit.target_record['RAISE6SEC'] = float(row[20])
                        unit.marginal_value_record['5MIN'] = float(row[25]) if row[25] else None
                        unit.marginal_value_record['60SEC'] = float(row[26]) if row[26] else None
                        unit.marginal_value_record['6SEC'] = float(row[27]) if row[27] else None
                        unit.violation_degree_record['5MIN'] = float(row[29]) if row[29] else None
                        unit.violation_degree_record['60SEC'] = float(row[30]) if row[30] else None
                        unit.violation_degree_record['6SEC'] = float(row[31]) if row[31] else None
                        unit.target_record['LOWERREG'] = float(row[35])
                        unit.target_record['RAISEREG'] = float(row[36])
                        unit.flags['RAISE6SEC'] = int(row[38])
                        unit.flags['RAISE60SEC'] = int(row[39])
                        unit.flags['RAISE5MIN'] = int(row[40])
                        unit.flags['RAISEREG'] = int(row[41])
                        unit.flags['LOWER6SEC'] = int(row[42])
                        unit.flags['LOWER60SEC'] = int(row[43])
                        unit.flags['LOWER5MIN'] = int(row[44])
                        unit.flags['LOWERREG'] = int(row[45])
                        unit.actual_availability_record['RAISE6SEC'] = float(row[46])
                        unit.actual_availability_record['RAISE60SEC'] = float(row[47])
                        unit.actual_availability_record['RAISE5MIN'] = float(row[48])
                        unit.actual_availability_record['RAISEREG'] = float(row[49])
                        unit.actual_availability_record['LOWER6SEC'] = float(row[50])
                        unit.actual_availability_record['LOWER60SEC'] = float(row[51])
                        unit.actual_availability_record['LOWER5MIN'] = float(row[52])
                        unit.actual_availability_record['LOWERREG'] = float(row[53])


def add_dispatchload(units, links, t, start, process, k=0, path_to_out=default.OUT_DIR, dispatchload_path=None, daily_energy_flag=False):
    """ Add the dispatch load record generated by our model.

    Args:
        units (dict): the dictionary of units
        links (dict): the dictionary of links
        t (datetime.datetime): current datetime
        start (datetime.datetime): start datetime of the process
        process (str): 'dispatch', 'predispatch', or 'p5min'
        k (int): price-taker iteration number
        path_to_out (Path): path to the out directory

    Returns:
        None
    """
    if dispatchload_path is None:
        interval_datetime = default.get_case_datetime(t)
        if process == 'dispatch':
            path_to_file = path_to_out / (process if k == 0 else f'{process}_{k}') / f'dispatchload_{interval_datetime}.csv'
        else:
            path_to_file = path_to_out / (process if k == 0 else f'{process}_{k}') / f'{process}load_{default.get_case_datetime(start)}' / f'dispatchload_{interval_datetime}.csv'
    else:
        path_to_file = dispatchload_path
    with path_to_file.open() as f:
        reader = csv.reader(f)
        # logging.info('Read next day dispatch.')
        for row in reader:
            if row[0] == 'D':
                duid = row[1]
                if duid in units:
                    unit = units[duid]
                    unit.initial_mw = float(row[2])
                    if daily_energy_flag and unit.energy is not None and unit.energy.daily_energy_limit != 0:
                        unit.energy.daily_energy = float(row[4])
                        unit.energy.daily_energy_record = float(row[5])
                        # unit.energy.last_daily_energy = float(row[6])
                        # unit.energy.last_daily_energy_record = float(row[7])
                elif duid in links:
                    links[duid].metered_mw_flow = float(row[2])


def add_last_daily_energy(units, t, start, process, k=0, path_to_out=default.OUT_DIR, dispatchload_path=None):
    if dispatchload_path is None:
        interval_datetime = default.get_case_datetime(t)
        if process == 'dispatch':
            path_to_file = path_to_out / (process if k == 0 else f'{process}_{k}') / f'dispatchload_{interval_datetime}.csv'
        else:
            path_to_file = path_to_out / (process if k == 0 else f'{process}_{k}') / f'{process}load_{default.get_case_datetime(start)}' / f'dispatchload_{interval_datetime}.csv'
    else:
        path_to_file = dispatchload_path
    with path_to_file.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                duid = row[1]
                if duid in units:
                    unit = units[duid]
                    # unit.initial_mw = float(row[2])
                    if unit.energy is not None and unit.energy.daily_energy_limit != 0:
                        # unit.energy.daily_energy = float(row[4])
                        # unit.energy.daily_energy_record = float(row[5])
                        unit.energy.last_daily_energy = float(row[6])
                        unit.energy.last_daily_energy_record = float(row[7])


def add_agc(units, t):
    """ Add AGC information.

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): current datetime

    Returns:
        None
    """
    record_dir = preprocess.download_next_day_dispatch(t)
    interval_datetime = default.get_interval_datetime(t)
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'UNIT_SOLUTION' and row[4] == interval_datetime:
                duid = row[6]
                if duid in units:
                    unit = units[duid]
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
        t (datetime.datetime): i datetime

    Returns:
        None
    """
    scada_dir = preprocess.download_dispatch_scada(t)
    with scada_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                if row[5] in units:
                    units[row[5]].scada_value = float(row[6])


def calculate_daily_energy(units, t, k, path_to_out):
    """ Calculate daily energy sum for PREDISPATCH.

    Args:
        units (dict): the dictionary of units
        t (datetime.datetime): current datetime
        k (int): iteration number
        path_to_out (Path): path to out file

    Returns:
        None
    """
    start = default.get_first_datetime(t, 'dispatch')
    while start < t:
        interval_datetime = default.get_interval_datetime(start)
        if k == 0:
            path_to_file = preprocess.download_next_day_dispatch(start)
            with path_to_file.open() as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == 'D' and row[2] == 'UNIT_SOLUTION' and row[4] == interval_datetime:
                        duid = row[6]
                        if duid in units:
                            unit = units[duid]
                            if unit.energy is not None and unit.energy.daily_energy_limit != 0:
                                unit.energy.daily_energy += float(row[14]) / 12.0
                                unit.energy.daily_energy_record += float(row[14]) / 12.0
        else:
            path_to_file = path_to_out / ('dispatch' if k == 0 else f'dispatch_{k}') / f'dispatchload_{default.get_case_datetime(start + default.FIVE_MIN)}.csv'
            with path_to_file.open() as f:
                reader = csv.reader(f)
                # logging.info('Read next day dispatch.')
                for row in reader:
                    if row[0] == 'D':
                        duid = row[1]
                        if duid in units:
                            unit = units[duid]
                            unit.initial_mw = float(row[2])
                            if unit.energy is not None and unit.energy.daily_energy_limit != 0:
                                unit.energy.daily_energy += float(row[2]) / 12.0
                                unit.energy.daily_energy_record += float(row[3]) / 12.0 if row[3] != '-' else 0
        start += default.FIVE_MIN


def get_units(t, start, i, process, units={}, links={}, fcas_flag=True, dispatchload_path=None, dispatchload_flag=True, daily_energy_flag=True, agc_flag=True, predispatch_t=None, k=0, path_to_out=default.OUT_DIR, debug_flag=False, dispatchload_record=False):
    """Get units.

    Args:
        t (datetime.datetime): Current datetime (Note special case for Predispatch)
        start (datetime.datetime): Start datetime
        i (int): Interval number
        process (str): 'dispatch', 'p5min' or 'predispatch'
        fcas_flag (bool): Consider FCAS or not
        dispatchload_flag (bool): True if use our DISPATCHLOAD; False if use AEMO'S DISPATCHLOAD record
        predispatch_t (datetime.datetime): Current Predispatch datetime
        k (int): Price-taker iteration number
        path_to_out (Path): Path to the out directory

    Returns:
        dict: A dictionary of units and a dictionary of connection points
    """
    # Pre-process t and predispatch_t for PREDISPATCH
    if process == 'predispatch':
        if predispatch_t is None:
            predispatch_t = start + i * default.THIRTY_MIN
            t = predispatch_t - default.TWENTYFIVE_MIN

    # add_unit_bids(units, predispatch_t if process == 'predispatch' else t, process, fcas_flag)
    # add_intermittent_forecast(units, t)

    # add_registration_information(units)
    # add_marginal_loss_factors(units)
    # add_reserve_trader(units)
    # connection_points = add_du_detail(units, t)
    # add_du_detail_summary(units, t)
    predefine.add_simplified_dudetailsummary(units, t)

    # if process == 'dispatch':
    if (dispatchload_record and fcas_flag) or debug_flag:
        add_dispatchload_record(units, t, fcas_flag, debug_flag)
    # elif process == 'p5min':
    #     add_unit_solution(units, t, start, fcas_flag)
    # elif process == 'predispatch':
    #     add_predispatchload(units, predispatch_t, start, i, fcas_flag)
    #     if i == 0 and daily_energy_flag:
    #         calculate_daily_energy(units, t, k, path_to_out)

    if process == 'predispatch' and i == 0 and daily_energy_flag:
        calculate_daily_energy(units, t, k, path_to_out)
    if i == 0 and fcas_flag and process != 'dispatch' and agc_flag:
        add_agc(units, t)
    if dispatchload_flag:
        add_dispatchload(units, links, predispatch_t if process == 'predispatch' else t, start, process, k=k,
                         path_to_out=path_to_out, dispatchload_path=dispatchload_path, daily_energy_flag=daily_energy_flag)
    # return connection_points
    return None
