import csv
import gurobipy
import logging
import pathlib

log = logging.getLogger(__name__)

# Base directory
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

# Result directory
OUT_DIR = BASE_DIR.joinpath('out')


def generate_result_csv(ramp_rate, interval_datetime, obj_value, obj_record, interconnectors, regions):
    """Write the dispatch results into a csv file.

    Args:
        interval_datetime (str): Interval datetime
        obj_value (float): Objective value
        obj_record (float: AEMO objective value
        interconnectors (dict): Interconnector dictionary
        regions (dict): Region dictionary

    Returns:
        None

    """
    if ramp_rate:
        result_dir = OUT_DIR.joinpath('results-ramp-rate.csv')
    else:
        result_dir = OUT_DIR.joinpath('results-basic.csv')
    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')

        writer.writerow([interval_datetime])
        writer.writerow(['Item', 'ID', 'Our Value', 'AEMO Value'])
        writer.writerow(['Objective', '', obj_value, obj_record])

        for name, interconnector in interconnectors.items():
            writer.writerow(['Interconnector', name, interconnector.mwflow.x, interconnector.mwflow_record])

        for name, region in regions.items():
            writer.writerow(['Net Interchange (into)', name, region.net_interchange.getValue(), region.net_interchange_record])

        for name, region in regions.items():
            writer.writerow(['Generation', name, region.dispatchable_generation.getValue(), region.dispatchable_generation_record])

        for name, region in regions.items():
            if region.dispatchable_load == 0:
                writer.writerow(['Load', name, 0, region.dispatchable_load_record])
            else:
                writer.writerow(['Load', name, region.dispatchable_load.getValue(), region.dispatchable_load_record])

        for name, region in regions.items():
            writer.writerow(['Price', name, region.price, region.rrp])
