# Cost reflective bidding strategy
import csv
import datetime
from helpers import Battery
from operate import schedule
from preprocess import get_market_price, download_dvd_data
from read import read_predispatch_prices, read_battery_optimisation, read_dispatch_prices, read_forecast_soc, read_battery_power
from multiprocessing.pool import ThreadPool as Pool
from dispatch import formulate, formulate_sequence
from offer import EnergyBid, FcasBid
from itertools import repeat
import default
from plot import plot_soc, plot_revenues, plot_power
from multidispatch import multiformulate
import numpy as np


fcas_pmax = {
    'RAISE5MIN': 1.0,
    'LOWER5MIN': 2.0,
    'RAISE6SEC': 35,
    'LOWER6SEC': 1.5,
    'RAISE60SEC': 20.0,
    'LOWER60SEC': 5.0,
    'RAISEREG': 35,
    'LOWERREG': 25
}


def generate_batteries(energies, usage):
    """Generate a list of Battery instances.

    Args:
        energies (list): a list of battery sizes (in MWh)
        usage (str): what those batteries used for

    Returns:
        list: a list of Battery instances
    """
    return [Battery(e, int(e * 2 / 3) if type(e) == int else (e * 2 / 3), usage=usage) for e in energies]


def extract_prices(region_id, intervention='0'):
    """Extract historical price records to determine band ranges.

    Args:
        region_id (str): region ID
        intervention (str): intervention flag

    Returns:
        None
    """
    from dateutil.relativedelta import relativedelta
    aemo_prices = []
    aemo_fcas_prices = {
        'RAISEREG': [],
        'RAISE6SEC': [],
        'RAISE60SEC': [],
        'RAISE5MIN': [],
        'LOWERREG': [],
        'LOWER6SEC': [],
        'LOWER60SEC': [],
        'LOWER5MIN': []
    }
    start = datetime.datetime(2021, 1, 1)
    for m in range(12):
        t = start + relativedelta(months=m)
        price_dir = download_dvd_data('DISPATCHPRICE', t)
        with price_dir.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == 'D' and row[6] == region_id and row[8] == intervention:
                    aemo_prices.append(float(row[9]))
                    aemo_fcas_prices['RAISE6SEC'].append(float(row[15]))
                    aemo_fcas_prices['RAISE60SEC'].append(float(row[18]))
                    aemo_fcas_prices['RAISE5MIN'].append(float(row[21]))
                    aemo_fcas_prices['RAISEREG'].append(float(row[24]))
                    aemo_fcas_prices['LOWER6SEC'].append(float(row[27]))
                    aemo_fcas_prices['LOWER60SEC'].append(float(row[30]))
                    aemo_fcas_prices['LOWER5MIN'].append(float(row[33]))
                    aemo_fcas_prices['LOWERREG'].append(float(row[36]))
    print(f'length: {len(aemo_prices)}')
    print(f'Energy Max: {max(aemo_prices)} Min: {min(aemo_prices)}')
    for bid_type, prices in aemo_fcas_prices.items():
        print(f'{region_id} {bid_type} Max: {max(prices)} Min: {min(prices)}')
    # import seaborn as sns
    import matplotlib
    import matplotlib.pyplot as plt
    # sns.displot([p for p in aemo_fcas_prices['RAISE5MIN'] if p < 100])
    bid_type = 'LOWERREG'
    plt.hist([p for p in aemo_fcas_prices[bid_type] if p < 40], 100)
    plt.title(bid_type)
    plt.xlabel('Price')
    plt.ylabel('Count')
    path_to_fig = default.OUT_DIR / f'{bid_type}.jpg'
    plt.savefig(path_to_fig)
    plt.show()
    counts = {60:0, 50:0, 40:0, 35:0, 30:0, 25:0, 20:0, 15:0, 10: 0, 7.5:0, 5: 0, 1.5:0, 1: 0, 0.75: 0, 0.5: 0, 0.25: 0, 0: 0}
    for p in aemo_fcas_prices[bid_type]:
        for n in counts.keys():
            if p >= n:
                counts[n] += 1
                break
    print(counts)
    print(len(aemo_prices))


def generate_bands(start, usage):
    """Generate a list of bands for different usages.

    Args:
        start (datetime.datetime): start datetime
        usage (str): usage

    Returns:
        (list, list): a list of energy bands, a list of FCAS bands
    """
    voll, market_price_floor = get_market_price(start)
    fcas_bands = {}
    fcas_flag = 'FCAS' in usage
    if 'reflective' in usage:
        B = 7
        times, prices, _, fcas_prices, _ = read_predispatch_prices(start + default.TWENTYFIVE_MIN, process='predispatch', custom_flag=False, region_id='NSW1', fcas_flag=fcas_flag)
        if 'new' in usage:
            pmax, pmin = max(prices) * 1.1, min(prices) * (0.9 if min(prices) >= 0 else 1.1)
        else:
            pmax, pmin = max(prices), min(prices)
        bands = [market_price_floor] + [pmin + b * (pmax - pmin) / B for b in range(B + 1)] + [voll]
        if fcas_flag:
            for bid_type, fcas_price in fcas_prices.items():
                if 'new' in usage:
                    pmax, pmin = max(fcas_pmax[bid_type], max(fcas_price)), min(0, min(fcas_price))
                else:
                    pmax, pmin = max(fcas_price), min(fcas_price)
                if '1' in usage:
                    if pmin == 0:
                        fcas_bands[bid_type] = [pmin + b * (pmax - pmin) / (B + 1) for b in range(B + 2)] + [voll]
                    else:
                        fcas_bands[bid_type] = [0] + [pmin + b * (pmax - pmin) / B for b in range(B + 1)] + [voll]
                else:
                    fcas_bands[bid_type] = [market_price_floor] + [pmin + b * (pmax - pmin) / B for b in range(B + 1)] + [voll]
    elif '500' in usage:
        bands = [0, 500]
    elif '0' in usage:
        bands = [0, voll]
    else:
        bands = [market_price_floor, voll]
    return bands, fcas_bands


def multischedule(band, battery, current, horizon, E_initial, fcas_flag, fcas_type, multi_flag):
    """Apply battery schedule using multiple processing.

    Args:
        band (float): band price
        battery (helpers.Battery): Battery instance
        current (datetime.datetime): current datetime
        horizon (int): horizon number
        E_initial (float): initial E (charege level)
        fcas_flag (bool): consider FCAS or not
        fcas_type (str): replaced band FCAS type
        multi_flag (bool): participate print multiple FCAS markets

    Returns:
        (float, float, float): discharging (positive) / charging (negative) power value, raise FCAS value, lower FCAS value
    """
    return schedule(current, battery, horizon=horizon, E_initial=E_initial, band=band, method=2, fcas_flag=fcas_flag, fcas_type=fcas_type, multi_flag=multi_flag)


def generate_availabilities(bands, battery, current, horizon, E_initial, fcas_flag, fcas_type, multi_flag):
    """Generate availabilities from battery schedule optimisation results.

    Args:
        bands (list): the list of band prices
        battery (helpers.Battery): Battery instance
        current (datetime.datetime): current datetime
        horizon (int): horizon number
        E_initial (float): initial E (charege level)
        fcas_flag (bool): consider FCAS or not
        fcas_type (str): replaced band FCAS type
        multi_flag (bool): participate print multiple FCAS markets

    Returns:
        (float, float, float): discharging (positive) / charging (negative) power value, raise FCAS value, lower FCAS value
    """
    with Pool(len(bands)) as pool:
        availabilities = pool.starmap(multischedule, zip(bands, repeat(battery), repeat(current), repeat(horizon), repeat(E_initial), repeat(fcas_flag), repeat(fcas_type), repeat(multi_flag)))
        # values = pool.map(multischedule, bands)
        # print('| No. | Price | Availability (MW) |')
        # print('| --- | ----- | ---- |')
        # for n, (p, v) in enumerate(zip(bands, values)):
        #     print(f'| {n + 1} | {p} | {v} |')
        return availabilities


def generate_max_avail(battery, E, dispatch_type):
    """Generate max avail.

    Args:
        battery (helpers.Battery): battery instance
        E (float): battery size
        dispatch_type (str): dispatch type

    Returns:
        float: max avail
    """
    if dispatch_type == 'GENERATOR':
        return (E - battery.Emin) * battery.eff * 12
    elif dispatch_type == 'LOAD':
        return ((battery.Emax - E) * 12) / battery.eff


def generate_band_avail(energy_avail, raise_avail, lower_avail, method, pmax=None):
    """Generate band avail based on battery optimisation results.

    Args:
        energy_avail (float): optimised energy avail
        raise_avail (float): optimised raise FCAS avail
        lower_avail (float): optimised lower FCAS avail
        method (int): calculation method number
        pmax (float): maximum power value

    Returns:
        (float, float, float, float): generator raise FCAS, load raise FCAS, generator lower FCAS, load lower FCAS
    """
    if method == 2:
        if energy_avail >= 0:
            generator_raise = raise_avail
            load_raise = 0
            generator_lower = min(energy_avail, - lower_avail)
            load_lower = max(- lower_avail - energy_avail, 0)
        else:
            generator_raise = max(raise_avail + energy_avail, 0)
            load_raise = min(- energy_avail, 0)
            generator_lower = 0
            load_lower = - lower_avail
    elif method == 1:
        generator_raise = pmax - max(energy_avail, 0)
        load_raise = max(0, - energy_avail)
        generator_lower = max(0, energy_avail)
        load_lower = pmax - max(0, - energy_avail)
    return generator_raise, load_raise, generator_lower, load_lower


def generate_fcas(bid_type, price_bands, band_avails, battery, load_flag, E):
    """Generate FCAS bid.

    Args:
        bid_type (str): FCAS type
        price_bands (list): the list of price bands
        band_avails (list): the list of band availabilities
        battery (helpers.Battery): battery instance
        load_flag (bool): it is a load or not
        E (float): battery size

    Returns:
        FcasBid: the FCAS bid
    """
    fcas_bid = FcasBid([])
    fcas_bid.bid_type = bid_type
    fcas_bid.price_band = price_bands
    fcas_bid.band_avail = band_avails
    tstep = 5 / 60
    C1 = battery.eff * (E - battery.Emin) / tstep
    C2 = (battery.Emax - E) / (tstep * battery.eff)
    Pmax = battery.load.max_capacity
    if (bid_type[:5] == 'RAISE' and not load_flag) or (bid_type[:5] == 'LOWER' and load_flag):
        fcas_bid.max_avail = fcas_bid.enablement_max = min(Pmax, C2 if load_flag else C1)
        fcas_bid.enablement_min = fcas_bid.low_breakpoint = fcas_bid.high_breakpoint = 0
    else:
        fcas_bid.max_avail = Pmax
        fcas_bid.enablement_min = 0
        fcas_bid.low_breakpoint = fcas_bid.high_breakpoint = fcas_bid.enablement_max = Pmax
    return fcas_bid


def generate_reflective_units(battery, bands, availabilities, E, fcas_flag, fcas_bands, fcas_availabilities, usage):
    """Generate units using cost-reflective bidding strategy.

    Args:
        battery (helpers.Battery): battery instance
        bands (list): band prices
        availabilities (list): band availabilities
        E (float): battery size
        fcas_flag (bool): consider FCAS or not
        fcas_bands (dict): FCAS band prices
        fcas_availabilities (dict): FCAS band availabilities
        usage (str): battery usage

    Returns:
        list: battery's generator and load
    """
    for unit in [battery.generator, battery.load]:
        unit.energy = EnergyBid([])
        unit.energy.price_band = bands
        unit.energy.fixed_load = 0
        unit.energy.max_avail = min(unit.max_capacity, generate_max_avail(battery, E, unit.dispatch_type))
        unit.energy.daily_energy_limit = 0
        unit.energy.roc_up = default.MAX_RAMP_RATE
        unit.energy.roc_down = default.MAX_RAMP_RATE
    battery.generator.energy.band_avail = [max(0, avail) for avail, _, _ in availabilities] if fcas_flag else [max(0, avail) for avail in availabilities]
    battery.load.energy.band_avail = [-min(0, avail) for avail, _, _ in availabilities] if fcas_flag else [-min(0, avail) for avail in availabilities]
    if fcas_flag:
        method = 1 if '1' in usage else 2
        for bid_type, fcas_avail in fcas_availabilities.items():
            generator_raise_avail, load_raise_avail, generator_lower_avail, load_lower_avail = [], [], [], []
            for energy_avail, raise_avail, lower_avail in fcas_avail:
                generator_raise, load_raise, generator_lower, load_lower = generate_band_avail(energy_avail, raise_avail, lower_avail, method, battery.generator.max_capacity)
                generator_raise_avail.append(generator_raise)
                load_raise_avail.append(load_raise)
                generator_lower_avail.append(generator_lower)
                load_lower_avail.append(load_lower)
            battery.generator.fcas_bids[bid_type] = generate_fcas(bid_type, fcas_bands[bid_type], generator_raise_avail if bid_type[:5] == 'RAISE' else generator_lower_avail, battery, False, E)
            battery.load.fcas_bids[bid_type] = generate_fcas(bid_type, fcas_bands[bid_type], load_raise_avail if bid_type[:5] == 'RAISE' else load_lower_avail, battery, True, E)
        # battery.generator.fcas_bids['RAISE5MIN'] = generate_fcas('RAISE5MIN', fcas_bands['RAISE5MIN'], generator_raise_avail, battery, False, E)
        # battery.generator.fcas_bids['LOWER5MIN'] = generate_fcas('LOWER5MIN', fcas_bands['LOWER5MIN'], generator_lower_avail, battery, False, E)
        # battery.load.fcas_bids['RAISE5MIN'] = generate_fcas('RAISE5MIN', fcas_bands['RAISE5MIN'], load_raise_avail, battery, True, E)
        # battery.load.fcas_bids['LOWER5MIN'] = generate_fcas('LOWER5MIN', fcas_bands['LOWER5MIN'], load_lower_avail, battery, True, E)
    return [battery.generator, battery.load]


def generate_price_taker_units(battery, bands, availability, E, raise_fcas, lower_fcas, multi_flag):
    """Generate units using price-taker bidding strategy.

        Args:
            battery (helpers.Battery): battery instance
            bands (list): band prices
            availability (float): optimised band availability
            E (float): battery size
            raise_fcas (float): optimised RAISE FCAS value
            lower_fcas (float): optimised LOWER FCAS value
            multi_flag (bool): participate in multiple FCAS markets or not

        Returns:
            list: battery's generator and load
        """
    for unit in [battery.generator, battery.load]:
        unit.total_cleared = 0.0
        unit.offers = []
        unit.initial_mw = 0
        unit.energy = EnergyBid([])
        unit.energy.price_band = bands
        unit.energy.fixed_load = 0
        unit.energy.max_avail = min(unit.max_capacity, generate_max_avail(battery, E, unit.dispatch_type))
        unit.energy.daily_energy_limit = 0
        unit.energy.roc_up = default.MAX_RAMP_RATE
        unit.energy.roc_down = default.MAX_RAMP_RATE
    battery.generator.energy.band_avail = [max(availability, 0), 0]
    battery.load.energy.band_avail = [0, -min(0, availability)]
    generator_raise, load_raise, generator_lower, load_lower = generate_band_avail(availability, raise_fcas, lower_fcas, 2)
    battery.generator.fcas_bids['RAISE5MIN'] = generate_fcas('RAISE5MIN', [bands[0]], [generator_raise], battery, False, E)
    battery.generator.fcas_bids['LOWER5MIN'] = generate_fcas('LOWER5MIN', [bands[0]],  [generator_lower], battery, False, E)
    battery.load.fcas_bids['RAISE5MIN'] = generate_fcas('RAISE5MIN', [bands[0]], [load_raise], battery, True, E)
    battery.load.fcas_bids['LOWER5MIN'] = generate_fcas('LOWER5MIN', [bands[0]], [load_lower], battery, True, E)
    if multi_flag:
        for raise_type, lower_type in (('RAISE6SEC', 'LOWER6SEC'), ('RAISE60SEC', 'LOWER60SEC')):
            battery.generator.fcas_bids[raise_type] = generate_fcas(raise_type, [bands[0]], [generator_raise], battery, False, E)
            battery.generator.fcas_bids[lower_type] = generate_fcas(lower_type, [bands[0]], [generator_lower], battery, False, E)
            battery.load.fcas_bids[raise_type] = generate_fcas(raise_type, [bands[0]], [load_raise], battery, True, E)
            battery.load.fcas_bids[lower_type] = generate_fcas(lower_type, [bands[0]], [load_lower], battery, True, E)
    return [battery.generator, battery.load]


def extract_row(row: list, fcas: dict) -> (float, dict):
    """Extract FCAS from row."""

    def transform(value):
        return 0 if value == '-' else float(value)

    fcas['RAISEREG'] = transform(row[8])
    fcas['RAISE6SEC'] = transform(row[10])
    fcas['RAISE60SEC'] = transform(row[12])
    fcas['RAISE5MIN'] = transform(row[14])
    fcas['LOWERREG'] = transform(row[16])
    fcas['LOWER6SEC'] = transform(row[18])
    fcas['LOWER60SEC'] = transform(row[20])
    fcas['LOWER5MIN'] = transform(row[22])
    return float(row[2]), fcas


def read_dispatchload(dispatchload_path):
    """Read battery's generation and load from DISPATCHLOAD file.

    Args:
        dispatchload_path (pathlib.Path): path to DISPATCHLOAD file

    Returns:
        (float, float, dict, dict): generation, load, generator's FCAS, load's FCAS
    """
    g, l, generator_fcas, load_fcas = 0, 0, {}, {}
    with dispatchload_path.open('r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[1] == 'G':
                g, generator_fcas = extract_row(row, generator_fcas)
            elif row[1] == 'L':
                l, load_fcas = extract_row(row, load_fcas)
    return g, l, generator_fcas, load_fcas


def exist_errors(g, l, generator_fcas, load_fcas, battery, E, fcas_flag, multi_flag):
    """Check if there are any errors.

    Args:
        g (float): generation (in MW)
        l (float): load (in MW)
        generator_fcas (float): generator's FCAS value (in MW)
        load_fcas (float): load's FCAS value (in MW)
        battery (helpers.Battery): battery instance
        E (float): battery charge level (in MWh)
        fcas_flag (bool): consider FCAS or not
        multi_flag (bool): participate in multiple FCAS markets or not

    Returns:
        bool: whether there is any errors or not
    """
    if g > 0 and l > 0:
        print('Energy error!')
        return True
    if fcas_flag:
        bid_types = [('RAISE5MIN', 'LOWER5MIN'), ('RAISE6SEC', 'LOWER6SEC'), ('RAISE60SEC', 'LOWER60SEC')] if multi_flag else [('RAISE5MIN', 'LOWER5MIN')]
        for raise_type, lower_type in bid_types:
            raise_fcas = generator_fcas[raise_type] + load_fcas[raise_type]
            lower_fcas = generator_fcas[lower_type] + load_fcas[lower_type]
            if g - l + raise_fcas > battery.generator.max_capacity and abs(g - l + raise_fcas - battery.generator.max_capacity) > 0.1:
                print(f'{raise_type} Capacity Error!')
                return True
            if g - l - lower_fcas < -battery.load.max_capacity and abs(g - l - lower_fcas + battery.load.max_capacity) > 0.1:
                print(f'{lower_type} Capacity Error!')
                return True
            tstep = 5 / 60
            if E + (l * battery.eff - g / battery.eff) * tstep + lower_fcas * battery.eff * tstep > battery.Emax and abs(E + (l * battery.eff - g / battery.eff) * tstep + lower_fcas * battery.eff * tstep - battery.Emax) > 0.1:
                print(f'Strict {lower_type} Transition Error!')
                if E + (l * battery.eff - g / battery.eff) * tstep + lower_fcas * tstep > battery.Emax and abs(E + (l * battery.eff - g / battery.eff) * tstep + lower_fcas * tstep - battery.Emax) > 0.1:
                    print(f'{lower_type} Transition Error!')
                    return True
            if E + (l * battery.eff - g / battery.eff) * tstep - raise_fcas * tstep / battery.eff < battery.Emin and abs(E + (l * battery.eff - g / battery.eff) * tstep - raise_fcas * tstep / battery.eff - battery.Emin) > 0.1:
                print(f'Strict {raise_type} Transition Error!')
                if E + (l * battery.eff - g / battery.eff) * tstep - raise_fcas * tstep < battery.Emin and abs(E + (l * battery.eff - g / battery.eff) * tstep - raise_fcas * tstep - battery.Emin) > 0.1:
                    print(f'{raise_type} Transition Error!')
                    return True
    return False


def rolling_horizon(start, battery, usage, days=1, debug_current=None, batt_no=None, predefined_battery=None):
    """Rolling horizon for optimisation.

    Args:
        start (datetime.datetime): start datetime
        battery (helpers.Battery): battery instance
        usage (str): battery usage
        days (int): number of days to optimise
        debug_current (datetime.datetime): current datetime (used to debug)
        batt_no (str): battery number (used to debug)

    Returns:
        None
    """
    fcas_flag, multi_flag, bands, der_flag = 'FCAS' in usage, 'multi' in usage, None, 'DER' in usage
    if fcas_flag:
        fcas_types = ['RAISE5MIN', 'LOWER5MIN', 'RAISE6SEC', 'LOWER6SEC', 'RAISE60SEC', 'LOWER60SEC'] if multi_flag else ['RAISE5MIN', 'LOWER5MIN']
    else:
        fcas_types = []
    HORIZONS = 1
    # HORIZONS = 288 * days
    result_path = battery.bat_dir / f'{default.get_case_datetime(start)}.csv'
    if debug_current:
        bands, fcas_bands = generate_bands(start, usage)
    if result_path.is_file():
        times, socs, prices = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
        mode = 'a'
        if debug_current is None:
            start_horizon = len(times)
            E_initial = 0.5 * battery.size if start_horizon == 0 else socs[-1] * battery.size / 100
        else:
            for i, t in enumerate(times):
                if t == debug_current:
                    start_horizon = i
                    E_initial = (0.5 * battery.size) if start_horizon == 0 else (socs[i - 1] * battery.size / 100)
                    break
    else:
        mode = 'w'
        start_horizon = 0
        E_initial = 0.5 * battery.size
    with result_path.open(mode) as result_file:
        writer = csv.writer(result_file)
        row = []
        if fcas_flag:
            for bid_type in fcas_types:
                row += [f'Generator {bid_type}', f'Load {bid_type}', f'Price {bid_type}']
        writer.writerow(['Datetime'] + row + ['Generator (MW)', 'Load (MW)', 'E (MWh)', 'SOC (%)', 'Price ($/MWh)'])
        for horizon in range(start_horizon, HORIZONS):
            battery = Battery(battery.size, battery.generator.max_capacity, usage=usage)
            current = start + horizon * default.FIVE_MIN
            if horizon % 288 == 0:
                bands, fcas_bands = generate_bands(current, usage)
            elif bands is None:
                current_start, _ = default.datetime_to_interval(current)
                bands, fcas_bands = generate_bands(current_start, usage)
            if 'Cost-reflective' in usage:
                if battery.size == 0:
                    energy_availabilities = [[0, 0, 0]]
                    fcas_availabilities = {'RAISE5MIN': [[0, 0, 0]], 'RAISE6SEC': [[0, 0, 0]], 'RAISE60SEC': [[0, 0, 0]], 'LOWER5MIN': [[0, 0, 0]], 'LOWER6SEC': [[0, 0, 0]], 'LOWER60SEC': [[0, 0, 0]]}
                else:
                    energy_availabilities = generate_availabilities(bands, battery, current, horizon, E_initial, fcas_flag, None, multi_flag)
                    if fcas_flag:
                        fcas_availabilities = {}
                        for bid_type in fcas_types:
                            fcas_availabilities[bid_type] = generate_availabilities(fcas_bands[bid_type], battery, current, horizon, E_initial, fcas_flag, bid_type, multi_flag)
                    else:
                        fcas_availabilities = None

                custom_units = generate_reflective_units(battery, bands, energy_availabilities, E_initial, fcas_flag, fcas_bands, fcas_availabilities, usage)
                if 'TT' in usage:
                    return battery
                dispatchload_path, rrp, fcas_rrp = formulate(start, horizon, 'dispatch', custom_unit=custom_units,
                                                             path_to_out=default.DEBUG_DIR if debug_current else battery.bat_dir,  # TODO
                                                             dispatchload_flag=(horizon != 0),
                                                             dispatchload_path=(battery.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(debug_current)}.csv') if debug_current else None,
                                                             # dispatchload_path=(default.DEBUG_DIR / f'dispatchload_{default.get_case_datetime(debug_current)}-batt{batt_no}.csv') if debug_current else None,
                                                             debug_flag=True if debug_current else False,
                                                             batt_no=batt_no)
                g, l, generator_fcas, load_fcas = read_dispatchload(dispatchload_path)
            elif 'Basic' in usage:
                if fcas_flag:
                    availability, raise_fcas, lower_fcas = schedule(current, battery, horizon=horizon, E_initial=E_initial, method=2, fcas_flag=fcas_flag, multi_flag=multi_flag)
                else:
                    availability = schedule(current, battery, horizon=horizon, E_initial=E_initial, method=2, fcas_flag=fcas_flag)
                    raise_fcas, lower_fcas = 0, 0
                g = max(availability, 0)
                l = - min(availability, 0)
                rrp, rrp_record, fcas_rrp, _ = read_dispatch_prices(current, 'dispatch', True, battery.load.region_id, fcas_flag=fcas_flag)
                generator_fcas, load_fcas = {}, {}
                generator_fcas['RAISE5MIN'], load_fcas['RAISE5MIN'], generator_fcas['LOWER5MIN'], load_fcas['LOWER5MIN'] = generate_band_avail(availability, raise_fcas, lower_fcas, 2)
                if multi_flag:
                    for part_bid_type in ['6SEC', '60SEC']:
                        generator_fcas[f'RAISE{part_bid_type}'], load_fcas[f'RAISE{part_bid_type}'], generator_fcas[f'LOWER{part_bid_type}'], load_fcas[f'LOWER{part_bid_type}'] = generate_band_avail(availability, raise_fcas, lower_fcas, 2)
            elif 'Price-taker' in usage:
                if fcas_flag:
                    availability, raise_fcas, lower_fcas = schedule(current, battery, horizon=horizon, E_initial=E_initial, method=2, fcas_flag=fcas_flag)
                else:
                    times, availability = schedule(current, battery, horizon=horizon, E_initial=E_initial, method=2, fcas_flag=fcas_flag, der_flag=der_flag)
                    raise_fcas, lower_fcas = 0, 0
                if der_flag:
                    g, l, rrp = formulate_sequence(current, battery.size, usage, availability, times, first_horizon_flag=(horizon==0), predefined_battery=predefined_battery)
                else:
                    custom_units = generate_price_taker_units(battery, bands, availability, E_initial, raise_fcas, lower_fcas, multi_flag)
                    dispatchload_path, rrp, fcas_rrp = formulate(start, horizon, 'dispatch', custom_unit=custom_units,
                                                                 path_to_out=battery.bat_dir,
                                                                 dispatchload_flag=False if horizon == 0 else True)
                    g, l, generator_fcas, load_fcas = read_dispatchload(dispatchload_path)
            # if exist_errors(g, l, generator_fcas, load_fcas, battery, E_initial, fcas_flag, multi_flag):
            #     return None
            E_initial += (l * battery.eff - g / battery.eff) * 5 / 60
            row = []
            if fcas_flag:
                for bid_type in fcas_types:
                    row += [generator_fcas[bid_type], load_fcas[bid_type], fcas_rrp[bid_type]]
            writer.writerow([current] + row + [g, l, E_initial, 0 if battery.size == 0 else E_initial / battery.size * 100, rrp])


def calculate_revenue(start, battery, usage, print_flag=0, sign=''):
    """Calculate total revenue of battery.

    Args:
        start (datetime.datetime): start datetime
        battery (helpers.Battery): battery instance
        usage (str): battery usage
        print_flag (str): used to identify different print content
        sign (str): used to identify different files

    Returns:
        float: total revenue
    """
    times, generations, loads, prices, generator_fcas, load_fcas, fcas_prices = read_battery_power(battery.bat_dir / f'{default.get_case_datetime(start)}{sign}.csv', usage)
    energy_revenue, fcas_revenue = [], {}
    if len(times) % 288 != 0:
        print('Interval Number Error!')
    revenue = 0
    if print_flag == 3:
        print('Datetime | Generator | Load | Price')
        print('---------|-----------|------|------')
    elif print_flag == 1:
        print('Day | Energy Revenue | FCAS Revenue | Total')
        print('----|----------------|--------------|------')
    for n, (t, g, l, p) in enumerate(zip(times, generations, loads, prices)):
        # if n >= 288:
        #     break
        if n % 287 == 0 and n > 0:
            energy_revenue.append(revenue)
            revenue = 0
        if g > 0 and l > 0:
            print('Energy Error!')
        if (g > 0 or l > 0) and print_flag == 3:
            print(f'`{t}` | {g:.2f} | {l:.2f} | {p:.2f}')
        revenue += (g - l) * p * 5 / 60
    if 'FCAS' in usage:
        for bid_type in fcas_prices.keys():
            fcas_revenue[bid_type] = []
            for n, (t, gen_value, load_value, price) in enumerate(zip(times, generator_fcas[bid_type], load_fcas[bid_type], fcas_prices[bid_type])):
                # if n >= 288:
                #     break
                if n % 287 == 0 and n > 0:
                    fcas_revenue[bid_type].append(revenue)
                    revenue = 0
                revenue += (gen_value + load_value) * price * 5 / 60
    total_revenue = 0
    for n in range(len(energy_revenue)):
        total_fcas_revenue = 0
        if 'FCAS' in usage:
            for revenue in fcas_revenue.values():
                total_fcas_revenue += revenue[n]
        total_revenue += energy_revenue[n] + total_fcas_revenue
        if print_flag == 1:
            print(f'{n + 1} | {energy_revenue[n]:.2f} | {total_fcas_revenue:.2f} | {energy_revenue[n] + total_fcas_revenue:.2f}')
    if print_flag == 1:
        print(f'Total | {sum(energy_revenue):.2f} | {total_revenue - sum(energy_revenue):.2f} | {total_revenue:.2f}')
    elif print_flag == 2:
        print(f'{usage} | {sum(energy_revenue):.2f} | {total_revenue - sum(energy_revenue):.2f} | {total_revenue:.2f}')
    return total_revenue


def different_batteries(battery, usage, days, start):
    """Optimise for different batteries.

    Args:
        battery (helpers.Battery): battery instance
        usage (str): battery usage
        days (int): total number of optimisation days
        start (datetime.datetime): start datetime

    Returns:
        None
    """
    rolling_horizon(start, battery, usage, days)
    if days == 7:
        times, socs, prices = read_battery_optimisation(battery.bat_dir / f'{default.get_case_datetime(start)}.csv')
        path_to_fig = battery.bat_dir / f'Comparison {default.get_case_datetime(start)}.jpg'
        if 'Basic' in usage:
            plot_soc(times, prices, socs, path_to_fig)
        else:
            original_prices = []
            # print('Datetime | AEMO record | Our NEMDE result | Price after battery participation')
            # print('---------|-------------|------------------|----------------------------------')
            for t, p in zip(times, prices):
                rrp, rrp_record, _, _ = read_dispatch_prices(t, 'dispatch', True, battery.generator.region_id)
                # print(f'`{t}` | {rrp_record} | {rrp} | {p}')
                original_prices.append(rrp)
            plot_soc(times, [prices, original_prices], socs, path_to_fig)
            # path_to_soc = battery.bat_dir / f'SOC {default.get_case_datetime(start)}.jpg'
            # plot_soc(times, _, socs, path_to_soc, price_flag=False)
            # path_to_price = battery.bat_dir / f'Price {default.get_case_datetime(start)}.jpg'
            # plot_soc(times, [prices, original_prices], _, path_to_price, soc_flag=False)
            # plot_soc(times, prices, socs, path_to_fig)
        # path_to_csv = battery.bat_dir / f'{default.get_case_datetime(start)}.csv'
        # times, generations, loads, prices, r5_values, r5_prices, l5_values, l5_prices = read_battery_power(path_to_csv, usage)
        # path_to_fig = battery.bat_dir / f'RAISE5MIN_{default.get_case_datetime(start)}.jpg'
        # plot_power(times, r5_prices, r5_values, 'RAISE5MIN', path_to_fig)
        # path_to_fig = battery.bat_dir / f'LOWER5MIN_{default.get_case_datetime(start)}.jpg'
        # plot_power(times, l5_prices, l5_values, 'LOWER5MIN', path_to_fig)
        # path_to_fig = battery.bat_dir / f'ENERGY_{default.get_case_datetime(start)}.jpg'
        # plot_power(times, prices, [g - l for g, l in zip(generations, loads)], 'ENERGY', path_to_fig)

        # times, prices, socs = read_forecast_soc(start, battery.bat_dir)
        # path_to_fig = battery.bat_dir / 'forecast' / f'{default.get_case_datetime(start)}.jpg'
        # plot_soc(times, prices, socs, path_to_fig)
        # return calculate_revenue(start, battery, usage)
    return None


def optimise(start, batteries, usage, prepare_flag=False, num_usage=16):
    """Optimise for 7 days.

    Args:
        start (datetime.datetime): start datetime
        batteries (list): a list of batteries
        usage (str): battery usage
        prepare_flag (bool): True haven't done predispatch and got prices; False otherwise
        num_usage (int): number of cores used for multiprocessing

    Returns:
        None
    """
    if prepare_flag:
        for days in range(1, 8):
            current_date = start + default.ONE_DAY * (days - 1)
            if days > 0:
                multiformulate(current_date, 'dispatch', 32, True if days == 1 else False)
                multiformulate(current_date.replace(minute=30), 'predispatch', num_usage)
                multiformulate(current_date, 'p5min', num_usage, True if days == 1 else False)
            with Pool(len(batteries)) as pool:
                revenues = pool.starmap(different_batteries, zip(batteries, repeat(usage), repeat(days), repeat(start)))
    else:
        days = 7
        with Pool(len(batteries)) as pool:
            revenues = pool.starmap(different_batteries, zip(batteries, repeat(usage), repeat(days), repeat(start)))


def compare_revenue_by_day(start, battery, usage):
    """Compare revenue of each day for one battery.

    Args:
        start (datetime.datetime): start datetime
        battery (helpers.Battery): battery instance
        usage (str): battery usage

    Returns:
        None
    """
    print('Day | Energy Revenue | FCAS Revenue | Total')
    print('----|----------------|--------------|------')
    calculate_revenue(start, battery, usage, 1)


def compare_revenue_by_size(start, energies, batteries, usage, sign):
    """Compare revenue rate of different battery sizes.

    Args:
        start (datetime.datetime): start datetime
        energies (list): different battery sizes
        batteries (list): different batteries
        usage (str): battery usage
        sign (str): used to identify different files

    Returns:
        None
    """
    revenues = [calculate_revenue(start, battery, usage, print_flag=1, sign=sign) for battery in batteries]
    rates = [r / e for e, r in zip(energies, revenues)]
    print('| Battery Size (MWh) | Revenue ($) | Revenue / Battery Size ($ / MWh) |')
    print('| ------------------ | ----------- | -------------------------------- |')
    for e, re, r in zip(energies, revenues, rates):
        print(f'| {e} | {re:.2f} | {r:.2f} |')
    # plot_revenues(energies, revenues, 'Battery Size (MWh)', 'Revenue ($)', usage)
    plot_revenues(energies, rates, 'Battery Size (MWh)', 'Revenue Rate ($/MWh)', usage, 'Revenue Rate')


def calculate_revenue_and_volatility(energies, usage, sign=''):
    """Calculate revenue and volatility of different batteries.

    Args:
        energies (list): different battery sizes
        usage (str): battery usage
        sign (str): used to identify different files

    Returns:
        (list, list, list): revenue rates, standard deviations, means
    """
    batteries = generate_batteries(energies, usage)
    revenues = [calculate_revenue(start, b, usage, print_flag=1, sign=sign) for b in batteries]
    rates = [r / e for e, r in zip(energies, revenues)]
    mean, var, std = calculate_volatility(start, batteries, usage)
    return rates, std, mean


def compare_revenue_by_usage_and_size(start, sign=''):
    """Compare revenues of different batteries with different usages.

    Args:
        start (datetime.datetime): start datetime
        sign (str): used to identify different files

    Returns:
        None
    """
    e1 = [0.03, 3, 30, 120, 240, 360, 480, 600, 720, 960, 1200, 2100, 3000]  # Cost-reflective + multiple FCAS
    # e1 = [0.03, 3, 30, 120, 240, 360, 480, 720]  # Price-taker
    # e2 = [0.03, 3, 30, 120, 240, 360, 480, 720, 960, 1200, 2100, 3000]  # Price-taker + multiple FCAS

    u1 = 'Cost-reflective + multiple FCAS'
    u2 = 'Price-taker500 + multiple FCAS'
    u3 = 'Cost-reflective'
    u4 = 'Price-taker'

    rate1, std1, mean1 = calculate_revenue_and_volatility(e1, u1, sign)
    rate2, std2, mean2 = calculate_revenue_and_volatility(e1, u2, sign)
    # rate3, std3 = calculate_revenue_and_volatility(e1, u3, sign)
    # rate4, std4 = calculate_revenue_and_volatility(e1, u4, sign)

    # print(f'Battery Capacity (MWh) | {u1} | {u2} | {u3} | {u4}')
    # for e, r1, r2, r3, r4 in zip(e1, rate1, rate2, rate3, rate4):
    #     print(f'{e} | {r1:.2f} | {r2:.2f} | {r3:.2f} | {r4:.2f}')

    plot_revenues(e1, rate1, 'Battery Size (MWh)', 'Revenue Rate', u1, 'Revenue Rate')
    plot_revenues(e1, rate2, 'Battery Size (MWh)', 'Revenue Rate', u2, 'Revenue Rate')
    plot_revenues(e1, rate1, 'Battery Size (MWh)', 'Revenue Rate ($/MWh)', u1[:-16], 'Revenue Comparison', e1, rate2, u2[:-19])
    plot_revenues(e1, std1, 'Battery Size (MWh)', 'Standard Deviation', u1, 'Standard Deviation')
    plot_revenues(e1, std2, 'Battery Size (MWh)', 'Standard Deviation', u2, 'Standard Deviation')
    plot_revenues(e1, std1, 'Battery Size (MWh)', 'Standard Deviation', u1[:-16], 'Standard Deviation', e1, std2, u2[:-19])
    plot_revenues(e1, mean1, 'Battery Size (MWh)', 'Average Price ($/MWh)', u1[:-16], 'Average Price', e1, mean2, u2[:-19])


def compare_soc_by_size(start, batteries):
    times0, socs0, prices0 = read_battery_optimisation(batteries[0].bat_dir / f'{default.get_case_datetime(start)}.csv')
    times1, socs1, prices1 = read_battery_optimisation(batteries[1].bat_dir / f'{default.get_case_datetime(start)}.csv')
    print('Datetime | SOC 1 (%) | SOC 2 (%) | Price 1 | Price 2 | Without Battery')
    print('---------|-------|-------|---------|---------|----------------')
    for t0, t1, s0, s1, p0, p1 in zip(times0, times1, socs0, socs1, prices0, prices1):
        if t0 != t1:
            print('error!')
        if t0 - start >= datetime.timedelta(hours=24):
            return None
        rrp, rrp_record, _, _ = read_dispatch_prices(t0, 'dispatch', True, batteries[0].generator.region_id,
                                                     path_to_out=default.OUT_DIR / 'sequence')
        if p0 != p1:
            print(f'`{t0}` | {s0:.2f} | {s1:.2f} | {p0:.2f} | {p1:.2f} | {rrp:.2f}')
            # print(f'**`{t0}`** | **{s0:.2f}** | **{s1:.2f}** | **{p0:.2f}** | **{p1:.2f}** | **{rrp:.2f}**')
        # else:
        #     print(f'`{t0}` | {s0:.2f} | {s1:.2f} | {p0:.2f} | {p1:.2f} | {rrp:.2f}')


def compare_revenue_by_usage(start):
    energy = 3000
    power = int(energy * 2 / 3)
    print(f'**{power}MW/{energy}MWh**\n')
    print('Strategy | Energy Revenue | FCAS Revenue | Total')
    print('-------- | -------------- | ------------ | -----')
    for usage in ['Basic price-taker',
                  'Basic price-taker + FCAS',
                  'Basic price-taker + multiple FCAS',
                  'Price-taker',
                  'Price-taker + FCAS',
                  'Price-taker + multiple FCAS',
                  'Cost-reflective',
                  'Cost-reflective + FCAS',
                  'Cost-reflective + multiple FCAS',
                  'Cost-reflective + multiple FCAS + new band price']:
        battery = Battery(energy, power, usage=usage)
        calculate_revenue(start, battery, usage, 2)


def calculate_volatility(start, batteries, usage):
    """Caluate volatility for different batteries.

    Args:
        start (datetime.datetime): start datetime
        batteries (list): different batteries
        usage (str): battery usage

    Returns:
        (list, list, list): means, variances, standard deviations
    """
    print('Battery Size | Mean | Variance | Standard Deviation')
    print('-------------|------|----------|-------------------')
    means, vars, stds = [], [], []
    for battery in batteries:
        times, generations, loads, prices, generator_fcas, load_fcas, fcas_prices = read_battery_power(battery.bat_dir / f'{default.get_case_datetime(start)}.csv', usage)
        print(f'{battery.size} | {np.mean(prices):.2f} | {np.var(prices):.2f} | {np.std(prices):.2f}')
        means.append(np.mean(prices))
        vars.append(np.var(prices))
        stds.append(np.std(prices))
    return means, vars, stds


if __name__ == '__main__':
    # energies = [3, 15, 30, 45, 60, 75, 90, 180, 270, 300, 360, 450, 540, 630, 720, 810, 900]  # price-taker
    # energies = [0.03, 3, 30, 120, 240, 360, 480, 720, 960, 1200, 2100, 3000]

    start_datetime = datetime.datetime.now()
    print(f'Start: {start_datetime}')
    # usage = 'Cost-reflective + multiple FCAS'
    # usage = 'Price-taker500 + multiple FCAS'

    usage = 'DER Price-taker NEW'
    start = datetime.datetime(2021, 9, 12, 4, 5)
    # start = datetime.datetime(2021, 7, 18, 4, 5)
    energies = [0]
    batteries = generate_batteries(energies, usage)
    rolling_horizon(start, batteries[0], usage)

    # DER Cost-reflective
    # usage = 'Cost-reflective TT'
    # start = datetime.datetime(2021, 9, 12, 4, 5)
    # energies = [30]
    # batteries = generate_batteries(energies, usage)
    # b = rolling_horizon(start, batteries[0], usage)
    # usage = 'DER Price-taker TT'
    # b.update_usage(usage)
    # batteries = generate_batteries(energies, usage)
    # rolling_horizon(start, batteries [0], usage, predefined_battery=b)

    # compare_revenue_by_size(start, energies, batteries, usage, '')
    # compare_revenue_by_usage_and_size(start)
    # compare_soc_by_size(start, batteries, usage)
    end_datetime = datetime.datetime.now()
    print(f'End: {end_datetime}')
    print(f'Cost: {end_datetime - start_datetime}')

    # TODO: Generate smarter price bands
    # for region_id in ['NSW1', 'SA1', 'VIC1', 'TAS1', 'QLD1']:
    # region_id = 'NSW1'
    # extract_prices(region_id)

    # TODO: Compare SOCs
    # start = datetime.datetime(2020, 9, 1, 4, 5)
    # b1 = Battery(30, 20, usage='basic-price-taker')
    # b2 = Battery(300, 200, usage='basic-price-taker')
    # times1, socs1, prices1 = read_battery_optimisation(b1.bat_dir / f'{default.get_case_datetime(start)}.csv')
    # times2, socs2, prices2 = read_battery_optimisation(b2.bat_dir / f'{default.get_case_datetime(start)}.csv')
    # for t, s1, s2 in zip(times1, socs1, socs2):
    #     if s1 != s2 and abs(s1 - s2) > 0.1:
    #         print(t, s1, s2)