import csv
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
        net_interchange (float): Net flow into the region
        total_demand (float): Total demand of the region at given interval
        dispatchable_generation_record (float): AEMO record for total generation
        dispatchable_load_record (float): AEMO record for total generation
        rrp (float): AEMO record of regional reference price
        price (float): Regional marginal price

    """
    def __init__(self, region_id):
        self.region_id = region_id
        self.generators = set()
        self.loads = set()
        self.dispatchable_generation = 0.0
        self.dispatchable_load = 0.0
        self.net_interchange = 0.0
        self.total_demand = 0.0
        self.dispatchable_generation_record = 0.0
        self.dispatchable_load_record = 0.0
        self.rrp = 0.0
        self.price = 0.0


class Interconnector:
    """Interconnector class.

    Attributes:
        interconnector_id (str): Interconnector identifier
        from_region (str): The region ID interconnector from
        to_region (str): The region ID interconnector to
        forward_cap (str): Forward interconnector nominal capacity
        reverse_cap (str): Reverse interconnector nomial capacity

    """
    def __init__(self,
                 interconnector_id: str,
                 from_region: str,
                 to_region: str,
                 forward_cap: float,
                 reverse_cap: float) -> None:
        self.interconnector_id = interconnector_id
        self.from_region = from_region
        self.to_region = to_region
        self.forward_cap = forward_cap
        self.reverse_cap = reverse_cap


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
    return {'N-Q-MNSP1': Interconnector('N-Q-MNSP1', 'NSW1', 'QLD1', 107.0, 210.0),
            'NSW1-QLD1': Interconnector('NSW1-QLD1', 'NSW1', 'QLD1', 600.0, 1078.0),
            'VIC1-NSW1': Interconnector('VIC1-NSW1', 'VIC1', 'NSW1', 1600.0, 1350.0),
            'T-V-MNSP1': Interconnector('T-V-MNSP1', 'TAS1', 'VIC1', 594.0, 478.0),
            'V-SA': Interconnector('V-SA', 'VIC1', 'SA1', 600.0, 500.0),
            'V-S-MNSP1': Interconnector('V-S-MNSP1', 'VIC1', 'SA1', 220.0, 200.0)}


def get_regions_and_interconnectors(case_datetime: str) -> (dict, dict, float):
    """Extract required information from dispatch summary file.

    Args:
        case_datetime (str): Case datetime

    Returns:
        pathlib.Path: The path to downloaded dispatch summary file
    """
    regions = init_regions()
    interconnectors = init_interconnectors()
    dispatch_dir = preprocess.download_dispatch_summary(case_datetime)
    logging.info('Read AEMO dispatch summary.')
    with dispatch_dir.open() as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSUM':
                region = regions[row[6]]
                region.total_demand = float(row[9])
                region.dispatchable_generation_record = float(row[13])
                region.dispatchable_load_record = float(row[14])
                region.net_interchange_record = float(row[15])
            elif row[0] == 'D' and row[2] == 'PRICE':
                regions[row[6]].rrp = float(row[9])
            elif row[0] == 'D' and row[2] == 'CASE_SOLUTION':
                obj_record = float(row[11])
            elif row[0] == 'D' and row[2] == 'INTERCONNECTORRES':
                interconnectors[row[6]].mwflow_record = float(row[10])
    return regions, interconnectors, obj_record