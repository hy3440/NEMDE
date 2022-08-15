import csv
import datetime
import default
import gurobipy as gp
import logging
import predefine
import preprocess

log = logging.getLogger(__name__)
intervention = '0'


class Solution:
    """Region class.

        Attributes:
            intervention (char): Intervention flag - refer to package documentation for definition and practical query examples
            case_subtype (str): Overconstrained dispatch indicator: OCD = detecting over-constrained dispatch; null = no special condition
            solution_status (int): If non-zero indicated one of the following conditions: 1 = Supply Scarcity, Excess generation or constraint violations; X = Model failure
            spd_version (str): Current version of SPD
            non_physical_losses (int): Non-Physical Losses algorithm invoked occurred during this run
            total_objective (float): The Objective function from the LP
            total_area_gen_violation (float): Total Region Demand violations
            total_interconnector_violation (float): Total interconnector violations
            total_generic_violation (float): Total generic constraint violations
            total_ramp_rate_violation (float): Total ramp rate violations
            total_unit_mw_capacity_violation (float): Total unit capacity violations
            total_5min_violation (float): Total of 5 minute ancillary service region violations
            total_reg_violation (float): Total of Regulation ancillary service region violations
            total_6sec_violation (float): Total of 6 second ancillary service region violations
            total_60sec_violation (float): Total of 60 second ancillary service region violations
            total_as_profile_violation (float): Total of ancillary service trader profile violations
            total_fast_start_violation (float): Total of fast start trader profile violations
            total_energy_offer_violation (float): Total of unit summated offer band violations
    """
    def __init__(self):
        self.intervention = None
        self.case_subtype = None
        self.solution_status = None
        self.spd_version = None
        self.non_physical_losses = None
        self.total_objective = None
        self.violations = {}
        # self.violations['total_area_gen_violation'] = float(row[12])
        # self.violations['total_interconnector_violation'] = float(row[13])
        # self.violations['total_generic_violation'] = float(row[14])
        # self.violations['total_ramp_rate_violation'] = float(row[15])
        # self.violations['total_unit_mw_capacity_violation'] = float(row[16])
        # self.violations['total_5min_violation'] = float(row[17]) if row[17] != '' else 0
        # self.violations['total_reg_violation'] = float(row[18]) if row[18] != '' else 0
        # self.violations['total_6sec_violation'] = float(row[19]) if row[19] != '' else 0
        # self.violations['total_60sec_violation'] = float(row[20]) if row[20] != '' else 0
        # self.violations['total_as_profile_violation'] = float(row[21])
        # self.violations['total_fast_start_violation'] = float(row[22])
        # self.violations['total_energy_offer_violation'] = float(row[23])
        # self.total_violation = sum(self.violations.values())


class Region:
    """Region class.

    Attributes:
        region_id (str): Region identifier
        # generators (set): A set of generators' DUID within the region
        # loads (set): A set of loads' DUID within the region
        dispatchable_generation (float): Total dispatched generation of the region
        dispatchable_generation_temp (float): Used to calculate AEMO generation record
        dispatchable_load (float): Total dispatched load of the region
        dispatchable_load_temp (float): Used to calculation AEMO load record
        net_mw_flow (float): Net interconnector targets into the region
        net_mw_flow_record (float): AEMO record for net flow into the region
        total_demand (float): Total demand of the region at given interval
        dispatchable_generation_record (float): AEMO record for total generation
        dispatchable_load_record (float): AEMO record for total loads
        rrp_record (float): AEMO record for regional reference price (after adjustments).
        rop_record (float): AEMO record for regional override price (before adjustments).
        rrp (float): Regional marginal price
        available_generation (float): Total available generation in the region
        available_load (float): Total available load in the region
        available_generation_record (float): AEMO record for total available generation
        available_load_record (float): AEMO record for total available load
        net_interchange_record (float): AEMO record for net interconnector flow from the regional reference node
        uigf (float): Regional aggregated Unconstrained Intermittent Generation Forecast
        uigf_record (float): AEMO record for UIGF
        losses (float): Allocated interconnector losses for the region
    """
    def __init__(self, region_id, debug_flag=False):
        self.region_id = region_id
        self.net_mw_flow = 0.0
        self.total_demand = None
        self.fcas_local_dispatch = {}  # Used to dispatch generic constraint
        self.fcas_local_dispatch_temp = {
            'RAISEREG': 0,
            'RAISE6SEC': 0,
            'RAISE60SEC': 0,
            'RAISE5MIN': 0,
            'LOWERREG': 0,
            'LOWER6SEC': 0,
            'LOWER60SEC': 0,
            'LOWER5MIN': 0
        }  # Used to calculate the sum of our FCAS value
        self.fcas_local_dispatch_record_temp = {
            'RAISEREG': 0,
            'RAISE6SEC': 0,
            'RAISE60SEC': 0,
            'RAISE5MIN': 0,
            'LOWERREG': 0,
            'LOWER6SEC': 0,
            'LOWER60SEC': 0,
            'LOWER5MIN': 0
        }  # Used to calculate the sum of each FCAS type
        self.fcas_local_dispatch_record = {}  # AEMO's FCAS local dispatch record
        self.rrp = None  # required
        self.rrp_record = 0
        # self.rop_record = None
        self.fcas_constraints = {
            'RAISEREG': set(),
            'RAISE6SEC': set(),
            'RAISE60SEC': set(),
            'RAISE5MIN': set(),
            'LOWERREG': set(),
            'LOWER6SEC': set(),
            'LOWER60SEC': set(),
            'LOWER5MIN': set()
        }
        self.local_fcas_constr = {}  # required
        self.fcas_rrp = {}  # required
        self.losses = 0.0  # required
        # self.offset = 0
        self.dispatchable_generation = 0.0  # required
        self.dispatchable_load = 0.0  # required
        if debug_flag:
            self.available_generation = 0.0
            self.available_load = 0.0
            self.available_generation_record = None
            self.available_load_record = None
            self.net_interchange_record = None
            self.dispatchable_generation_temp = 0.0
            self.dispatchable_load_temp = 0.0
            self.dispatchable_generation_record = None
            self.dispatchable_load_record = None
            self.net_mw_flow_record = 0.0
            self.fcas_rrp_record = {}
            self.net_interchange_record_temp = 0.0
            self.uigf_record = None
            self.losses_record = 0.0


def init_regions(debug_flag):
    """Initiate the dictionary for regions.

    Returns:
        dict: A dictionary of regions.
    """
    # logging.info('Initiate regions.')
    return {'NSW1': Region('NSW1', debug_flag),
            'QLD1': Region('QLD1', debug_flag),
            'SA1': Region('SA1', debug_flag),
            'TAS1': Region('TAS1', debug_flag),
            'VIC1': Region('VIC1', debug_flag)}


class Interconnector:
    """Interconnector class.

    Attributes:
        interconnector_id (str): Unique ID of this interconnector
        region_from (str): Starting region of the interconnector
        region_to (str): Ending region of the interconnector

        from_region_loss_share (float): Loss share attributable to from region
        max_mw_in (float): Limit of energy flowing into the RegionFrom
        max_mw_out (float): Limit of energy flowing out of the RegionFrom
        loss_constant (float): Constant loss factor
        loss_flow_coefficient (float): Linear coefficient of loss factor calculation
        import_limit (int): Interconnector import limit
        export_limit (int): Interconnector export limit
        fcas_support_unavailable (int): Flag to indicate that the interconnector cannot support FCAS transfers
        ic_type (str): Interconnector type - either REGULATED or MNSP

        mw_flow (float): Target for interconnector flow
        mw_flow_record (float): AEMO record for interconnector flow
        mw_losses (float): Interconnector MW losses
        mw_losses_record (float): AEMO record for MW losses
        marginal_loss_record (float): AEMO record for marginal loss factor
    """
    def __init__(self,
                 interconnector_id,
                 region_from,
                 region_to):
        # Interconnector
        self.interconnector_id = interconnector_id  # required
        self.region_from = region_from  # required
        self.region_to = region_to  # required
        # Interconnector constraint
        self.from_region_loss_share = None  # required
        # self.max_mw_in = None
        # self.max_mw_out = None
        self.loss_constant = None  # used to calculate losses
        self.loss_flow_coefficient = None  # used to calculate losses
        self.import_limit = None  # used in interconnector capacity constr
        self.export_limit = None  # used in interconnector capacity constr
        # self.fcas_support_unavailable = None
        # self.ic_type = None
        # Loss factor model
        self.demand_coefficient = {}  # used to calculate losses
        # Loss model
        self.mw_breakpoint = {}  # used to calculate losses
        # Dispatch
        # self.metered_mw_flow = None
        self.mw_flow = None  # required
        self.mw_flow_record = None
        self.mw_losses = 0.0  # required
        # self.mw_losses_record = None
        # self.marginal_value_record = None
        # self.violation_degree_record = None
        # self.export_limit_record = None  # used in interconnector limit constr
        # self.import_limit_record = None  # used in interconnector limit constr
        # self.marginal_loss = None
        # self.marginal_loss_record = None
        # self.fcas_export_limit_record = None
        # self.fcas_import_limit_record = None


def init_interconnectors():
    """Initiate the dictionary for interconnectors.

    Returns:
        dict: A dictionary of interconnectors
    """
    # logging.info('Initiate interconnectors.')
    return {'N-Q-MNSP1': Interconnector('N-Q-MNSP1', 'NSW1', 'QLD1'),
            'NSW1-QLD1': Interconnector('NSW1-QLD1', 'NSW1', 'QLD1'),
            'VIC1-NSW1': Interconnector('VIC1-NSW1', 'VIC1', 'NSW1'),
            'T-V-MNSP1': Interconnector('T-V-MNSP1', 'TAS1', 'VIC1'),
            'V-SA': Interconnector('V-SA', 'VIC1', 'SA1'),
            'V-S-MNSP1': Interconnector('V-S-MNSP1', 'VIC1', 'SA1')}


def add_interconnector_constraint(interconnectors, t):
    ic_dir = preprocess.download_dvd_data('INTERCONNECTORCONSTRAINT', t)
    with ic_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and default.extract_datetime(row[6]) <= t:
                ic = interconnectors.get(row[8])
                if ic:
                    ic.from_region_loss_share = float(row[5])
                    # ic.max_mw_in = float(row[9])
                    # ic.max_mw_out = float(row[10])
                    ic.loss_constant = float(row[11])
                    ic.loss_flow_coefficient = float(row[12])
                    ic.import_limit = int(row[17])
                    ic.export_limit = int(row[18])
                    # ic.fcas_support_unavailable = int(row[24])
                    # ic.ic_type = row[25]


def add_loss_factor_model(interconnectors, t):
    lfm_dir = preprocess.download_dvd_data('LOSSFACTORMODEL', t)
    with lfm_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and default.extract_datetime(row[4]) <= t:
                ic = interconnectors.get(row[6])
                if ic:
                    ic.demand_coefficient[row[7]] = float(row[8])


def add_loss_model(interconnectors, t):
    lm_dir = preprocess.download_dvd_data('LOSSMODEL', t)
    with lm_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and default.extract_datetime(row[4]) <= t:
                ic = interconnectors.get(row[6])
                if ic:
                    ic.mw_breakpoint[int(row[8])] = float(row[9])


class Link:
    """ MNSP link class.

    Attributes:
        link_id (str): Identifier for each of the two MNSP Interconnector Links

        interconnector_id (str): Interconnector identifier
        from_region (str): Nominated source region for interconnector
        to_region (str): Nominated destination region for interconnector
        max_capacity (float): Maximum capacity
        lhs_factor (float): Factor applied to the LHS of constraint equations
        from_region_tlf (float): Transmission loss factor for link "From Region" end
        to_region_tlf (float): Transmission loss factor for link at "To Region" end

        price_band (list): Ten price bands
        max_avail (int): Maximum planned availability MW
        fixed_load (float): Inflexibility flag and availability. Fixed unit output MW.
        band_avail (list): Band Availability for current Period

    """
    def __init__(self,
                 link_id,):
        # Initiate
        self.link_id = link_id
        # MNSP interconnector
        self.interconnector_id = None
        self.from_region = None
        self.to_region = None
        self.max_capacity = None
        self.lhs_factor = None
        self.from_region_tlf = None
        self.to_region_tlf = None
        # Bid
        self.price_band = None
        self.max_avail = None
        self.band_avail = None
        self.ramp_up_rate = None
        # Custom
        self.mw_flow = 0.0
        self.mw_flow_record = 0.0
        self.losses = None


def init_links():
    """Initiate the dictionary for links.

    Returns:
        dict: A dictionary of links

    """
    # logging.info('Initiate links.')
    return {'BLNKTAS': Link('BLNKTAS'),
            'BLNKVIC': Link('BLNKVIC')}


def add_mnsp_interconnector(links, t):
    """Add MNSP interconnector information.

    Args:
        links (dict): dictionary of links
        t (datetime.datetime): current datetime

    Returns:
        None
    """
    mnsp_dir = preprocess.download_dvd_data('MNSP_INTERCONNECTOR', t)
    with mnsp_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and default.extract_datetime(row[5]) <= t:
                link = links.get(row[4])
                if link:
                    link.interconnector_id = row[7]
                    link.from_region = row[8]
                    link.to_region = row[9]
                    link.max_capacity = int(row[10])
                    link.lhs_factor = float(row[12])
                    link.from_region_tlf = float(row[17]) if row[17] else None
                    link.to_region_tlf = float(row[18]) if row[18] else None


def add_mnsp_bids(links, t):
    """Add MNSP bids.

    Args:
        links (dict): dictionary of links
        t (datetime.datetime): current datetime

    Returns:
        None
    """
    mnsp_dir = preprocess.download_mnsp_bids(t)
    with mnsp_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                if row[2] == 'DAILY':
                    link = links[row[4]]
                    link.price_band = [float(price) for price in row[12:22]]
                elif row[2] == 'PERIOD' and default.ZERO <= default.extract_datetime(row[9]) - t < default.THIRTY_MIN:
                    link = links[row[4]]
                    link.max_avail = int(row[10])
                    link.band_avail = [int(avail) for avail in row[12:22]]
                    link.ramp_up_rate = int(row[22])


def get_links(t):
    """Get the dictionary of links.

    Args:
        t (datetime.datetime): current datetime

    Returns:
        dict: dictionary of links
    """
    links = init_links()
    add_mnsp_interconnector(links, t)
    add_mnsp_bids(links, t)
    return links


def sos_calculate_interconnector_losses(model, regions, interconnectors, prob_id, debug_flag):
    """Use Special Ordered Set (SOS) type 2 to calculate interconnector losses.

    Args:
        model (gurobipy.Model): optimisation model
        regions (dict): dictionary of regions
        interconnectors (dict): dictionary of interconnectors
        prob_id (str): problem ID

    Returns:
        None
    """
    for ic_id, ic in interconnectors.items():
        coefficient = ic.loss_constant - 1
        for region_id, dc in ic.demand_coefficient.items():
            coefficient += regions[region_id].total_demand * dc

        x_s = sorted(ic.mw_breakpoint.values())
        y_s = [0.5 * ic.loss_flow_coefficient * x * x + coefficient * x for x in x_s]
        ic.mw_losses = model.addVar(lb=-gp.GRB.INFINITY, name=f'Mw_Losses_{ic_id}_{prob_id}')

        lambda_s = [model.addVar(name=f'Lambda{i}_{ic_id}_{prob_id}') for i in x_s]
        model.addLConstr(ic.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]), f'SOS_MW_FLOW_{ic_id}_{prob_id}')
        model.addLConstr(ic.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]), f'SOS_MW_LOSSES_{ic_id}_{prob_id}')
        model.addLConstr(sum(lambda_s) == 1, f'SOS_LAMBDA_{ic_id}_{prob_id}')
        model.addSOS(gp.GRB.SOS_TYPE2, lambda_s)
        share_losses(regions, ic, debug_flag)


def calculate_interconnector_losses(model, regions, interconnectors, prob_id, debug_flag):
    """Linearly calculate interconnector losses.

    Args:
        model (gurobipy.Model): optimisation probelm
        regions (dict): dictionary of regions
        interconnectors (dict): dictionary of interconnectors
        prob_id (str): problem ID
        debug_flag (bool): used to debug or not

    Returns:
        None
    """
    for ic in interconnectors.values():
        coefficient = ic.loss_constant - 1
        for region_id, dc in ic.demand_coefficient.items():
            coefficient += regions[region_id].total_demand * dc
        x_s = sorted(ic.mw_breakpoint.values())
        y_s = [0.5 * ic.loss_flow_coefficient * x * x + coefficient * x for x in x_s]
        ic.mw_losses = model.addVar(lb=-gp.GRB.INFINITY, name=f'Mw_Losses_{ic.interconnector_id}_{prob_id}')
        for i in range(len(x_s) - 1):
            model.addLConstr((ic.mw_losses - y_s[i]) * (x_s[i + 1] - x_s[i]) >= (y_s[i + 1] - y_s[i]) * (ic.mw_flow - x_s[i]), f'LOSSES_{ic.interconnector_id}_{prob_id}')
        share_losses(regions, ic, debug_flag)


def share_losses(regions, ic, debug_flag):
    """Share interconnector's losses to connected regions.

    Args:
        regions (dict): dictionary of regions
        ic (Interconnector): interconnector instance
        debug_flag (bool): used to debug or not

    Returns:
        None
    """
    if ic.interconnector_id == 'T-V-MNSP1':
        if ic.metered_mw_flow >= 0:
            regions['TAS1'].losses += ic.mw_losses
            if debug_flag:
                regions['TAS1'].losses_record += ic.mw_losses_record
                regions['TAS1'].net_interchange_record_temp += ic.mw_losses_record
        else:
            regions['VIC1'].losses += ic.mw_losses
            if debug_flag:
                regions['VIC1'].losses_record += ic.mw_losses_record
                regions['VIC1'].net_interchange_record_temp += ic.mw_losses_record
    else:
        regions[ic.region_from].losses += ic.mw_losses * ic.from_region_loss_share
        regions[ic.region_to].losses += ic.mw_losses * (1 - ic.from_region_loss_share)
        if debug_flag:
            regions[ic.region_from].losses_record += ic.mw_losses_record * ic.from_region_loss_share
            regions[ic.region_to].losses_record += ic.mw_losses_record * (1 - ic.from_region_loss_share)
            regions[ic.region_from].net_interchange_record_temp += ic.mw_losses_record * ic.from_region_loss_share
            regions[ic.region_to].net_interchange_record_temp += ic.mw_losses_record * (1 - ic.from_region_loss_share)


def add_dispatchis_record(regions, interconnectors, t, fcas_flag, debug_flag):
    """Add region and interconnector record from DISPATCHIS file.

    Args:
        regions (dict): dictionary of regions
        interconnectors (dict): dictionary
        t (datetime.datetime): current datetime
        fcas_flag (bool): consider FCAS or not
        debug_flag (bool): used to debug or not

    Returns:
        Solution: solution instance
    """
    solution = None
    dispatch_dir = preprocess.download_dispatch_summary(t)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSUM' and row[8] == intervention:
                region = regions[row[6]]
                region.total_demand = float(row[9])
                if debug_flag:
                    region.available_generation_record = float(row[10])
                    region.available_load_record = float(row[11])
                    region.dispatchable_generation_record = float(row[13])
                    region.dispatchable_load_record = float(row[14])
                    region.net_interchange_record = float(row[15])
                    if fcas_flag:
                        region.fcas_local_dispatch_record['LOWER5MIN'] = float(row[19])
                        region.fcas_local_dispatch_record['LOWER60SEC'] = float(row[27])
                        region.fcas_local_dispatch_record['LOWER6SEC'] = float(row[35])
                        region.fcas_local_dispatch_record['RAISE5MIN'] = float(row[43])
                        region.fcas_local_dispatch_record['RAISE60SEC'] = float(row[51])
                        region.fcas_local_dispatch_record['RAISE6SEC'] = float(row[59])
                        region.fcas_local_dispatch_record['LOWERREG'] = float(row[71])
                        region.fcas_local_dispatch_record['RAISEREG'] = float(row[75])
                    # region.lower5min_local_dispatch_record = float(row[19])
                    # region.lower60sec_local_dispatch_record = float(row[27])
                    # region.lower6sec_local_dispatch_record = float(row[35])
                    # region.raise5min_local_dispatch_record = float(row[43])
                    # region.raise60sec_local_dispatch_record = float(row[51])
                    # region.raise6sec_local_dispatch_record = float(row[59])
                    # region.lowerreg_local_dispatch_record = float(row[71])
                    # region.raisereg_local_dispatch_record = float(row[75])
                    region.uigf_record = float(row[106])
            elif debug_flag and row[0] == 'D' and row[2] == 'PRICE' and row[8] == intervention:
                region = regions[row[6]]
                region.rrp_record = float(row[9])
                region.rop_record = float(row[11])
                if fcas_flag:
                    region.fcas_rrp_record['RAISE6SEC'] = float(row[15])
                    region.fcas_rrp_record['RAISE60SEC'] = float(row[18])
                    region.fcas_rrp_record['RAISE5MIN'] = float(row[21])
                    region.fcas_rrp_record['RAISEREG'] = float(row[24])
                    region.fcas_rrp_record['LOWER6SEC'] = float(row[27])
                    region.fcas_rrp_record['LOWER60SEC'] = float(row[30])
                    region.fcas_rrp_record['LOWER5MIN'] = float(row[33])
                    region.fcas_rrp_record['LOWERREG'] = float(row[36])
                # region.raise6sec_rrp_record = float(row[15])
                # region.raise60sec_rrp_record = float(row[18])
                # region.raise5min_rrp_record = float(row[21])
                # region.raisereg_rrp_record = float(row[24])
                # region.lower6sec_rrp_record = float(row[27])
                # region.lower60sec_rrp_record = float(row[30])
                # region.lower5min_rrp_record = float(row[33])
                # region.lowerreg_rrp_record = float(row[36])
            elif debug_flag and row[0] == 'D' and row[2] == 'CASE_SOLUTION':
                solution = Solution()
                solution.intervention = row[6]
                solution.case_subtype = row[7]
                solution.solution_status = int(row[8])
                solution.spd_version = row[9]
                solution.non_physical_losses = int(row[10])
                solution.total_objective = float(row[11])
                solution.violations['total_area_gen_violation'] = float(row[12])
                solution.violations['total_interconnector_violation'] = float(row[13])
                solution.violations['total_generic_violation'] = float(row[14])
                solution.violations['total_ramp_rate_violation'] = float(row[15])
                solution.violations['total_unit_mw_capacity_violation'] = float(row[16])
                solution.violations['total_5min_violation'] = float(row[17]) if row[17] != '' else 0
                solution.violations['total_reg_violation'] = float(row[18]) if row[18] != '' else 0
                solution.violations['total_6sec_violation'] = float(row[19]) if row[19] != '' else 0
                solution.violations['total_60sec_violation'] = float(row[20]) if row[20] != '' else 0
                solution.violations['total_as_profile_violation'] = float(row[21])
                solution.violations['total_fast_start_violation'] = float(row[22])
                solution.violations['total_energy_offer_violation'] = float(row[23])
                solution.total_violation = sum(solution.violations.values())
            elif row[0] == 'D' and row[2] == 'INTERCONNECTORRES' and row[8] == intervention:
                interconnector = interconnectors[row[6]]
                interconnector.metered_mw_flow = float(row[9])
                interconnector.mw_flow_record = float(row[10])
                if debug_flag:
                    interconnector.mw_losses_record = float(row[11])
                    interconnector.marginal_value_record = float(row[12])
                    interconnector.violation_degree_record = float(row[13])
                    interconnector.export_limit_record = float(row[15])
                    interconnector.import_limit_record = float(row[16])
                    interconnector.marginal_loss_record = float(row[17])
    return solution


def add_predispatch_record(regions, interconnectors, i, start, debug_flag):
    """Add predispatch region and interconnector record from PREDISPATCHIS file.

    Args:
        regions (dict): dictionary of regions
        interconnectors (dict): dictionary
        i (int): interval number
        start (datetime.datetime): start datetime
        debug_flag (bool): used to debug or not

    Returns:
        Solution: solution instance
    """
    solution = None
    dispatch_dir = preprocess.download_predispatch(start)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGION_SOLUTION' and int(row[7]) == i + 1 and row[8] == intervention:  # 7: Period ID; 8: Intervention flag
                region = regions[row[6]]
                region.total_demand = float(row[9])
                if debug_flag:
                    region.available_generation_record = float(row[10])
                    region.available_load_record = float(row[11])
                    region.dispatchable_generation_record = float(row[13])
                    region.dispatchable_load_record = float(row[14])
                    region.net_interchange_record = float(row[15])
                    region.fcas_local_dispatch_record['LOWER5MIN'] = float(row[19])
                    region.fcas_local_dispatch_record['LOWER60SEC'] = float(row[27])
                    region.fcas_local_dispatch_record['LOWER6SEC'] = float(row[35])
                    region.fcas_local_dispatch_record['RAISE5MIN'] = float(row[43])
                    region.fcas_local_dispatch_record['RAISE60SEC'] = float(row[51])
                    region.fcas_local_dispatch_record['RAISE6SEC'] = float(row[59])
                    region.fcas_local_dispatch_record['LOWERREG'] = float(row[70])
                    region.fcas_local_dispatch_record['RAISEREG'] = float(row[74])
                    region.uigf_record = float(row[106])
            elif debug_flag and row[0] == 'D' and row[2] == 'REGION_PRICES' and int(row[7]) == i + 1 and row[8] == intervention:
                region = regions[row[6]]
                region.rrp_record = float(row[9])
                region.fcas_rrp_record['RAISE6SEC'] = float(row[29])
                region.fcas_rrp_record['RAISE60SEC'] = float(row[30])
                region.fcas_rrp_record['RAISE5MIN'] = float(row[31])
                region.fcas_rrp_record['RAISEREG'] = float(row[32])
                region.fcas_rrp_record['LOWER6SEC'] = float(row[33])
                region.fcas_rrp_record['LOWER60SEC'] = float(row[34])
                region.fcas_rrp_record['LOWER5MIN'] = float(row[35])
                region.fcas_rrp_record['LOWERREG'] = float(row[36])
            elif debug_flag and row[0] == 'D' and row[2] == 'CASE_SOLUTION':
                solution = Solution()
                # solution.intervention = row[6]
                # solution.case_subtype = row[7]
                solution.solution_status = int(row[6])
                solution.spd_version = row[7]
                solution.non_physical_losses = int(row[8])
                solution.total_objective = float(row[9])
                solution.violations['total_area_gen_violation'] = float(row[10])
                solution.violations['total_interconnector_violation'] = float(row[11])
                solution.violations['total_generic_violation'] = float(row[12])
                solution.violations['total_ramp_rate_violation'] = float(row[13])
                solution.violations['total_unit_mw_capacity_violation'] = float(row[14])
                solution.violations['total_5min_violation'] = float(row[15]) if row[15] != '' else 0
                solution.violations['total_reg_violation'] = float(row[16]) if row[16] != '' else 0
                solution.violations['total_6sec_violation'] = float(row[17]) if row[17] != '' else 0
                solution.violations['total_60sec_violation'] = float(row[18]) if row[18] != '' else 0
                solution.violations['total_as_profile_violation'] = float(row[19])
                # solution.violations['total_fast_start_violation'] = float(row[22])
                solution.violations['total_energy_constr_violation'] = float(row[20])
                solution.violations['total_energy_offer_violation'] = float(row[21])
                solution.total_violation = sum(solution.violations.values())
            elif row[0] == 'D' and row[2] == 'INTERCONNECTOR_SOLN' and int(row[7]) == i + 1 and row[8] == intervention:
                ic = interconnectors[row[6]]
                ic.metered_mw_flow = float(row[9])
                ic.mw_flow_record = float(row[10])
                if debug_flag:
                    ic.mw_losses_record = float(row[11])
                    ic.marginal_value_record = float(row[12])
                    ic.violation_degree_record = float(row[13])
                    ic.export_limit_record = float(row[16])
                    ic.import_limit_record = float(row[17])
                    ic.marginal_loss_record = float(row[18])
                    ic.fcas_export_limit_record = float(row[21])
                    ic.fcas_import_limit_record = float(row[22])
    return solution
                

def add_p5min_record(regions, interconnectors, t, start, debug_flag):
    """Add P5MIN region and interconnector record from P5MIN file.

    Args:
        regions (dict): dictionary of regions
        interconnectors (dict): dictionary of interconnectors
        t (datetime.dateime): current datetime
        start (datetime.datetime): start datetime

    Returns:
        Solution: solution instance
    """
    solution = None
    dispatch_dir = preprocess.download_5min_predispatch(start)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and default.extract_datetime(row[6]) == t and row[5] == intervention:
                region = regions[row[7]]
                region.total_demand = float(row[27])
                if debug_flag:
                    region.rrp_record = float(row[8])
                    region.rop_record = float(row[9])
                    region.fcas_rrp_record['RAISE6SEC'] = float(row[11])
                    region.fcas_rrp_record['RAISE60SEC'] = float(row[13])
                    region.fcas_rrp_record['RAISE5MIN'] = float(row[15])
                    region.fcas_rrp_record['RAISEREG'] = float(row[17])
                    region.fcas_rrp_record['LOWER6SEC'] = float(row[19])
                    region.fcas_rrp_record['LOWER60SEC'] = float(row[21])
                    region.fcas_rrp_record['LOWER5MIN'] = float(row[23])
                    region.fcas_rrp_record['LOWERREG'] = float(row[25])
                    region.available_generation_record = float(row[28])
                    region.available_load_record = float(row[29])
                    region.dispatchable_generation_record = float(row[31])
                    region.dispatchable_load_record = float(row[32])
                    region.net_interchange_record = float(row[33])
                    region.fcas_local_dispatch_record['LOWER5MIN'] = float(row[36])
                    region.fcas_local_dispatch_record['LOWER60SEC'] = float(row[41])
                    region.fcas_local_dispatch_record['LOWER6SEC'] = float(row[46])
                    region.fcas_local_dispatch_record['RAISE5MIN'] = float(row[51])
                    region.fcas_local_dispatch_record['RAISE60SEC'] = float(row[56])
                    region.fcas_local_dispatch_record['RAISE6SEC'] = float(row[61])
                    region.fcas_local_dispatch_record['LOWERREG'] = float(row[69])
                    region.fcas_local_dispatch_record['RAISEREG'] = float(row[74])
                    region.uigf_record = float(row[96])
            elif debug_flag and row[0] == 'D' and row[2] == 'CASESOLUTION':
                solution = Solution()
                solution.intervention = row[6]
                solution.total_objective = float(row[7])
                solution.non_physical_losses = int(row[8])
                solution.violations['total_area_gen_violation'] = float(row[9])
                solution.violations['total_interconnector_violation'] = float(row[10])
                solution.violations['total_generic_violation'] = float(row[11])
                solution.violations['total_ramp_rate_violation'] = float(row[12])
                solution.violations['total_unit_mw_capacity_violation'] = float(row[13])
                solution.violations['total_5min_violation'] = float(row[14]) if row[14] != '' else 0
                solution.violations['total_reg_violation'] = float(row[15]) if row[15] != '' else 0
                solution.violations['total_6sec_violation'] = float(row[16]) if row[16] != '' else 0
                solution.violations['total_60sec_violation'] = float(row[17]) if row[17] != '' else 0
                solution.violations['total_as_profile_violation'] = float(row[20])
                solution.violations['total_fast_start_violation'] = float(row[21])
                solution.violations['total_energy_offer_violation'] = float(row[19])
                solution.violations['total_energy_constr_violation'] = float(row[18])
                solution.total_violation = sum(solution.violations.values())
            elif row[0] == 'D' and row[2] == 'INTERCONNECTORSOLN' and default.extract_datetime(row[7]) == t and row[5] == intervention:
                ic = interconnectors[row[6]]
                ic.metered_mw_flow = float(row[8])
                ic.mw_flow_record = float(row[9])
                if debug_flag:
                    ic.mw_losses_record = float(row[10])
                    ic.marginal_value_record = float(row[11])
                    ic.violation_degree_record = float(row[12])
                    ic.export_limit_record = float(row[14])
                    ic.import_limit_record = float(row[15])
                    ic.marginal_loss_record = float(row[16])
                    ic.fcas_export_limit_record = float(row[19])
                    ic.fcas_import_limit_record = float(row[20])
    return solution


def add_dispatch_record(t, start, i, process, problem, fcas_flag, debug_flag):
    if process == 'p5min':
        problem.solution = add_p5min_record(problem.regions, problem.interconnectors, t, start, debug_flag)
    elif process == 'predispatch':
        problem.solution = add_predispatch_record(problem.regions, problem.interconnectors, i, start, debug_flag)
    else:
        problem.solution = add_dispatchis_record(problem.regions, problem.interconnectors, t, fcas_flag, debug_flag)



def add_link_record(ic, blnktas, blnkvic, debug_flag):
    """Add link record from AEMO's record.

    Args:
        ic (Interconnector): Basslink
        blnktas (link): BLINK TAS
        blnkvic (link): BLINK VIC

    Returns:
        None
    """
    if debug_flag:
        if ic.mw_flow_record >= 0:
            blnktas.mw_flow_record = ic.mw_flow_record
            blnkvic.mw_flow_record = 0
        else:
            blnktas.mw_flow_record = 0
            blnkvic.mw_flow_record = - ic.mw_flow_record
    if ic.metered_mw_flow >= 0:
        blnktas.metered_mw_flow = ic.metered_mw_flow
        blnkvic.metered_mw_flow = 0
    else:
        blnktas.metered_mw_flow = 0
        blnkvic.metered_mw_flow = - ic.metered_mw_flow


def get_regions_and_interconnectors(t, start, i, process, problem=None, fcas_flag=True, link_flag=True, dispatchload_record=False, debug_flag=False):
    """Get dictionaries of regions and interconnectors.

    Args:
        t (datetime.datetime): current datetime
        start (datetime.datetime): start datetime
        i (int): interval number
        process (str): process type, 'dispatch', 'p5min', or 'predispatch'
        problem (dispatch.Problem): problem instance
        fcas_flag (bool): consider FCAS or not
        link_flag (bool): consider links or not
        last_prob_id (str): problem ID of last horizon
        dispatchload_flag (bool):
        debug_flag (bool): debug or not

    Returns:
        None
    """
    predefine.add_simplified_interconnector_constraint(problem.interconnectors, t)
    predefine.add_simplified_loss_factor_model(problem.interconnectors, t)
    predefine.add_simplified_loss_model(problem.interconnectors, t)
    predefine.add_simplified_mnsp_interconnector(problem.links, t)
    # add_interconnector_constraint(problem.interconnectors, t)
    # add_loss_factor_model(problem.interconnectors, t)
    # add_loss_model(problem.interconnectors, t)
    # add_mnsp_interconnector(problem.links, t)
    # add_mnsp_bids(problem.links, t)
    add_dispatch_record(t, start, i, process, problem, fcas_flag, debug_flag)
    if link_flag:
        if dispatchload_record and i == 0:
            add_link_record(problem.interconnectors['T-V-MNSP1'], problem.links['BLNKTAS'], problem.links['BLNKVIC'], debug_flag)
