import csv
import datetime
import gurobipy
import logging
import pathlib
import preprocess

log = logging.getLogger(__name__)

# Base directory
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

# Data directory
DATA_DIR = BASE_DIR.joinpath('data')


class Region:
    """Region class.

    Attributes:
        region_id (str): Region identifier
        generators (set): A set of generators' DUID within the region
        loads (set): A set of loads' DUID within the region
        dispatchable_generation (float): Total generation of the region
        dispatchable_load (float): Total loads of the region
        net_mw_flow (float): Net flow into the region
        net_mw_flow_record (float): AEMO record for net flow
        total_demand (float): Total demand of the region at given interval
        dispatchable_generation_record (float): AEMO record for total generation
        dispatchable_load_record (float): AEMO record for total loads
        rrp (float): AEMO record for regional reference price (after adjustments).
        rop (float): AEMO record for regional original price (before adjustments).
        price (float): Regional marginal price
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
        self.generators = set()
        self.loads = set()
        self.dispatchable_generation = 0.0
        self.dispatchable_load = 0.0
        self.net_mw_flow = 0.0
        self.net_mw_flow_record = 0.0
        self.total_demand = None
        self.dispatchable_generation_record = None
        self.dispatchable_load_record = None
        self.rrp = None
        self.rop = None
        self.price = None
        self.available_generation = 0.0
        self.available_load = 0.0
        self.available_generation_record = None
        self.available_load_record = None
        self.net_interchange_record = None
        self.uigf_record = None
        self.losses = 0.0


class Interconnector:
    """Interconnector class.

    Attributes:
        interconnector_id (str): Interconnector identifier
        from_region (str): The region ID interconnector from
        to_region (str): The region ID interconnector to
        forward_cap (int): Forward interconnector nominal capacity
        reverse_cap (int): Reverse interconnector nomial capacity
        mw_flow (float): Target for interconnector flow
        mw_flow_record (float): AEMO record for interconnector flow
        mw_losses (float): Interconnector MW losses
        mw_losses_record (float): AEMO record for MW losses
        marginal_loss_record (float): AEMO record for marginal loss factor
        from_region_loss_share (float): Factor for proportioning of inter-regional losses to regions

    """
    def __init__(self,
                 interconnector_id: str,
                 from_region: str,
                 to_region: str,
                 forward_cap: float,
                 reverse_cap: float,
                 from_region_loss_share: float) -> None:
        self.interconnector_id = interconnector_id
        self.from_region = from_region
        self.to_region = to_region
        self.forward_cap = forward_cap
        self.reverse_cap = reverse_cap
        self.mw_flow = None
        self.mw_flow_record = None
        self.mw_losses = 0.0
        self.mw_losses_record = None
        self.marginal_loss = None
        self.marginal_loss_record = None
        self.from_region_loss_share = from_region_loss_share


def init_regions() -> dict:
    """Initiate the dictionary for regions.

    Returns:
        dict: A dictionary of regions.
    """
    logging.info('Initiate regions.')
    return {'NSW1': Region('NSW1'),
            'QLD1': Region('QLD1'),
            'SA1': Region('SA1'),
            'TAS1': Region('TAS1'),
            'VIC1': Region('VIC1')}


def init_interconnectors() -> dict:
    """Initiate the dictionary for interconnectors.

    Returns:
        dict: A dictionary of interconnectors
    """
    logging.info('Initiate interconnectors.')
    return {'N-Q-MNSP1': Interconnector('N-Q-MNSP1', 'NSW1', 'QLD1', 260, 260, 0.54),
            'NSW1-QLD1': Interconnector('NSW1-QLD1', 'NSW1', 'QLD1', 600, 1078, 0.56),
            'VIC1-NSW1': Interconnector('VIC1-NSW1', 'VIC1', 'NSW1', 2000, 2000, 0.54),
            'T-V-MNSP1': Interconnector('T-V-MNSP1', 'TAS1', 'VIC1', 594, 478, 0.0),
            'V-SA': Interconnector('V-SA', 'VIC1', 'SA1', 500, 300, 0.73),
            'V-S-MNSP1': Interconnector('V-S-MNSP1', 'VIC1', 'SA1', 220, 220, 0.73)}


def calculate_interconnector_losses_v1(regions, interconnectors):
    qd = regions['QLD1'].total_demand
    vd = regions['VIC1'].total_demand
    nd = regions['NSW1'].total_demand
    sd = regions['SA1'].total_demand

    i = interconnectors['NSW1-QLD1']
    # i.mw_losses = (-0.0468 + 3.5206E-06 * nd + 5.3555E-06 * qd) * i.mw_flow + 9.5859E-05 * (i.mw_flow ** 2)
    losses = (-0.0468 + 3.5206E-06 * nd + 5.3555E-06 * qd) * i.mw_flow_record + 9.5859E-05 * (i.mw_flow_record ** 2)
    i.mw_losses = losses
    logging.info('{} Loss record: {} Our calculation: {}'.format(i.interconnector_id, i.mw_losses_record, losses))
    # i.marginal_loss = 0.9532 + 1.9172E-04 * i.mw_flow + 3.5206E-06 * nd + 5.3555E-06 * qd
    # factor = 0.9532 + 1.9172E-04 * i.mw_flow_record + 3.5206E-06 * nd + 5.3555E-06 * qd
    # logging.info('MLF Record: {} Our calculation: {}'.format(i.marginal_loss_record, factor))

    i = interconnectors['VIC1-NSW1']
    # i.mw_losses = (0.0555 - 3.0036E-05 * vd + 7.8643E-06 * nd - 5.4411E-06 * sd) * i.mw_flow + 7.0213E-05 * (i.mw_flow ** 2)
    losses = (0.0555 - 3.0036E-05 * vd + 7.8643E-06 * nd - 5.4411E-06 * sd) * i.mw_flow_record + 7.0213E-05 * (i.mw_flow_record ** 2)
    i.mw_losses = losses
    logging.info('{} Loss record: {} Our calculation: {}'.format(i.interconnector_id, i.mw_losses_record, losses))
    # i.marginal_loss = 1.0555 + 1.4043E-04 * i.mw_flow - 3.0036E-05 * vd + 7.8643E-06 * nd - 5.4411E-06 * sd
    # factor = 1.0555 + 1.4043E-04 * i.mw_flow_record - 3.0036E-05 * vd + 7.8643E-06 * nd - 5.4411E-06 * sd
    # logging.info('MLF Record: {} Our calculation: {}'.format(i.marginal_loss_record, factor))

    i = interconnectors['V-SA']
    # i.mw_losses = (0.0291 + 7.8218E-07 * vd - 2.5868E-05 * sd) * i.mw_flow + 1.8474E-04 * (i.mw_flow ** 2)
    losses = (0.0291 + 7.8218E-07 * vd - 2.5868E-05 * sd) * i.mw_flow_record + 1.8474E-04 * (i.mw_flow_record ** 2)
    i.mw_losses = losses
    logging.info('{} Loss record: {} Our calculation: {}'.format(i.interconnector_id, i.mw_losses_record, losses))
    # i.marginal_loss = 1.0291 + 3.6949E-04 * i.mw_flow + 7.8218E-07 * vd - 2.5868E-05 * sd
    # factor = 1.0291 + 3.6949E-04 * i.mw_flow_record + 7.8218E-07 * vd - 2.5868E-05 * sd
    # logging.info('MLF Record: {} Our calculation: {}'.format(i.marginal_loss_record, factor))

    i = interconnectors['T-V-MNSP1']
    i.mw_losses = i.mw_losses_record

    i = interconnectors['V-S-MNSP1']
    # i.mw_losses = -0.0298 * i.mw_flow + 1.1435E-03 * (i.mw_flow ** 2)
    losses = -0.0298 * i.mw_flow_record + 1.1435E-03 * (i.mw_flow_record ** 2)
    i.mw_losses = losses
    logging.info('{} Loss record: {} Our calculation: {}'.format(i.interconnector_id, i.mw_losses_record, losses))
    # i.marginal_loss = 0.9702 + 2.2869E-03 * i.mw_flow
    # factor = 0.9702 + 2.2869E-03 * i.mw_flow_record
    # logging.info('MLF Record: {} Our calculation: {}'.format(i.marginal_loss_record, factor))

    i = interconnectors['N-Q-MNSP1']
    # i.mw_losses = 0.0289 * i.mw_flow + 8.9620E-04 * (i.mw_flow ** 2)
    losses = 0.0289 * i.mw_flow_record + 8.9620E-04 * (i.mw_flow_record ** 2)
    i.mw_losses = losses
    logging.info('{} Loss record: {} Our calculation: {}'.format(i.interconnector_id, i.mw_losses_record, losses))
    # i.marginal_loss = 1.0289 + 1.7924E-03 * i.mw_flow
    # factor = 1.0289 + 1.7924E-03 * i.mw_flow_record
    # logging.info('MLF Record: {} Our calculation: {}'.format(i.marginal_loss_record, factor))


def calculate_interconnector_losses(model, regions, interconnectors):
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

    i = interconnectors['VIC1-NSW1']
    x_s = range(-i.reverse_cap, i.forward_cap + 1)
    y_s = [(0.0657 - 3.1523E-05 * vd + 2.1734E-05 * nd - 6.5967E-05 * sd) * x_i + 8.5133E-05 * (x_i ** 2) for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(i.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(i.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))

    i = interconnectors['V-SA']
    x_s = range(-i.reverse_cap, i.forward_cap + 1)
    y_s = [(0.0138 + 1.3598E-06 * vd - 1.3290E-05 * sd) * x_i + 1.4761E-04 * (x_i ** 2) for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(i.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(i.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))

    i = interconnectors['V-S-MNSP1']
    x_s = range(-i.reverse_cap, i.forward_cap + 1)
    y_s = [-0.1067 * x_i + 9.0595E-04 * (x_i ** 2) for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(i.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(i.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))

    i = interconnectors['N-Q-MNSP1']
    x_s = range(-i.reverse_cap, i.forward_cap + 1)
    y_s = [0.0331 * x_i + 1.3042E-03 * (x_i ** 2) for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(i.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(i.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))

    i = interconnectors['T-V-MNSP1']
    # x_s = range(-i.reverse_cap, i.forward_cap + 1)
    # y_s = [(0.061 - 3.0201E-05 * vd + 2.147E-05 * nd - 6.6377E-05 * sd) * x_i + 8.634E-05 * (x_i ** 2) for x_i in x_s]
    # lambda_s = [model.addVar(lb=0.0) for i in x_s]
    # model.addConstr(i.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    # i.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    # model.addConstr(i.mw_losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    i.mw_losses = i.mw_losses_record


def get_regions_and_interconnectors(t: datetime) -> (dict, dict, float):
    """Extract required information from dispatch summary file.

    Args:
        t(datetime): Case datetime

    Returns:
        dict: Region dictionary
        dict: Interconnector dictionary
        float: AEMO record for objective total_cleared
    """
    regions = init_regions()
    interconnectors = init_interconnectors()
    dispatch_dir = preprocess.download_dispatch_summary(t)
    logging.info('Read dispatch summary.')
    with dispatch_dir.open() as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSUM':
                region = regions[row[6]]
                region.total_demand = float(row[9])
                region.available_generation_record = float(row[10])
                region.available_load_record = float(row[11])
                region.dispatchable_generation_record = float(row[13])
                region.dispatchable_load_record = float(row[14])
                region.net_interchange_record = float(row[15])
                region.uigf_record = float(row[106])
            elif row[0] == 'D' and row[2] == 'PRICE':
                regions[row[6]].rrp = float(row[9])
                regions[row[6]].rop = float(row[11])
            elif row[0] == 'D' and row[2] == 'CASE_SOLUTION':
                obj_record = float(row[11])
            elif row[0] == 'D' and row[2] == 'INTERCONNECTORRES':
                interconnector = interconnectors[row[6]]
                interconnector.mw_flow_record = float(row[10])
                interconnector.mw_losses_record = float(row[11])
                interconnector.marginal_loss_record = float(row[17])
    return regions, interconnectors, obj_record


