import csv
import default
import dispatch
import preprocess
import write


def read_trading_prices(t, custom_flag, region_id, k=0, path_to_out=default.OUT_DIR):
    if custom_flag:
        p = path_to_out / ('dispatch' if k == 0 else f'dispatch_{k}') / f'TRADINGIS_{default.get_case_datetime(t)}.csv'
        if not p.is_file():
            start = default.get_first_datetime(t, process='dispatch')
            write.write_trading_prices(start, k, path_to_out)
    else:
        p = preprocess.download_tradingis(t)
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'PRICE' and row[6] == region_id:
                return float(row[8]), float(row[9]) if custom_flag else float(row[8])  # RRP of period


def read_dispatch_prices(t, process, custom_flag, region_id, k=0, path_to_out=default.OUT_DIR, intervention='0'):
    if custom_flag:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'DISPATCHIS_{default.get_case_datetime(t)}.csv'
        if not p.is_file() and k == 0:
            dispatch.get_all_dispatch(t, process)
    else:
        p = preprocess.download_dispatch_summary(t)
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'PRICE' and row[6] == region_id and row[8] == intervention:
                # interval_rrp_record.append(float(row[9]))  # RRP of interval
                # interval_prices_dict[t] = float(row[9])
                # raise6sec_rrp_record.append(float(row[15]))
                # raise60sec_rrp_record.append(float(row[18]))
                # raise5min_rrp_record.append(float(row[21]))
                # raisereg_rrp_record.append(float(row[24]))
                # lower6sec_rrp_record.append(float(row[27]))
                # lower60sec_rrp_record.append(float(row[30]))
                # lower5min_rrp_record.append(float(row[33]))
                # lowerreg_rrp_record.append(float(row[36]))
                return float(row[9]), float(row[10]) if custom_flag else float(row[9])


def read_p5min_prices(t, process, custom_flag, region_id, k=0, path_to_out=default.OUT_DIR, intervention='0'):
    if custom_flag:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'P5MIN_{default.get_case_datetime(t)}.csv'
        if not p.is_file() and k == 0:
            dispatch.get_all_dispatch(t, process)
    else:
        p = preprocess.download_5min_predispatch(t)
    p5min_times, p5min_prices, aemo_p5min_prices = [], [], []
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and row[7] == region_id and row[5] == intervention:
                p5min_times.append(default.extract_datetime(row[6]))
                p5min_prices.append(float(row[8]))
                aemo_p5min_prices.append(float(row[9]) if custom_flag else float(row[8]))
    return p5min_times, p5min_prices, aemo_p5min_prices


def read_predispatch_prices(t, process, custom_flag, region_id, k=0, path_to_out=default.OUT_DIR, intervention='0'):
    if custom_flag:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'PREDISPATCHIS_{default.get_case_datetime(t)}.csv'
        if not p.is_file():
            if k == 0:
                dispatch.get_all_dispatch(t, process)
    else:
        p = preprocess.download_predispatch(t)
    predispatch_times, predispatch_prices, aemo_predispatch_prices = [], [], []
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGION_PRICES' and row[6] == region_id and row[8] == intervention:
                predispatch_times.append(default.extract_datetime(row[28]))
                predispatch_prices.append(float(row[9]))
                aemo_predispatch_prices.append(float(row[10]) if custom_flag else float(row[9]))
    return predispatch_times, predispatch_prices, aemo_predispatch_prices


def read_prices(t, process, custom_flag, region_id, k=0, path_to_out=default.OUT_DIR, intervention='0'):
    price_func = {'dispatch': read_dispatch_prices,
                  'p5min': read_p5min_prices,
                  'predispatch': read_predispatch_prices}
    func = price_func.get(process)
    return func(t, process, custom_flag, region_id, k, path_to_out, intervention)


def read_forecasts(current, battery_dir, k):
    result_dir = battery_dir / ('forecast' if k == 0 else f'forecast_{k}') / f'{default.get_case_datetime(current)}.csv'
    p5min_pgen = {}
    p5min_pload = {}
    predispatch_pgen = {}
    predispatch_pload = {}
    with result_dir.open(mode='r') as result_file:
        reader = csv.reader(result_file)
        for row in reader:
            if row[0] == 'I':
                pt = default.extract_datetime(row[6])
            else:
                pgen = p5min_pgen if row[0] == 'P5MIN' else predispatch_pgen
                pload = p5min_pload if row[0] == 'P5MIN' else predispatch_pload
                pgen[default.extract_datetime(row[1])] = float(row[3])
                pload[default.extract_datetime(row[1])] = float(row[4])
    return p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, pt


def read_optimisation(t, b):
    times, generations, loads, energy, power, dispatch_prices, aemo_dispatch_prices = [], [], [], [], [], [], []
    opt_dir = b.bat_dir / f'Optimisation {default.get_case_datetime(t)}.csv'
    with opt_dir.open('r') as opt_file:
        reader = csv.reader(opt_file)
        for row in reader:
            if row[0] == 'D':
                times.append(default.extract_default_datetime(row[1]))
                generations.append(float(row[2]))
                loads.append(float(row[3]))
                power.append(float(row[4]))
                energy.append(float(row[5]))
                dispatch_prices.append(float(row[6]))
                aemo_dispatch_prices.append(float(row[7]))
            elif row[0] == 'H':
                revenue = float(row[2])
    return times, generations, loads, energy, power, dispatch_prices, aemo_dispatch_prices, revenue


def read_revenues(region_id, method):
    capacities, powers, revenues = [], [], []
    path_to_revenue = default.OUT_DIR / 'revenue' / f'revenue {region_id} method {method}.csv'
    with path_to_revenue.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'I':
                capacity_label = row[1]
                power_label = row[2]
                revenue_label = row[3]
            elif row[0] == 'D':
                capacities.append(float(row[1]))
                powers.append(float(row[2]))
                revenues.append(float(row[3]))
    return capacity_label, capacities, power_label, powers, revenue_label, revenues
