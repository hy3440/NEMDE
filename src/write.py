import csv
import default
import read


def write_forecasts(current, soc, times, prices, pgen, pload, pt, T1, T2, battery_dir, k=0):
    forecast_dir = battery_dir / ('forecast' if k == 0 else f'forecast_{k}')
    forecast_dir.mkdir(parents=True, exist_ok=True)
    result_dir = forecast_dir / f'{default.get_case_datetime(current)}.csv'
    with result_dir.open(mode='w') as result_file:
        writer = csv.writer(result_file, delimiter=',')
        writer.writerow(['I', 'Time', 'Price', 'Generation', 'Load', 'SOC', default.get_interval_datetime(pt)])
        for j, (s, t, p, g, l) in enumerate(zip(soc, times, prices, pgen, pload)):
            if T1 <= j < T1 + T2:
                process_type = 'PREDISPATCH'
            elif j < T1:
                process_type = 'P5MIN'
            else:
                process_type = 'DISPATCH'
            writer.writerow([process_type, default.get_interval_datetime(t), p, g.x, l.x, s.x])


def write_trading_prices(start, k=0, path_to_out=default.OUT_DIR):
    trading_prices = {'NSW1': [], 'VIC1': [], 'SA1': [], 'QLD1': [], 'TAS1': []}
    aemo_prices = {'NSW1': [], 'VIC1': [], 'SA1': [], 'QLD1': [], 'TAS1': []}
    for i in range(288):
        if i % 6 == 0:
            prices = {'NSW1': [], 'VIC1': [], 'SA1': [], 'QLD1': [], 'TAS1': []}
        t = start + i * default.FIVE_MIN
        for region in prices.keys():
            dispatch_price, _ = read.read_dispatch_prices(t, 'dispatch', True, region)
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
    path_to_revenue = default.OUT_DIR / 'revenue' / f'revenue {region_id} method {method}.csv'
    with path_to_revenue.open('w') as rf:
        writer = csv.writer(rf)
        writer.writerow(['I', 'Capacity (MWh)', 'Power (MW)', 'Revenue ($)'])
        for b, r in zip(batteries, revenues):
            writer.writerow(['D', b.generator.Emax, b.generator.max_capacity, r])
