import csv
import datetime
import gurobipy
import logging
import pathlib
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
    def __init__(self, row):
        self.intervention = row[6]
        self.case_subtype = row[7]
        self.solution_status = int(row[8])
        self.spd_version = row[9]
        self.non_physical_losses = int(row[10])
        self.total_objective = float(row[11])
        self.total_area_gen_violation = float(row[12])
        self.total_interconnector_violation = float(row[13])
        self.total_generic_violation = float(row[14])
        self.total_ramp_rate_violation = float(row[15])
        self.total_unit_mw_capacity_violation = float(row[16])
        self.total_5min_violation = float(row[17]) if row[17] != '' else ''
        self.total_reg_violation = float(row[18]) if row[18] != '' else ''
        self.total_6sec_violation = float(row[19]) if row[19] != '' else ''
        self.total_60sec_violation = float(row[20]) if row[20] != '' else ''
        self.total_as_profile_violation = float(row[21])
        self.total_fast_start_violation = float(row[22])
        self.total_energy_offer_violation = float(row[23])


class Region:
    """Region class.

    Attributes:
        region_id (str): Region identifier
        # generators (set): A set of generators' DUID within the region
        # loads (set): A set of loads' DUID within the region
        dispatchable_generation (float): Total generation of the region
        dispatchable_load (float): Total loads of the region
        net_mw_flow (float): Net flow into the region
        net_mw_flow_record (float): AEMO record for net flow
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
    def __init__(self, region_id):
        self.region_id = region_id
        # self.generators = set()
        # self.loads = set()
        self.dispatchable_generation = 0.0
        self.dispatchable_generation_temp = 0.0
        self.dispatchable_load = 0.0
        self.dispatchable_load_temp = 0.0
        self.net_mw_flow = 0.0
        self.net_mw_flow_record = 0.0
        self.total_demand = None
        self.dispatchable_generation_record = None
        self.dispatchable_load_record = None
        self.fcas_local_dispatch = {}
        self.fcas_local_dispatch_temp = {
            'RAISEREG': 0,
            'RAISE6SEC': 0,
            'RAISE60SEC': 0,
            'RAISE5MIN': 0,
            'LOWERREG': 0,
            'LOWER6SEC': 0,
            'LOWER60SEC': 0,
            'LOWER5MIN': 0
        }
        self.fcas_local_dispatch_record_temp = {
            'RAISEREG': 0,
            'RAISE6SEC': 0,
            'RAISE60SEC': 0,
            'RAISE5MIN': 0,
            'LOWERREG': 0,
            'LOWER6SEC': 0,
            'LOWER60SEC': 0,
            'LOWER5MIN': 0
        }
        self.fcas_local_dispatch_record = {}
        # self.lower5min_local_dispatch = 0.0
        # self.lower60sec_local_dispatch = 0.0
        # self.lower6sec_local_dispatch = 0.0
        # self.raise5min_local_dispatch = 0.0
        # self.raise60sec_local_dispatch = 0.0
        # self.raise6sec_local_dispatch = 0.0
        # self.lowerreg_local_dispatch = 0.0
        # self.raisereg_local_dispatch = 0.0
        # self.lower5min_local_dispatch_record = None
        # self.lower60sec_local_dispatch_record = None
        # self.lower6sec_local_dispatch_record = None
        # self.raise5min_local_dispatch_record = None
        # self.raise60sec_local_dispatch_record = None
        # self.raise6sec_local_dispatch_record = None
        # self.lowerreg_local_dispatch_record = None
        # self.raisereg_local_dispatch_record = None
        self.rrp = None
        self.rrp_record = None
        self.rop_record = None
        self.fcas_rrp = {}
        self.fcas_rrp_record = {}
        # self.raise6sec_rrp = None
        # self.raise6sec_rrp_record = None
        # self.raise60sec_rrp = None
        # self.raise60sec_rrp_record = None
        # self.raise5min_rrp = None
        # self.raise5min_rrp_record = None
        # self.raisereg_rrp = None
        # self.raisereg_rrp_record = None
        # self.lower6sec_rrp = None
        # self.lower6sec_rrp_record = None
        # self.lower60sec_rrp = None
        # self.lower60sec_rrp_record = None
        # self.lower5min_rrp = None
        # self.lower5min_rrp_record = None
        # self.lowerreg_rrp = None
        # self.lowerreg_rrp_record = None
        self.available_generation = 0.0
        self.available_load = 0.0
        self.available_generation_record = None
        self.available_load_record = None
        self.net_interchange_record = None
        self.uigf_record = None
        self.losses = 0.0
        self.losses_record = 0.0
        self.offset = 0


def init_regions():
    """Initiate the dictionary for regions.

    Returns:
        dict: A dictionary of regions.
    """
    # logging.info('Initiate regions.')
    return {'NSW1': Region('NSW1'),
            'QLD1': Region('QLD1'),
            'SA1': Region('SA1'),
            'TAS1': Region('TAS1'),
            'VIC1': Region('VIC1')}


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
        self.interconnector_id = interconnector_id
        self.region_from = region_from
        self.region_to = region_to
        # Interconnector constraint
        self.from_region_loss_share = None
        self.max_mw_in = None
        self.max_mw_out = None
        self.loss_constant = None
        self.loss_flow_coefficient = None
        self.import_limit = None
        self.export_limit = None
        self.fcas_support_unavailable = None
        self.ic_type = None
        # Loss factor model
        self.demand_coefficient = {}
        # Loss model
        self.mw_breakpoint = {}
        # Dispatch
        self.metered_mw_flow = None
        self.mw_flow = None
        self.mw_flow_record = None
        self.mw_losses = 0.0
        self.mw_losses_record = None
        self.marginal_value_record = None
        self.violation_degree_record = None
        self.export_limit_record = None
        self.import_limit_record = None
        self.marginal_loss = None
        self.marginal_loss_record = None
        self.fcas_export_limit_record = None
        self.fcas_import_limit_record = None


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
    # logging.info('Read interconnector constraint.')
    with ic_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and preprocess.extract_datetime(row[6]) <= t:
                ic = interconnectors.get(row[8])
                if ic:
                    ic.from_region_loss_share = float(row[5])
                    ic.max_mw_in = float(row[9])
                    ic.max_mw_out = float(row[10])
                    ic.loss_constant = float(row[11])
                    ic.loss_flow_coefficient = float(row[12])
                    ic.import_limit = int(row[17])
                    ic.export_limit = int(row[18])
                    ic.fcas_support_unavailable = int(row[24])
                    ic.ic_type = row[25]


def add_loss_factor_model(interconnectors, t):
    lfm_dir = preprocess.download_dvd_data('LOSSFACTORMODEL', t)
    # logging.info('Read loss factor model.')
    with lfm_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and preprocess.extract_datetime(row[4]) <= t:
                ic = interconnectors.get(row[6])
                if ic:
                    ic.demand_coefficient[row[7]] = float(row[8])


def add_loss_model(interconnectors, t):
    lm_dir = preprocess.download_dvd_data('LOSSMODEL', t)
    # logging.info('Read loss model.')
    with lm_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and preprocess.extract_datetime(row[4]) <= t:
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
        self.mw_flow = None
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
    mi_dir = preprocess.download_dvd_data('MNSP_INTERCONNECTOR', t)
    # logging.info('Read MNSP interconnector.')
    with mi_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and preprocess.extract_datetime(row[5]) <= t:
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
    mnsp_dir = preprocess.download_mnsp_bids(t)
    with mnsp_dir.open() as f:
        reader = csv.reader(f)
        # logging.info('Read MNSP bids.')
        for row in reader:
            if row[0] == 'D':
                if row[2] == 'DAILY':
                    link = links[row[4]]
                    link.price_band = [float(price) for price in row[12:22]]
                elif row[2] == 'PERIOD' and preprocess.ZERO <= preprocess.extract_datetime(row[9]) - t < preprocess.THIRTY_MIN:
                    link = links[row[4]]
                    link.max_avail = int(row[10])
                    link.band_avail = [int(avail) for avail in row[12:22]]
                    link.ramp_up_rate = int(row[22])


def get_links(t):
    links = init_links()
    add_mnsp_interconnector(links, t)
    add_mnsp_bids(links, t)
    return links


def nonlinear_calculate_interconnector_losses(model, regions, interconnectors, links):
    qd = regions['QLD1'].total_demand
    vd = regions['VIC1'].total_demand
    nd = regions['NSW1'].total_demand
    sd = regions['SA1'].total_demand

    i = interconnectors['NSW1-QLD1']
    x_s = range(-i.reverse_cap, i.forward_cap + 1)
    y_s = [(-0.0471 + 1.0044E-05 * qd - 3.5146E-07 * nd) * x_i + 9.8083E-05 * (x_i ** 2) for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(i.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(i.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    model.addConstr(sum(lambda_s) == 1)
    model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)

    i = interconnectors['VIC1-NSW1']
    x_s = range(-i.reverse_cap, i.forward_cap + 1)
    y_s = [(0.0657 - 3.1523E-05 * vd + 2.1734E-05 * nd - 6.5967E-05 * sd) * x_i + 8.5133E-05 * (x_i ** 2) for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(i.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(i.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    model.addConstr(sum(lambda_s) == 1)
    model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)

    i = interconnectors['V-SA']
    x_s = range(-i.reverse_cap, i.forward_cap + 1)
    y_s = [(0.0138 + 1.3598E-06 * vd - 1.3290E-05 * sd) * x_i + 1.4761E-04 * (x_i ** 2) for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(i.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(i.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    model.addConstr(sum(lambda_s) == 1)
    model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)

    i = interconnectors['V-S-MNSP1']
    x_s = range(-i.reverse_cap, i.forward_cap + 1)
    y_s = [-0.1067 * x_i + 9.0595E-04 * (x_i ** 2) for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(i.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(i.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    model.addConstr(sum(lambda_s) == 1)
    model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)

    i = interconnectors['N-Q-MNSP1']
    x_s = range(-i.reverse_cap, i.forward_cap + 1)
    y_s = [0.0331 * x_i + 1.3042E-03 * (x_i ** 2) for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(i.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(i.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    model.addConstr(sum(lambda_s) == 1)
    model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)

    i = interconnectors['T-V-MNSP1']
    model.addConstr(i.mw_flow == links['BLNKVIC'].mw_flow + links['BLNKTAS'].mw_flow)

    # model.addConstr(i.mw_flow == i.mw_flow_record)

    link = links['BLNKVIC']
    x_s = range(link.max_cap + 1)
    y_s = [-3.92E-03 * x_i + 1.0393E-04 * (x_i ** 2) + 4 for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(link.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    link.losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(link.losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    model.addConstr(sum(lambda_s) == 1)
    model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)
    regions[link.from_region].losses += (1 - link.from_region_tlf) * (link.mw_flow + link.losses)
    regions[link.to_region].losses += (1 - link.to_region_tlf) * link.mw_flow

    link = links['BLNKTAS']
    x_s = range(-link.max_cap, 1)
    y_s = [-3.92E-03 * x_i + 1.0393E-04 * (x_i ** 2) + 4 for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(link.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    link.losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(link.losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    model.addConstr(sum(lambda_s) == 1)
    model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)
    regions[link.from_region].losses += (1 - link.from_region_tlf) * (link.mw_flow + link.losses)
    regions[link.to_region].losses += (1 - link.to_region_tlf) * link.mw_flow

    model.addSOS(gurobipy.GRB.SOS_TYPE1, [links['BLNKVIC'].mw_flow, links['BLNKTAS'].mw_flow])
    i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(i.mw_losses == links['BLNKVIC'].losses + links['BLNKTAS'].losses - 8)

    for interconnector in interconnectors.values():
        if interconnector.interconnector_id == 'T-V-MNSP1':
            if interconnector.metered_mw_flow >= 0:
                regions['TAS1'].losses += interconnector.mw_losses
            else:
                regions['VIC1'].losses += interconnector.mw_losses
        else:
            regions[interconnector.from_region].losses += interconnector.mw_losses * interconnector.from_region_loss_share
            regions[interconnector.to_region].losses += interconnector.mw_losses * (1 - interconnector.from_region_loss_share)


def sos_calculate_interconnector_losses(model, regions, interconnectors, links=None):
    for ic in interconnectors.values():
        coefficient = ic.loss_constant - 1
        for region_id, dc in ic.demand_coefficient.items():
            coefficient += regions[region_id].total_demand * dc

        x_s = sorted(ic.mw_breakpoint.values())
        y_s = [0.5 * ic.loss_flow_coefficient * x * x + coefficient * x for x in x_s]
        ic.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY, name='Mw_Losses_{}'.format(ic.interconnector_id))

        lambda_s = [model.addVar(lb=0.0) for i in x_s]
        model.addConstr(ic.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
        model.addConstr(ic.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
        model.addConstr(sum(lambda_s) == 1)
        model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)
        share_losses(regions, ic)


def calculate_interconnector_losses(model, regions, interconnectors):
    for ic in interconnectors.values():
        coefficient = ic.loss_constant - 1
        for region_id, dc in ic.demand_coefficient.items():
            coefficient += regions[region_id].total_demand * dc

        x_s = sorted(ic.mw_breakpoint.values())
        y_s = [0.5 * ic.loss_flow_coefficient * x * x + coefficient * x for x in x_s]
        ic.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY, name='Mw_Losses_{}'.format(ic.interconnector_id))

        for i in range(len(x_s) - 1):
            model.addConstr((ic.mw_losses - y_s[i]) * (x_s[i + 1] - x_s[i]) >= (y_s[i + 1] - y_s[i]) * (ic.mw_flow - x_s[i]), 'LOSSES_{}'.format(ic.interconnector_id))
            if (ic.mw_losses_record - y_s[i]) * (x_s[i + 1] - x_s[i]) < (y_s[i + 1] - y_s[i]) * (ic.mw_flow_record - x_s[i]):
                logging.warning('IC {} violate losses constraint'.format(ic.interconnector_id))
        share_losses(regions, ic)


def share_losses(regions, ic):
    if ic.interconnector_id == 'T-V-MNSP1':
        if ic.metered_mw_flow >= 0:
            regions['TAS1'].losses += ic.mw_losses
            regions['TAS1'].losses_record += ic.mw_losses_record
        else:
            regions['VIC1'].losses += ic.mw_losses
            regions['VIC1'].losses_record += ic.mw_losses_record
    else:
        regions[ic.region_from].losses += ic.mw_losses * ic.from_region_loss_share
        regions[ic.region_to].losses += ic.mw_losses * (1 - ic.from_region_loss_share)
        regions[ic.region_from].losses_record += ic.mw_losses_record * ic.from_region_loss_share
        regions[ic.region_to].losses_record += ic.mw_losses_record * (1 - ic.from_region_loss_share)


def add_dispatchis_record(regions, interconnectors, t, fcas_flag):
    dispatch_dir = preprocess.download_dispatch_summary(t)
    # logging.info('Read dispatch summary.')
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSUM' and row[8] == intervention:
                region = regions[row[6]]
                region.total_demand = float(row[9])
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
            elif row[0] == 'D' and row[2] == 'PRICE' and row[8] == intervention:
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
            elif row[0] == 'D' and row[2] == 'CASE_SOLUTION':
                solution = Solution(row)
            elif row[0] == 'D' and row[2] == 'INTERCONNECTORRES' and row[8] == intervention:
                interconnector = interconnectors[row[6]]
                interconnector.metered_mw_flow = float(row[9])
                interconnector.mw_flow_record = float(row[10])
                interconnector.mw_losses_record = float(row[11])
                interconnector.marginal_value_record = float(row[12])
                interconnector.violation_degree_record = float(row[13])
                interconnector.export_limit_record = float(row[15])
                interconnector.import_limit_record = float(row[16])
                interconnector.marginal_loss_record = float(row[17])
    return solution


def add_predispatch_record(regions, interconnectors, i, start):
    dispatch_dir = preprocess.download_predispatch(start)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGION_SOLUTION' and int(row[7]) == i + 1 and row[8] == intervention:  # 7: Period ID; 8: Intervention flag
                region = regions[row[6]]
                region.total_demand = float(row[9])
            elif row[0] == 'D' and row[2] == 'REGION_PRICES' and int(row[7]) == i + 1 and row[8] == intervention:
                region = regions[row[6]]
                region.rrp_record = float(row[9])
                # region.rop_record = float(row[])  # Note: Predispatch doesn't have ROP
            # elif row[0] == 'D' and row[2] == 'CASE_SOLUTION':
            #     solution = Solution(row[:5] + [None, row[23], None] + row[5:])
            elif row[0] == 'D' and row[2] == 'INTERCONNECTOR_SOLN' and int(row[7]) == i + 1 and row[8] == intervention:
                ic = interconnectors[row[6]]
                ic.metered_mw_flow = float(row[9])
                ic.mw_flow_record = float(row[10])
                ic.mw_losses_record = float(row[11])
                ic.marginal_value_record = float(row[12])
                ic.violation_degree_record = float(row[13])
                ic.export_limit_record = float(row[16])
                ic.import_limit_record = float(row[17])
                ic.marginal_loss_record = float(row[18])
                ic.fcas_export_limit_record = float(row[21])
                ic.fcas_import_limit_record = float(row[22])
    return None
                

def add_p5min_record(regions, interconnectors, t, start):
    dispatch_dir = preprocess.download_5min_predispatch(start)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and preprocess.extract_datetime(row[6]) == t and row[5] == intervention:
                region = regions[row[7]]
                region.rrp_record = float(row[8])
                region.rop_record = float(row[9])
                region.total_demand = float(row[27])
            # elif row[0] == 'D' and row[2] == 'CASESOLUTION':
            #     solution = Solution(row[:7] + [None, None, None, row[8], row[7]] + row[9:])
            elif row[0] == 'D' and row[2] == 'INTERCONNECTORSOLN' and preprocess.extract_datetime(row[7]) == t and row[5] == intervention:
                ic = interconnectors[row[6]]
                ic.metered_mw_flow = float(row[8])
                ic.mw_flow_record = float(row[9])
                ic.mw_losses_record = float(row[10])
                ic.marginal_value_record = float(row[11])
                ic.violation_degree_record = float(row[12])
                ic.export_limit_record = float(row[14])
                ic.import_limit_record = float(row[15])
                ic.marginal_loss_record = float(row[16])
                ic.fcas_export_limit_record = float(row[19])
                ic.fcas_import_limit_record = float(row[20])
    return None


def add_link_record(ic, blnktas, blnkvic):
    if ic.mw_flow_record >= 0:
        blnktas.mw_flow_record = ic.mw_flow_record
        blnkvic.mw_flow_record = 0
        blnktas.metered_mw_flow = ic.metered_mw_flow
        blnkvic.metered_mw_flow = 0
    else:
        blnktas.mw_flow_record = 0
        blnkvic.mw_flow_record = - ic.mw_flow_record
        blnktas.metered_mw_flow = 0
        blnkvic.metered_mw_flow = - ic.metered_mw_flow


def get_regions_and_interconnectors(t, start, i, process, fcas_flag, link_flag):
    """Extract required information from dispatch summary file.

    Args:
        t(datetime.datetime): Case datetime

    Returns:
        (dict, dict, float): Region dictionary, Interconnector dictionary, AEMO record for objective total_cleared

    """
    regions = init_regions()
    interconnectors = init_interconnectors()
    links = get_links(t) if link_flag else None
    add_interconnector_constraint(interconnectors, t)
    add_loss_factor_model(interconnectors, t)
    add_loss_model(interconnectors, t)
    if process == 'dispatch':
        solution = add_dispatchis_record(regions, interconnectors, t, fcas_flag)
    elif process == 'predispatch':
        solution = add_predispatch_record(regions, interconnectors, i, start)
    else:
        solution = add_p5min_record(regions, interconnectors, t, start)
    if link_flag:
        add_link_record(interconnectors['T-V-MNSP1'], links['BLNKTAS'], links['BLNKVIC'])
    return regions, interconnectors, solution, links


def main():
    t = datetime.datetime(2019, 9, 29, 4, 10, 0)
    regions, interconnectors, solution, links = get_regions_and_interconnectors(t, t, 0, 'dispatch', True)
    model = gurobipy.Model('losses')

    for ic_id, ic in interconnectors.items():
        # Define interconnector MW flow
        ic.mw_flow = model.addVar(lb=-gurobipy.GRB.INFINITY, name='Mw_Flow_{}'.format(ic_id))

        ic.import_limit_constr = model.addConstr(ic.mw_flow >= -ic.import_limit, 'IMPORT_LIMIT_{}'.format(ic_id))
        ic.export_limit_constr = model.addConstr(ic.mw_flow <= ic.export_limit, 'EXPORT_LIMIT_{}'.format(ic_id))

        # Allocate inter-flow to regions
        regions[ic.region_to].net_mw_flow_record += ic.mw_flow_record
        regions[ic.region_from].net_mw_flow_record -= ic.mw_flow_record
        regions[ic.region_to].net_mw_flow += ic.mw_flow
        regions[ic.region_from].net_mw_flow -= ic.mw_flow

        model.addConstr(ic.mw_flow == ic.mw_flow_record, 'FIXED_INTERFLOW_{}'.format(ic_id))

    calculate_interconnector_losses(model, regions, interconnectors)
    model.optimize()

    for ic_id, ic in interconnectors.items():
        print('{} losses record {} but calculate {}'.format(ic_id, ic.mw_losses_record, ic.mw_losses.x))


def test():
    t = datetime.datetime(2019, 9, 29, 4, 5, 0)
    regions, interconnectors, solution, links = get_regions_and_interconnectors(t, t, 0, 'dispatch', True)
    for ic_id, ic in interconnectors.items():
        # print('{} flow {} losses {}'.format(ic_id, ic.mw_flow_record, ic.mw_losses_record))
        # print('from {} flow {} * factor {} = losses {} to flow {} * factor {} = losses {}'.format(ic.region_from,
        #                                                                                           -ic.mw_flow_record,
        #                                                                                           ic.from_region_loss_share,
        #                                                                                           ic.mw_losses_record*ic.from_region_loss_share,
        #                                                                                           ic.region_to,
        #                                                                                           ic.mw_flow_record,
        #                                                                                           1-ic.from_region_loss_share,
        #                                                                                           ic.mw_losses_record*(1-ic.from_region_loss_share)))


        if ic.interconnector_id == 'T-V-MNSP1':
            if ic.metered_mw_flow >= 0:
                print('metered>0')
                regions['TAS1'].losses_record += ic.mw_losses_record
            else:
                print('metered<0')
                # regions['VIC1'].losses_record += ic.mw_losses_record
                regions['VIC1'].losses_record += ic.mw_losses_record
            if ic.mw_flow_record > 0:
                print('flow>0')
                links['BLNKTAS'].mw_flow = ic.mw_flow_record
                links['BLNKTAS'].losses = ic.mw_losses_record
                links['BLNKVIC'].mw_flow = 0
                links['BLNKVIC'].losses = 0
                # regions['VIC1'].losses_record += (1 - 0.9728) * ic.mw_flow_record
            else:
                print('flow<0')
                links['BLNKTAS'].mw_flow = 0
                links['BLNKTAS'].losses = 0
                links['BLNKVIC'].mw_flow = - ic.mw_flow_record
                links['BLNKVIC'].losses = - ic.mw_losses_record
                # regions['VIC1'].losses_record += (1 - 0.9789) * (ic.mw_losses_record+ic.mw_flow_record)
        else:
            regions[ic.region_to].net_mw_flow_record += ic.mw_flow_record
            regions[ic.region_from].net_mw_flow_record -= ic.mw_flow_record
            regions[ic.region_from].losses_record += ic.mw_losses_record * ic.from_region_loss_share
            regions[ic.region_to].losses_record += ic.mw_losses_record * (1 - ic.from_region_loss_share)

    for link in links.values():
        regions[link.from_region].net_mw_flow_record -= (link.mw_flow) * link.from_region_tlf
        regions[link.to_region].net_mw_flow_record += link.mw_flow * link.to_region_tlf

    for region_id, region in regions.items():
        print('{} record {} flow {} losses {} guess {}'.format(region_id, -region.net_interchange_record, region.net_mw_flow_record, region.losses_record, region.net_mw_flow_record-region.losses_record))
        print('guess {} rhs {} lhs {}'.format(region_id, region.dispatchable_generation_record, region.dispatchable_load_record+region.total_demand+region.net_interchange_record))
        print('verify {} rhs {} lhs {}'.format(region_id, region.dispatchable_generation_record + region.net_mw_flow_record, region.dispatchable_load_record + region.total_demand + region.losses_record))


if __name__ == '__main__':
    main()
    # test()



