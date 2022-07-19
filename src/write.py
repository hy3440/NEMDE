import csv
import default
import read


def write_forecasts(current, soc, times, prices, pgen, pload, pt, T1, T, battery_dir, k=0, band=None, raise_fcas=None, lower_fcas=None, fcas_type=None):
    p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload = {}, {}, {}, {}, {}, {}
    forecast_dir = battery_dir / ('forecast' if k == 0 else f'forecast_{k}')
    forecast_dir.mkdir(parents=True, exist_ok=True)
    if band is None:
        result_dir = forecast_dir / f'{default.get_case_datetime(current)}.csv'
    else:
        result_dir = forecast_dir / f'{default.get_case_datetime(current)}_{fcas_type}_{band}.csv'
    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['I', 'Time', 'Price', 'Generation', 'Load', 'SOC', 'RAISE5MIN', 'LOWER5MIN', default.get_interval_datetime(pt)])
        if raise_fcas is None:
            raise_fcas = lower_fcas = [None for n in range(T)]
        for j, (s, t, p, g, l, ra, lo) in enumerate(zip(soc, times, prices, pgen, pload, raise_fcas, lower_fcas)):
            if T1 <= j < T:
                process_type = 'PREDISPATCH'
                predispatch_pgen[t] = g.x
                predispatch_pload[t] = l.x
            elif j < T1:
                process_type = 'P5MIN'
                p5min_pgen[t] = g.x
                p5min_pload[t] = l.x
            else:
                process_type = 'DISPATCH'
                dispatch_pgen[t] = g.x
                dispatch_pload[t] = l.x
            writer.writerow([process_type, default.get_interval_datetime(t), p, g.x, l.x, s.x, '-' if ra is None else ra.x, '-' if lo is None else lo.x])
    return p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload


def write_trading_prices(start, k=0, path_to_out=default.OUT_DIR):
    trading_prices = {'NSW1': [], 'VIC1': [], 'SA1': [], 'QLD1': [], 'TAS1': []}
    aemo_prices = {'NSW1': [], 'VIC1': [], 'SA1': [], 'QLD1': [], 'TAS1': []}
    for i in range(288):
        if i % 6 == 0:
            prices = {'NSW1': [], 'VIC1': [], 'SA1': [], 'QLD1': [], 'TAS1': []}
        t = start + i * default.FIVE_MIN
        for region in prices.keys():
            dispatch_price, _, _, _ = read.read_dispatch_prices(t, 'dispatch', True, region)
            prices[region].append(dispatch_price)
        if i % 6 == 5:
            p = path_to_out / ('dispatch' if k == 0 else f'dispatch_{k}') / f'TRADINGIS_{default.get_case_datetime(t)}.csv'
            with p.open('w') as f:
                writer = csv.writer(f)
                writer.writerow(['I', 'TRADING', 'PRICE', '', 'SETTLEMENTDATE', '', 'REGIONID', 'PERIODID', 'RRP', 'AEMO RRP'])
                for region in prices.keys():
                    aemo_price = read.read_trading_prices(t, False, region)
                    trading_price = sum(prices[region]) / 6
                    writer.writerow(['D', 'TRADING', 'PRICE', '', default.get_interval_datetime(t), '', region, i // 6 + 1, trading_price, aemo_price])
                    trading_prices[region].append(trading_price)
                    aemo_prices[region].append(aemo_price)
    return trading_prices, aemo_prices


def write_revenues(batteries, revenues, region_id, method):
    path_to_dir = default.OUT_DIR / 'revenue'
    path_to_dir.mkdir(exist_ok=True, parents=True)
    path_to_revenue = path_to_dir / f'Revenue {region_id} Method {method}.csv'
    with path_to_revenue.open('w') as rf:
        writer = csv.writer(rf)
        writer.writerow(['I', 'Capacity (MWh)', 'Power (MW)', 'Revenue ($)'])
        for b, r in zip(batteries, revenues):
            writer.writerow(['D', b.generator.Emax, b.generator.max_capacity, r])


def write_schedule(times, gens, loads, path_to_dir):
    path_to_file = path_to_dir / f'DER_Schedule_{default.get_case_datetime(times[0])}.csv'
    with path_to_file.open('w') as rf:
        writer = csv.writer(rf)
        writer.writerow(['Datetime', 'Generator', 'Load'])
        for t, g, l in zip(times, gens, loads):
            writer.writerow([default.get_interval_datetime(t), g.x, l.x])

