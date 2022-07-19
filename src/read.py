import csv
import default
import preprocess
import write


def read_trading_prices(t, custom_flag, region_id, k=0, path_to_out=default.OUT_DIR):
    """Read prices from TRADINGIS file.

    Args:
        t (datetime.datetime): current datetime
        custom_flag (bool): our custom results or AEMO's records
        region_id (str): region ID
        k (int): iteration number
        path_to_out (pathlib.Path): path to output directory
    Returns:
        (float, float): period RRP, RRP record
    """
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


def read_dispatch_prices(t, process, custom_flag, region_id, k=0, path_to_out=default.RECORD_DIR, intervention='0', fcas_flag=False):
    """Read prices from DISPATCHIS file.

    Args:
        t (datetime.datetime): current datetime
        process (str): process type, 'dispatch', 'p5min' or 'predispatch'
        custom_flag (bool): our custom results or AEMO's records
        region_id (str): region ID
        k (int): iteration number
        path_to_out (pathlib.Path): path to output directory
        intervention (str): intervention or not
        fcas_flag (bool): consider FCAS or not

    Returns:
        (float, float, dict, dict): RRP, RRP record, FCAS RRP, FCAS RRP record
    """
    if custom_flag:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'DISPATCHIS_{default.get_case_datetime(t)}.csv'
        # if not p.is_file() and k == 0:
        #     dispatch.get_all_dispatch(t, process)
    else:
        p = preprocess.download_dispatch_summary(t)

    def extract_row(row):
        fcas_prices, aemo_fcas_prices = {}, {}
        rrp = float(row[9])
        rrp_record = float(row[10]) if custom_flag else None
        if fcas_flag:
            fcas_prices['RAISE6SEC'] = 0 if row[15] == '' else float(row[15])
            fcas_prices['RAISE60SEC'] = 0 if row[18] == '' else float(row[18])
            fcas_prices['RAISE5MIN'] = 0 if row[21] == '' else float(row[21])
            fcas_prices['RAISEREG'] = 0 if row[24] == '' else float(row[24])
            fcas_prices['LOWER6SEC'] = 0 if row[27] == '' else float(row[27])
            fcas_prices['LOWER60SEC'] = 0 if row[30] == '' else float(row[30])
            fcas_prices['LOWER5MIN'] = 0 if row[33] == '' else float(row[33])
            fcas_prices['LOWERREG'] = 0 if row[36] == '' else float(row[36])
            if custom_flag:
                aemo_fcas_prices['RAISE6SEC'] = float(row[16])
                aemo_fcas_prices['RAISE60SEC'] = float(row[19])
                aemo_fcas_prices['RAISE5MIN'] = float(row[22])
                aemo_fcas_prices['RAISEREG'] = float(row[25])
                aemo_fcas_prices['LOWER6SEC'] = float(row[28])
                aemo_fcas_prices['LOWER60SEC'] = float(row[31])
                aemo_fcas_prices['LOWER5MIN'] = float(row[34])
                aemo_fcas_prices['LOWERREG'] = float(row[37])
        return rrp, rrp_record, fcas_prices, aemo_fcas_prices

    regions_price = {}
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'PRICE' and row[8] == intervention:
                if region_id:
                    if row[6] == region_id:
                        return extract_row(row)
                else:
                    regions_price[row[6]] = (extract_row(row))
    return regions_price


def read_p5min_prices(t, process, custom_flag, region_id, k=0, path_to_out=default.RECORD_DIR, intervention='0', fcas_flag=False):
    """Read P5MIN prices.

    Args:
        t (datetime.datetime): current datetime
        process (str): process type, 'dispatch', 'p5min' or 'predispatch'
        custom_flag (bool): our custom results or AEMO's records
        region_id (str): region ID
        k (int): iteration number
        path_to_out (pathlib.Path): path to output directory
        intervention (str): intervention or not
        fcas_flag (bool): consider FCAS or not

    Returns:
        (list, list, list, dict, dict): datetimes, RRP, RRP record, FCAS RRP, FCAS RRP record
    """
    if custom_flag:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'P5MIN_{default.get_case_datetime(t)}.csv'
        # if not p.is_file() and k == 0:
        #     dispatch.get_all_dispatch(t, process)
    else:
        p = preprocess.download_5min_predispatch(t)
    p5min_times, p5min_prices, aemo_p5min_prices = [], [], []
    p5min_fcas_prices = {
        'RAISEREG': [],
        'RAISE6SEC': [],
        'RAISE60SEC': [],
        'RAISE5MIN': [],
        'LOWERREG': [],
        'LOWER6SEC': [],
        'LOWER60SEC': [],
        'LOWER5MIN': []
    }
    aemo_p5min_fcas_prices = {
        'RAISEREG': [],
        'RAISE6SEC': [],
        'RAISE60SEC': [],
        'RAISE5MIN': [],
        'LOWERREG': [],
        'LOWER6SEC': [],
        'LOWER60SEC': [],
        'LOWER5MIN': []
    }
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and row[7] == region_id and row[5] == intervention:
                p5min_times.append(default.extract_datetime(row[6]))
                p5min_prices.append(float(row[8]))
                if custom_flag:
                    aemo_p5min_prices.append(float(row[9]))
                if fcas_flag:
                    p5min_fcas_prices['RAISE6SEC'].append(float(row[11]))
                    p5min_fcas_prices['RAISE60SEC'].append(float(row[13]))
                    p5min_fcas_prices['RAISE5MIN'].append(float(row[15]))
                    p5min_fcas_prices['RAISEREG'].append(float(row[17]))
                    p5min_fcas_prices['LOWER6SEC'].append(float(row[19]))
                    p5min_fcas_prices['LOWER60SEC'].append(float(row[21]))
                    p5min_fcas_prices['LOWER5MIN'].append(float(row[23]))
                    p5min_fcas_prices['LOWERREG'].append(float(row[25]))
                    if custom_flag:
                        aemo_p5min_fcas_prices['RAISE6SEC'].append(float(row[12]))
                        aemo_p5min_fcas_prices['RAISE60SEC'].append(float(row[14]))
                        aemo_p5min_fcas_prices['RAISE5MIN'].append(float(row[16]))
                        aemo_p5min_fcas_prices['RAISEREG'].append(float(row[18]))
                        aemo_p5min_fcas_prices['LOWER6SEC'].append(float(row[20]))
                        aemo_p5min_fcas_prices['LOWER60SEC'].append(float(row[22]))
                        aemo_p5min_fcas_prices['LOWER5MIN'].append(float(row[24]))
                        aemo_p5min_fcas_prices['LOWERREG'].append(float(row[26]))
    return p5min_times, p5min_prices, aemo_p5min_prices, p5min_fcas_prices, aemo_p5min_fcas_prices


def read_predispatch_prices(t, process, custom_flag, region_id, k=0, path_to_out=default.RECORD_DIR, intervention='0', fcas_flag=False):
    """Read PREDISPATCH prices.

        Args:
            t (datetime.datetime): current datetime
            process (str): process type, 'dispatch', 'p5min' or 'predispatch'
            custom_flag (bool): our custom results or AEMO's records
            region_id (str): region ID
            k (int): iteration number
            path_to_out (pathlib.Path): path to output directory
            intervention (str): intervention or not
            fcas_flag (bool): consider FCAS or not

        Returns:
            (list, list, list, dict, dict): datetimes, RRP, RRP record, FCAS RRP, FCAS RRP record
        """
    if custom_flag:
        p = path_to_out / (process if k == 0 else f'{process}_{k}') / f'PREDISPATCHIS_{default.get_case_datetime(t)}.csv'
        # if not p.is_file() and k == 0:
        #     dispatch.get_all_dispatch(t, process)
    else:
        p = preprocess.download_predispatch(t)
    predispatch_times, predispatch_prices, aemo_predispatch_prices = [], [], []
    predispatch_fcas_prices = {
        'RAISEREG': [],
        'RAISE6SEC': [],
        'RAISE60SEC': [],
        'RAISE5MIN': [],
        'LOWERREG': [],
        'LOWER6SEC': [],
        'LOWER60SEC': [],
        'LOWER5MIN': []
    }
    aemo_predispatch_fcas_prices = {
        'RAISEREG': [],
        'RAISE6SEC': [],
        'RAISE60SEC': [],
        'RAISE5MIN': [],
        'LOWERREG': [],
        'LOWER6SEC': [],
        'LOWER60SEC': [],
        'LOWER5MIN': []
    }
    with p.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGION_PRICES' and row[6] == region_id and row[8] == intervention:
                predispatch_times.append(default.extract_datetime(row[28]))
                predispatch_prices.append(float(row[9]))
                if custom_flag:
                    aemo_predispatch_prices.append(float(row[10]))
                if fcas_flag:
                    predispatch_fcas_prices['RAISE6SEC'].append(float(row[29]))
                    predispatch_fcas_prices['RAISE60SEC'].append(float(row[30]))
                    predispatch_fcas_prices['RAISE5MIN'].append(float(row[31]))
                    predispatch_fcas_prices['RAISEREG'].append(float(row[32]))
                    predispatch_fcas_prices['LOWER6SEC'].append(float(row[33]))
                    predispatch_fcas_prices['LOWER60SEC'].append(float(row[34]))
                    predispatch_fcas_prices['LOWER5MIN'].append(float(row[35]))
                    predispatch_fcas_prices['LOWERREG'].append(float(row[36]))
                    if custom_flag:
                        aemo_predispatch_fcas_prices['RAISE6SEC'].append(float(row[37]))
                        aemo_predispatch_fcas_prices['RAISE60SEC'].append(float(row[38]))
                        aemo_predispatch_fcas_prices['RAISE5MIN'].append(float(row[39]))
                        aemo_predispatch_fcas_prices['RAISEREG'].append(float(row[40]))
                        aemo_predispatch_fcas_prices['LOWER6SEC'].append(float(row[41]))
                        aemo_predispatch_fcas_prices['LOWER60SEC'].append(float(row[42]))
                        aemo_predispatch_fcas_prices['LOWER5MIN'].append(float(row[43]))
                        aemo_predispatch_fcas_prices['LOWERREG'].append(float(row[44]))
    return predispatch_times, predispatch_prices, aemo_predispatch_prices, predispatch_fcas_prices, aemo_predispatch_fcas_prices


def read_prices(t, process, custom_flag, region_id, k=0, path_to_out=default.RECORD_DIR, intervention='0', fcas_flag=False):
    """Read prices.

    Args:
        t (datetime.datetime): datetime
        process (str): 'dispatch', 'p5min', or 'predispatch'
        custom_flag (bool): use our results or AEMO's records
        region_id (str): region ID
        k (int): iteration number
        path_to_out (pathlib.Path): path to the output directory
        intervention (str): intervention or not
        fcas_flag (bool): consider FCAS or not

    Returns:

    """
    price_func = {'dispatch': read_dispatch_prices,
                  'p5min': read_p5min_prices,
                  'predispatch': read_predispatch_prices}
    func = price_func.get(process)
    return func(t, process, custom_flag, region_id, k, path_to_out, intervention, fcas_flag)


def read_dispatch_fcas(start, region_id):
    """Read DISPATCH maximum FCAS of the given region.

        Args:
            start (datetime.datetime): start datetime
            region_id (str): region ID

        Returns:
            (list, list): max RAISE FCAS record, max LOWER FCAS record
        """
    dispatch_dir = preprocess.download_dispatch_summary(start)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSUM' and row[6] == region_id:
                raise_fcas_record = max(float(row[43]), float(row[51]), float(row[59]))
                lower_fcas_record = max(float(row[19]), float(row[27]), float(row[35]))
    return raise_fcas_record, lower_fcas_record


def read_p5min_fcas(start, region_id):
    """Read P5MIN maximum FCAS of the given region.

    Args:
        start (datetime.datetime): start datetime
        region_id (str): region ID

    Returns:
        (list, list): max RAISE FCAS record, max LOWER FCAS record
    """
    raise_fcas_record, lower_fcas_record = [], []
    dispatch_dir = preprocess.download_5min_predispatch(start)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSOLUTION' and row[7] == region_id:
                raise_fcas_record.append(max(float(row[51]), float(row[56]), float(row[61])))
                lower_fcas_record.append(max(float(row[36]), float(row[41]), float(row[46])))
    return raise_fcas_record, lower_fcas_record


def read_predispatch_fcas(start, region_id):
    """Read PREDISPATCH maximum FCAS of the given region.

        Args:
            start (datetime.datetime): start datetime
            region_id (str): region ID

        Returns:
            (list, list): max RAISE FCAS record, max LOWER FCAS record
    """
    raise_fcas_record, lower_fcas_record = [], []
    dispatch_dir = preprocess.download_predispatch(start)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGION_SOLUTION' and row[6] == region_id:
                raise_fcas_record.append(max(float(row[43]), float(row[51]), float(row[59])))
                lower_fcas_record.append(max(float(row[19]), float(row[27]), float(row[35])))
    return raise_fcas_record, lower_fcas_record


def read_forecasts(current, battery_dir, k):
    result_dir = battery_dir / ('forecast' if k == 0 else f'forecast_{k}') / f'{default.get_case_datetime(current)}.csv'
    p5min_pgen = {}
    p5min_pload = {}
    predispatch_pgen = {}
    predispatch_pload = {}
    dispatch_pgen = {}
    dispatch_pload = {}
    with result_dir.open(mode='r') as result_file:
        reader = csv.reader(result_file)
        for row in reader:
            if row[0] == 'I':
                pt = default.extract_datetime(row[6])
            else:
                if row[0] == 'P5MIN':
                    pgen = p5min_pgen
                    pload = p5min_pload
                elif row[0] == 'PREDISPATCH':
                    pgen = predispatch_pgen
                    pload = predispatch_pload
                else:
                    pgen = dispatch_pgen
                    pload = dispatch_pload
                pgen[default.extract_datetime(row[1])] = float(row[3])
                pload[default.extract_datetime(row[1])] = float(row[4])
    return p5min_pgen, p5min_pload, predispatch_pgen, predispatch_pload, dispatch_pgen, dispatch_pload, pt


def read_forecast_soc(current, battery_dir, k=0, band=None):
    if band is None:
        result_dir = battery_dir / ('forecast' if k == 0 else f'forecast_{k}') / f'{default.get_case_datetime(current)}.csv'
    else:
        result_dir = battery_dir / ('forecast' if k == 0 else f'forecast_{k}') / f'{default.get_case_datetime(current)}_{band}.csv'
    times, prices, socs = [], [], []
    with result_dir.open(mode='r') as result_file:
        reader = csv.reader(result_file)
        for row in reader:
            if row[0] != 'I':
                times.append(default.extract_datetime(row[1]))
                prices.append(float(row[2]))
                socs.append(float(row[5]) * 100)
    return times, prices, socs


def read_first_forecast(start, end, region_id, battery_dir, k):
    times, prices, socs, original_prices = [], [], [], []
    while start <= end:
        times.append(start)
        result_dir = battery_dir / ('forecast' if k == 0 else f'forecast_{k}') / f'{default.get_case_datetime(start)}.csv'
        with result_dir.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] != 'I':
                    prices.append(float(row[2]))
                    socs.append(float(row[5]) * 100)
                    break
        rrp, rrp_record, _, _ = read_dispatch_prices(start, 'dispatch', True, region_id)
        original_prices.append(rrp)
        start += default.FIVE_MIN
        if k == 0:
            k = 1
    return times, prices, socs, original_prices


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
    path_to_revenue = default.OUT_DIR / 'revenue' / f'Revenue {region_id} Method {method}.csv'
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


def read_optimisation_with_bids(b, method, k):
    import datetime
    opt_dir = default.OUT_DIR / f'battery optimisation with bids {b.generator.region_id} method {method}'
    opt_path = opt_dir / f'battery optimisation with bids {b.name}.csv'
    times, socs, prices, original_prices = [datetime.datetime(2020, 9, 1, 4, 0)], [50], [None], [None]
    with opt_path.open('r') as f:
        reader = csv.reader(f)
        i = 0
        max_temp = 0
        for row in reader:
            if 0 < i < 287:
                t = datetime.datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                times.append(t)
                socs.append(float(row[1]))
                rrp, _, _, _ = read_dispatch_prices(t, 'dispatch', True, b.load.region_id, k=k, path_to_out=b.bat_dir)
                prices.append(rrp)
                original_rrp, _, _, _ = read_dispatch_prices(t, 'dispatch', True, b.load.region_id)
                original_prices.append(original_rrp)
                if abs(rrp - original_rrp) > max_temp:
                    max_temp = abs(rrp - original_rrp)
                    tuple_temp = (t, rrp, original_rrp)
            i += 1
        print(tuple_temp)
    return times, socs, prices, original_prices


def read_der(e, start, bat_dir):
    import datetime
    times, socs, prices, socs_record = [], [], [], []
    path_to_csv = bat_dir / f'DER_{e}MWh_{default.get_case_datetime(start)}.csv'
    with path_to_csv.open() as f:
        reader = csv.reader(f)
        for row in reader:
            times.append(default.extract_default_datetime(row[0]))
            socs.append(float(row[2]) * 100 / e)
            prices.append(float(row[5]))
            # socs_record.append(float(row[6]) * 100 / e)
    return times, socs, prices, socs_record


def read_battery_optimisation(path_to_csv):
    """Read battery optimisation result.

    Args:
        path_to_csv (pathlib.Path): path to the CSV file

    Returns:
        (list, list, list): datetimes, SOCs, prices
    """
    times, socs, prices = [], [], []
    with path_to_csv.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] != 'Datetime':
                times.append(default.extract_default_datetime(row[0]))
                socs.append(float(row[-2]))
                prices.append(float(row[-1]))
    return times, socs, prices


def read_battery_power(path_to_csv, usage):
    """Read battery dispatch results after participating in NEMDE.

    Args:
        path_to_csv (pathlib.Path): path to the CSV file
        usage (str): battery usage

    Returns:
        (list, list, list, list, list, list, list): times, generations, loads, prices, generator_fcas, load_fcas, fcas_prices
    """
    times, generations, loads, prices = [], [], [], []
    if 'multi' in usage:
        generator_fcas = {'RAISE5MIN': [], 'LOWER5MIN': [], 'RAISE6SEC': [], 'LOWER6SEC': [], 'RAISE60SEC': [], 'LOWER60SEC': []}
        load_fcas = {'RAISE5MIN': [], 'LOWER5MIN': [], 'RAISE6SEC': [], 'LOWER6SEC': [], 'RAISE60SEC': [], 'LOWER60SEC': []}
        fcas_prices = {'RAISE5MIN': [], 'LOWER5MIN': [], 'RAISE6SEC': [], 'LOWER6SEC': [], 'RAISE60SEC': [], 'LOWER60SEC': []}
    else:
        generator_fcas = {'RAISE5MIN': [], 'LOWER5MIN': []}
        load_fcas = {'RAISE5MIN': [], 'LOWER5MIN': []}
        fcas_prices = {'RAISE5MIN': [], 'LOWER5MIN': []}
    with path_to_csv.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] != 'Datetime':
                times.append(default.extract_default_datetime(row[0]))
                generations.append(float(row[-5]))
                loads.append(float(row[-4]))
                prices.append(float(row[-1]))
                # if 'price-taker' in usage and 'FCAS' in usage:
                #     r5_values.append(float(row[-9]))
                #     r5_prices.append(float(row[-8]))
                #     l5_values.append(float(row[-7]))
                #     l5_prices.append(float(row[-6]))
                # elif 'reflective' in usage and 'FCAS' in usage:
                if 'FCAS' in usage:
                    generator_fcas['RAISE5MIN'].append(float(row[1]))
                    load_fcas['RAISE5MIN'].append(float(row[2]))
                    fcas_prices['RAISE5MIN'].append(float(row[3]))
                    generator_fcas['LOWER5MIN'].append(float(row[4]))
                    load_fcas['LOWER5MIN'].append(float(row[5]))
                    fcas_prices['LOWER5MIN'].append(float(row[6]))
                    if 'multi' in usage:
                        generator_fcas['RAISE6SEC'].append(float(row[7]))
                        load_fcas['RAISE6SEC'].append(float(row[8]))
                        fcas_prices['RAISE6SEC'].append(float(row[9]))
                        generator_fcas['LOWER6SEC'].append(float(row[10]))
                        load_fcas['LOWER6SEC'].append(float(row[11]))
                        fcas_prices['LOWER6SEC'].append(float(row[12]))
                        generator_fcas['RAISE60SEC'].append(float(row[13]))
                        load_fcas['RAISE60SEC'].append(float(row[14]))
                        fcas_prices['RAISE60SEC'].append(float(row[15]))
                        generator_fcas['LOWER60SEC'].append(float(row[16]))
                        load_fcas['LOWER60SEC'].append(float(row[17]))
                        fcas_prices['LOWER60SEC'].append(float(row[18]))
    return times, generations, loads, prices, generator_fcas, load_fcas, fcas_prices


def read_bidding_strategy(start, current, bat_dir, usage):
    path_to_csv = bat_dir / f'{default.get_case_datetime(start)}.csv'
    with path_to_csv.open() as f:
        reader = csv.reader(f)
        bands = None
        max_avail= None
        for row in reader:
            if row[0] == str(current):
                if usage == 'price-taker':
                    availability = float(row[1])
                    # max_avail = float(row[2])
                elif usage == 'reflective':
                    availability = [float(avail) for avail in row[1:11]]
                    # max_avail = [float(row[11]), float(row[12])]
                soc = float(row[-2])
                price = float(row[-1])
                return bands, availability, max_avail, soc, price
            elif usage == 'reflective':
                bands = [float(band) for band in row[1:11]]


def read_der_nemde_battery(battery, start):
    times, prices = [], []
    path_to_csv = battery.bat_dir / f'DER_{battery.size}MWh_{default.get_case_datetime(start)}.csv'
    with path_to_csv.open() as f:
        reader = csv.reader(f)
        for row in reader:
            times.append(default.extract_default_datetime(row[0]))
            prices.append(float(row[-1]))
    return times, prices


