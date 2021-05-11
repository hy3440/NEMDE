import csv
import default

FCAS_TYPES = ['RAISEREG', 'RAISE6SEC', 'RAISE60SEC', 'RAISE5MIN', 'LOWERREG', 'LOWER6SEC', 'LOWER60SEC', 'LOWER5MIN']


def write_dispatchis(start, t, regions, prices, k=0, path_to_out=default.OUT_DIR):
    p = path_to_out / ('dispatch' if k == 0 else f'dispatch_{k}')
    p.mkdir(parents=True, exist_ok=True)
    result_dir = p / f'DISPATCHIS_{default.get_case_datetime(t)}.csv'

    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['I', 'DISPATCH', 'PRICE', '', 'SETTLEMENTDATE', 'RUNNO', 'REGIONID', 'DISPATCHINTERVAL', 'INTERVENTION', 'RRP', 'RRP Record', 'ROP Record'])
        for region_id, region in regions.items():
            writer.writerow(['D', 'DISPATCH', 'PRICE', '', default.get_interval_datetime(t), '', region_id, '', 0, prices[region_id], region.rrp_record, region.rop_record])


def write_predispatchis(start, t, i, regions, prices, k=0, path_to_out=default.OUT_DIR):
    p = path_to_out / ('predispatch' if k == 0 else f'predispatch_{k}')
    p.mkdir(parents=True, exist_ok=True)
    result_dir = p / f'PREDISPATCHIS_{default.get_case_datetime(start)}.csv'
    with result_dir.open(mode='w' if i == 0 else 'a') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['I', 'PREDISPATCH', 'REGION_PRICE', '', 'PREDISPATCHSEQNO', 'RUNNO', 'REGIONID', 'PERIODID', 'INTERVENTION', 'RRP', 'RRP Record'])
        for region_id, region in regions.items():
            writer.writerow(['D',  # 0
                             'PREDISPATCH',
                             'REGION_PRICES',  # 2
                             '', '', '',
                             region_id,  # 6
                             i + 1,
                             0,  # 8
                             prices[region_id],  # Column 9
                             region.rrp_record,
                             '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
                             default.get_interval_datetime(t)  # 28
                             ])


def write_p5min(start, t, i, regions, prices, k=0, path_to_out=default.OUT_DIR):
    p = path_to_out / ('p5min' if k == 0 else f'p5min_{k}')
    p.mkdir(parents=True, exist_ok=True)
    result_dir = p / f'P5MIN_{default.get_case_datetime(start)}.csv'
    with result_dir.open(mode='w' if i == 0 else 'a') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['I', 'P5MIN', 'REGIONSOLUTION', '', 'RUN_DATETIME', 'INTERVENTION', 'RUNNO', 'REGIONID', 'Price', 'RRP Record', 'ROP Record'])
        for region_id, region in regions.items():
            writer.writerow(['D',  # 0
                             'P5MIN',
                             'REGIONSOLUTION',  # 2
                             '',
                             '',
                             0,  # 5
                             default.get_interval_datetime(t),  # 6
                             region_id,  # 7
                             prices[region_id],  # 8
                             region.rrp_record,
                             region.rop_record
                             ])


def write_dispatchload(units, t, start, process, k=0, path_to_out=default.OUT_DIR):
    interval_datetime = default.get_case_datetime(t + default.THIRTY_MIN) if process == 'predispatch' else default.get_case_datetime(t + default.FIVE_MIN)
    if process == 'dispatch':
        p = path_to_out / (process if k == 0 else f'{process}_{k}')
    else:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'{process}load_{default.get_case_datetime(start)}'
    p.mkdir(parents=True, exist_ok=True)
    result_dir = p / f'dispatchload_{interval_datetime}.csv'
    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        row = ['I', 'DUID', 'TOTALCLEARED', 'RECORD', 'DAILY ENERGY', 'DAILY ENERGY RECORD']
        for bid_type in FCAS_TYPES:
            row.append(bid_type)
            row.append(f'AEMO {bid_type}')
        writer.writerow(row)
        for duid, unit in units.items():
            # print(unit.total_cleared.x if unit.total_cleared != 0 else 0)
            row = ['D',  # 0
                   duid,  # 1
                   0 if type(unit.total_cleared) == float else unit.total_cleared.x,  # 2
                   '-' if unit.total_cleared_record is None else unit.total_cleared_record,  # 3
                   (unit.total_cleared / 2.0 + unit.energy.daily_energy).getValue() if unit.energy is not None and process == 'predispatch' and unit.energy.daily_energy_limit != 0 else 0,  # 4
                   unit.total_cleared_record / 2.0 + unit.energy.daily_energy_record if unit.total_cleared_record is not None and unit.energy is not None and process == 'predispatch' and unit.energy.daily_energy_limit != 0 else 0  # 5
                   ]
            for bid_type in FCAS_TYPES:
                if unit.fcas_bids != {} and bid_type in unit.fcas_bids:
                    row.append('0' if type(unit.fcas_bids[bid_type].value) == float else unit.fcas_bids[bid_type].value.x)
                    row.append('-' if unit.target_record == {} else unit.target_record[bid_type])
                else:
                    row.append('-')
                    row.append('-')
            writer.writerow(row)


def add_prices(process, start, t, prices, k=0, path_to_out=default.OUT_DIR):
    if process == 'dispatch':
        result_dir = path_to_out / (process if k == 0 else f'{process}_{k}') / f'dispatchis_{default.get_case_datetime(t)}.csv'
    else:
        result_dir = path_to_out / (process if k == 0 else f'{process}_{k}') / f'{process}_{default.get_case_datetime(start)}' / f'dispatchis_{default.get_case_datetime(t)}.csv'
    with result_dir.open(mode='a') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['Region ID', 'Differece of Costs'])
        for region_id, price in prices.items():
            writer.writerow([region_id, price])


def write_result_csv(process, start, t, obj_value, solution, penalty, interconnectors, regions, units, fcas_flag, k=0, path_to_out=default.OUT_DIR):
    """Write the dispatch results into a csv file.

    Args:
        t (datetime): Interval datetime
        obj_value (float): Objective total_cleared
        obj_record (float): AEMO objective total_cleared
        interconnectors (dict): Interconnector dictionary
        regions (dict): Region dictionary

    Returns:
        None

    """
    if process == 'dispatch':
        p = path_to_out / (process if k == 0 else f'{process}_{k}')
    else:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'{process}_{default.get_case_datetime(start)}'
    p.mkdir(parents=True, exist_ok=True)
    result_dir = p / f'{process}_{default.get_case_datetime(t)}.csv'
    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')

        writer.writerow([default.get_interval_datetime(t)])
        writer.writerow(['Item', 'Our Objective', 'AEMO Objective', 'Our Violation', 'AEMO Violation'])
        writer.writerow(['Value', obj_value, solution.total_objective, penalty, solution.total_violation])

        writer.writerow(['Interconnector',
                         'Inter-flow',
                         'AEMO',
                         'Losses',
                         'AEMO'])
        for name, interconnector in interconnectors.items():
            writer.writerow([name,
                             interconnector.mw_flow.x,
                             interconnector.mw_flow_record,
                             interconnector.mw_losses.x,
                             interconnector.mw_losses_record
                             ])

        row = ['REGIONSUM',
               'Region ID',
               'Total Demand',
               # 'Available Gen',
               # 'AEMO Avail Gen Record',
               # 'Available Load',
               # 'AEMO Avail Load Record',
               '*Dispatchable Generation*',
               'AEMO Gen Record',
               # 'Aggregate AEMO Gen Record',
               '*Dispatchable Load*',
               'AEMO Load Record',
               # 'Aggregate AEMO Load Record',
               'Net Interconnector Targets (into)',
               'AEMO Inter-flow']
        for bid_type in FCAS_TYPES:
            row.append(bid_type)
            row.append(f'AEMO {bid_type}')

        writer.writerow(row)
        for name, region in regions.items():
            row = ['REGIONSUM',
                   name,
                   region.total_demand,
                   # region.available_generation,
                   # region.available_generation_record,
                   # region.available_load,
                   # region.available_load_record,
                   region.dispatchable_generation.getValue(),
                   region.dispatchable_generation_record,
                   # region.dispatchable_generation_temp,
                   region.dispatchable_load.getValue() if type(region.dispatchable_load) != float else 0,
                   region.dispatchable_load_record,
                   # region.dispatchable_load_temp,
                   region.net_mw_flow.getValue(),
                   region.net_mw_flow_record]
            if fcas_flag:
                for bid_type in FCAS_TYPES:
                    row.append(region.fcas_local_dispatch[bid_type].x)
                    row.append(region.fcas_local_dispatch_record[bid_type])
            writer.writerow(row)

        row = ['PRICE',
               'Region ID',
               'Price',
               'AEMO Regional Reference Price',
               'AEMO ROP'
               ]
        for bid_type in FCAS_TYPES:
            row.append(bid_type)
            row.append(f'AEMO {bid_type}')

        writer.writerow(row)
        for name, region in regions.items():
            row = ['PRICE',
                   name,
                   region.rrp,
                   region.rrp_record,
                   region.rop_record]
            if fcas_flag:
                for bid_type in FCAS_TYPES:
                    row.append('' if region.fcas_rrp == {} else region.fcas_rrp[bid_type])
                    row.append(region.fcas_rrp_record[bid_type])
            writer.writerow(row)

    # for name, unit in units.items():
    #     if unit.energy is not None:
    #         if unit.total_cleared.x != unit.total_cleared_record:
    #             print('{} our {} AEMO {}'.format(name, unit.total_cleared.x, unit.total_cleared_record))

    # regions_dir = default.OUT_DIR.joinpath('generator_dispatch.csv')
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


def record_cutom_unit(t, unit, prices):
    unit.dir = default.OUT_DIR / f'Battery_{default.get_case_datetime(t)}.csv'
    with unit.dir.open('a') as f:
        writer = csv.writer(f)
        writer.writerow([unit.Emax, unit.max_capacity, unit.dispatch_type, unit.energy.band_avail[0]] + [prices[r] for r in ['NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']])
