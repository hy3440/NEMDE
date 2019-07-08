import csv
# import gurobipy
import logging
# import matplotlib.pyplot as plt
# import pandas as pd
import pathlib
import preprocess

log = logging.getLogger(__name__)

# Base directory
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

# Result directory
OUT_DIR = BASE_DIR.joinpath('out')


def generate_result_csv(ramp_flag, loss_flag, t, obj_value, obj_record, interconnectors, regions, generators):
    """Write the dispatch results into a csv file.

    Args:
        ramp_flag (bool): Flag for whether using ramp rate
        loss_flag (bool): Flag for whether calculating inter-regional losses
        interval_datetime (datetime): Interval datetime
        obj_value (float): Objective total_cleared
        obj_record (float: AEMO objective total_cleared
        interconnectors (dict): Interconnector dictionary
        regions (dict): Region dictionary

    Returns:
        None

    """
    if loss_flag:
        result_dir = OUT_DIR.joinpath('results-fixed-interconnector.csv')
    elif ramp_flag:
        result_dir = OUT_DIR.joinpath('results-ramp-rate.csv')
    else:
        result_dir = OUT_DIR.joinpath('results-basic.csv')
    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')

        writer.writerow([preprocess.get_interval_datetime(t)])
        writer.writerow(['Item', 'ID', 'Our Value', 'AEMO Value'])
        writer.writerow(['Objective', '', obj_value, obj_record])

        for name, interconnector in interconnectors.items():
            if loss_flag:
                writer.writerow(['Interconnector', name, interconnector.mw_flow, interconnector.mw_flow_record])
            else:
                writer.writerow(['Interconnector', name, interconnector.mw_flow.x, interconnector.mw_flow_record])

        for name, region in regions.items():
            if loss_flag:
                writer.writerow(['Net Interchange (into)', name, region.net_mw_flow, region.net_mw_flow_record])
            else:
                writer.writerow(['Net Interchange (into)', name, region.net_mw_flow.getValue(), region.net_mw_flow_record])

        for name, region in regions.items():
            writer.writerow(['Generation', name, region.dispatchable_generation.getValue(), region.dispatchable_generation_record])

        for name, region in regions.items():
            if region.dispatchable_load == 0:
                writer.writerow(['Load', name, 0, region.dispatchable_load_record])
            else:
                writer.writerow(['Load', name, region.dispatchable_load.getValue(), region.dispatchable_load_record])

        for name, region in regions.items():
            writer.writerow(['Price', name, region.price, region.rrp])

    regions_dir = OUT_DIR.joinpath('generator_dispatch.csv')
    with regions_dir.open(mode='w') as regions_file:
        writer = csv.writer(regions_file, delimiter=',')
        writer.writerow(['DUID', 'Region', 'Fuel Source', 'Our Value', 'AEMO Value', 'Our Value minus AEMO Value'])
        for name, region in regions.items():
            for duid in region.generators:
                genrator = generators[duid]
                writer.writerow([duid,
                                 name,
                                 genrator.source,
                                 genrator.total_cleared.getValue(),
                                 genrator.total_cleared_record,
                                 genrator.total_cleared.getValue() - genrator.total_cleared_record])
