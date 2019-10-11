import csv
# import gurobipy
import logging
# import matplotlib.pyplot as plt
# import pandas as pd
import pathlib
import preprocess

log = logging.getLogger(__name__)

FCAS_TYPES = ['RAISEREG', 'RAISE6SEC', 'RAISE60SEC', 'RAISE5MIN', 'LOWERREG', 'LOWER6SEC', 'LOWER60SEC', 'LOWER5MIN']


def generate_dispatchis(t, regions):
    p = preprocess.OUT_DIR / 'dispatch'
    p.mkdir(parents=True, exist_ok=True)
    result_dir = p / 'DISPATCHIS_{}.csv'.format(preprocess.get_case_datetime(t))

    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['I', 'DISPATCH', 'PRICE', '', 'SETTLEMENTDATE', 'RUNNO', 'REGIONID', 'INTERVENTION', 'RRP', 'RRP Record'])
        for region_id, region in regions.items():
            writer.writerow(['D', 'DISPATCH', 'PRICE', '', preprocess.get_interval_datetime(t), '', region_id, 0, region.rrp, region.rrp_record])


def generate_predispatchis(start, t, i, regions):
    p = preprocess.OUT_DIR / 'predispatch'
    p.mkdir(parents=True, exist_ok=True)
    result_dir = p / 'PREDISPATCHIS_{}.csv'.format(preprocess.get_case_datetime(start))
    with result_dir.open(mode='a+') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['I', 'PREDISPATCH', 'REGION_PRICE', '', 'PREDISPATCHSEQNO', 'RUNNO', 'REGIONID', 'PERIODID', 'INTERVENTION', 'RRP', 'RRP Record'])
        for region_id, region in regions.items():
            writer.writerow(['D',  # 0
                             'PREDISPATCH',
                             'REGION_PRICE',  # 2
                             '', '', '',
                             region_id,  # 6
                             i + 1,
                             0,  # 8
                             region.rrp,  # Column 9
                             region.rrp_record,
                             '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
                             preprocess.get_interval_datetime(t)  # 28
                             ])


def generate_p5min(start, t, regions):
    p = preprocess.OUT_DIR / 'p5min' 
    p.mkdir(parents=True, exist_ok=True)
    result_dir = p / 'P5MIN_{}.csv'.format(preprocess.get_case_datetime(start))
    with result_dir.open(mode='a+') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['I', 'P5MIN', 'REGIONSOLUTION', '', 'RUN_DATETIME', 'INTERVENTION', 'RUNNO', 'REGIONID', 'RRP', 'RRP Record'])
        for region_id, region in regions.items():
            writer.writerow(['D',  # 0
                             'P5MIN',
                             'REGIONSOLUTION',  # 2
                             '',
                             '',
                             0,  # 5
                             preprocess.get_interval_datetime(t),  # 6
                             region_id,  # 7
                             region.rrp,  # 8
                             region.rrp_record
                             ])


def generate_dispatchload(units, t, start, process):
    interval_datetime = preprocess.get_case_datetime(t + preprocess.FIVE_MIN)
    if process == 'dispatch':
        p = preprocess.OUT_DIR / process
        p.mkdir(parents=True, exist_ok=True)
        result_dir = p / 'dispatch_{}.csv'.format(interval_datetime)
    else:
        p = preprocess.OUT_DIR / process / '{}_{}'.format(process, preprocess.get_case_datetime(start))
        p.mkdir(parents=True, exist_ok=True)
        result_dir = p / 'dispatchload_{}.csv'.format(interval_datetime)
    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['I', 'DUID', 'TOTALCLEARED'])
        for duid, unit in units.items():
            # print(unit.total_cleared.x if unit.total_cleared != 0 else 0)
            writer.writerow(['D',  # 0
                             duid,  # 1
                             unit.total_cleared
                             #  0 if unit.total_cleared == 0 else unit.total_cleared.x  # 2
                             ])


def generate_result_csv(fixed_interflow_flag, fixed_target_flag, t, obj_value, obj_record, interconnectors, regions, units):
    """Write the dispatch results into a csv file.

    Args:
        fixed_interflow_flag (bool): Flag for whether fix inter-flow value
        fixed_target_flag (bool): Flag for whether fix unit dispatch target
        t (datetime): Interval datetime
        obj_value (float): Objective total_cleared
        obj_record (float: AEMO objective total_cleared
        interconnectors (dict): Interconnector dictionary
        regions (dict): Region dictionary

    Returns:
        None

    """
    if fixed_interflow_flag:
        result_dir = preprocess.OUT_DIR / 'fixed_interflow_{}.csv'.format(preprocess.get_case_datetime(t))
    elif fixed_target_flag:
        result_dir = preprocess.OUT_DIR / 'fixed_target_{}.csv'.format(preprocess.get_case_datetime(t))
    else:
        result_dir = preprocess.OUT_DIR / 'DISPATCHIS_{}.csv'.format(preprocess.get_case_datetime(t))

    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')

        writer.writerow([preprocess.get_interval_datetime(t)])
        writer.writerow(['Item', 'Our Value', 'AEMO Value'])
        writer.writerow(['Objective', obj_value, obj_record])

        writer.writerow(['Interconnector',
                         'Inter-flow',
                         'AEMO',
                         'Losses',
                         'AEMO'])
        for name, interconnector in interconnectors.items():
            writer.writerow([name,
                             interconnector.mw_flow.x,
                             interconnector.mw_flow_record,
                             interconnector.mw_losses,
                             interconnector.mw_losses_record
                             ])

        row = ['REGIONSUM',
               'Region ID',
               'Generation',
               'AEMO Gen',
               'Load Load',
               'AEMO',
               # 'Available Gen',
               # 'AEMO',
               # 'Available Load',
               # 'AEMO'
               'Net Interchange (into)',
               'AEMO Inter-flow']
        for bid_type in FCAS_TYPES:
            row.append(bid_type)
            row.append('AEMO {}'.format(bid_type))

        writer.writerow(row)
        for name, region in regions.items():
            row = ['REGIONSUM',
                   name,
                   region.dispatchable_generation.getValue(),
                   region.dispatchable_generation_record,
                   region.dispatchable_load.x,
                   region.dispatchable_load_record,
                   # region.available_generation,
                   # region.available_generation_record,
                   # region.available_load,
                   # region.available_load_record
                   region.net_mw_flow.getValue(),
                   region.net_mw_flow_record]

            for bid_type in FCAS_TYPES:
                row.append(region.fcas_local_dispatch[bid_type].getValue())
                row.append(region.fcas_local_dispatch_record[bid_type])
            writer.writerow(row)

        row = ['PRICE',
               'Region ID',
               'Region Reference Price',
               'AEMO RRP'
               ]
        for bid_type in FCAS_TYPES:
            row.append(bid_type)
            row.append('AEMO {}'.format(bid_type))

        writer.writerow(row)
        for name, region in regions.items():
            row = ['PRICE',
                   name,
                   region.rrp,
                   region.rrp_record]

            for bid_type in FCAS_TYPES:
                row.append(region.fcas_rrp[bid_type])
                row.append(region.fcas_rrp_record[bid_type])
            writer.writerow(row)

    # for name, unit in units.items():
    #     if unit.energy is not None:
    #         if unit.total_cleared.x != unit.total_cleared_record:
    #             print('{} our {} AEMO {}'.format(name, unit.total_cleared.x, unit.total_cleared_record))

    # regions_dir = preprocess.OUT_DIR.joinpath('generator_dispatch.csv')
    # with regions_dir.open(mode='w') as regions_file:
    #     writer = csv.writer(regions_file, delimiter=',')
    #     writer.writerow(['DUID', 'Region', 'Fuel Source', 'Our Value', 'AEMO Value', 'Our Value minus AEMO Value'])
    #     for name, region in regions.items():
    #         for duid in region.generators:
    #             genrator = generators[duid]
    #             writer.writerow([duid,
    #                              name,
    #                              genrator.source,
    #                              genrator.total_cleared.getValue(),
    #                              genrator.total_cleared_record,
    #                              genrator.total_cleared.getValue() - genrator.total_cleared_record])
