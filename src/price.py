import default, read


def preprocess_prices(current, custom_flag, battery, k):
    """ Read and preprocess prices.

    Args:
        current (datetime.datetime): current datetime
        custom_flag (bool): read custom results or AEMO records
        battery (helpers.Battery): custom Battery class
        k (int): iteration number

    Returns:
        (list, datetime.datetime, list, list, dict, dict, list, list): times, predispatch time, prices, AEMO prices, FCAS prices, AEMO FCAS prices, raise FCAS record, lower FCAS record
    """
    path_to_out = default.RECORD_DIR if k == 0 else battery.bat_dir
    p5min_times, p5min_prices, aemo_p5min_prices, p5min_fcas_prices, aemo_p5min_fcas_prices = read.read_prices(current, 'p5min', custom_flag,
                                                               battery.region_id, k, path_to_out, fcas_flag=True)
    p5min_raise_fcas, p5min_lower_fcas = read.read_p5min_fcas(current, battery.region_id)
    predispatch_time = default.get_predispatch_time(current)
    predispatch_times, predispatch_prices, aemo_predispatch_prices, predispatch_fcas_prices, aemo_predispatch_fcas_prices = read.read_prices(predispatch_time, 'predispatch', custom_flag, battery.region_id, k, path_to_out, fcas_flag=True)
    fcas_prices, aemo_fcas_prices = {}, {}
    for bid_type in p5min_fcas_prices.keys():
        # fcas_prices[bid_type] = p5min_fcas_prices[bid_type] + predispatch_fcas_prices[bid_type][2:]
        # aemo_fcas_prices[bid_type] = aemo_p5min_fcas_prices[bid_type] + aemo_predispatch_fcas_prices[bid_type][2:]
        fcas_prices[bid_type] = p5min_fcas_prices[bid_type][:6] + predispatch_fcas_prices[bid_type][1:]
        aemo_fcas_prices[bid_type] = aemo_p5min_fcas_prices[bid_type][:6] + aemo_predispatch_fcas_prices[bid_type][1:]
    predispatch_raise_fcas, predispatch_lower_fcas = read.read_predispatch_fcas(predispatch_time, battery.region_id)
    # return p5min_times + predispatch_times[2:], predispatch_time, p5min_prices + predispatch_prices[2:], aemo_p5min_prices + aemo_predispatch_prices[2:], fcas_prices, aemo_fcas_prices, p5min_raise_fcas + predispatch_raise_fcas[2:], p5min_lower_fcas + predispatch_lower_fcas[2:]
    return p5min_times[:6] + predispatch_times[1:], predispatch_time, p5min_prices[:6] + predispatch_prices[1:], aemo_p5min_prices[:6] + aemo_predispatch_prices[1:], fcas_prices, aemo_fcas_prices, p5min_raise_fcas[:6] + predispatch_raise_fcas[1:], p5min_lower_fcas[:6] + predispatch_lower_fcas[1:]


def extend_forcast_horizon(current, times, prices, aemo_prices, fcas_prices, aemo_fcas_prices, custom_flag, battery, k, raise_fcas_records, lower_fcas_records, fcas_flag):
    """ Extend forecast horizon to 24hrs.

    Args:
        current (datetime.datetime): current datetime
        times (list): a list of datetimes
        prices (list): a list of prices
        aemo_prices (list): a list of AEMO price records
        fcas_prices (dict): a dictionary of FCAS prices
        aemo_fcas_prices (dict): a dictionary of AEMO FCAS price records
        custom_flag (bool): use custom results or AEMO records
        battery (helpers.Battery): Battery instance
        k (int): iteration number
        raise_fcas_records (list): a list of raise FCAS record
        lower_fcas_records (list): a list of lower FCAS record

    Returns:
        (list, list, list, dict, dict, datetime.datetime, list, list): times, prices, AEMO prices, FCAS prices, AEMO FCAS prices, end datetime, raise FCAS record, lower FCAS record
    """
    # path_to_out = default.OUT_DIR if k == 0 else battery.bat_dir
    path_to_out = default.RECORD_DIR if not custom_flag else battery.bat_dir
    # path_to_out = battery.bat_dir
    # path_to_out = default.RECORD_DIR
    end_time = current + default.ONE_DAY - default.FIVE_MIN
    extend_time = end = times[-1]
    extended_times = [None for _ in range(len(times))]
    if extend_time < end_time:
        # 30min-based
        # while end_time - extend_time > default.THIRTY_MIN:
        #     extend_time += default.THIRTY_MIN
        #     price, _ = read.read_trading_prices(extend_time - default.ONE_DAY, custom_flag, battery.load.region_id, k, path_to_out)
        #     aemo_price, _ = read.read_trading_prices(extend_time, False, battery.load.region_id)
        #     prices.append(price)
        #     aemo_prices.append(aemo_price)
        #     times.append(extend_time)
        # 5min-based
        while extend_time <= end_time:
            extend_time += default.THIRTY_MIN
            # extend_time += default.FIVE_MIN
            price, aemo_price, fcas_price, aemo_fcas_price = read.read_dispatch_prices(min(extend_time, end_time) - default.ONE_DAY, 'dispatch', custom_flag, battery.region_id, k, path_to_out, fcas_flag=fcas_flag)
            extended_times.append(min(extend_time, end_time) - default.ONE_DAY)
            prices.append(price)
            if fcas_flag:
                aemo_prices.append(aemo_price)
                for bid_type in fcas_prices.keys():
                    fcas_prices[bid_type].append(fcas_price[bid_type])
                    aemo_fcas_prices[bid_type].append(aemo_fcas_price[bid_type])
                dispatch_raise_record, dispatch_lower_record = read.read_dispatch_fcas(min(extend_time, end_time) - default.ONE_DAY, battery.region_id)
                raise_fcas_records.append(dispatch_raise_record)
                lower_fcas_records.append(dispatch_lower_record)
            # times.append(extend_time)  # Make the last datetime is PREDISPATCH i.e. end with 00 or 30.
            times.append(min(extend_time, end_time))  # The exact end datetime
    if extend_time > end_time:
        while extend_time >= end_time + default.THIRTY_MIN:
            extended_times.pop()
            times.pop()
            prices.pop()
            if fcas_flag:
                aemo_prices.pop()
                for bid_type in fcas_prices.keys():
                    fcas_prices[bid_type].pop()
                    aemo_fcas_prices[bid_type].pop()
                raise_fcas_records.pop()
                lower_fcas_records.pop()
            extend_time = times[-1]
        # times[-1] = min(extend_time, end_time)  # The exact end datetime
    return times, prices, aemo_prices, fcas_prices, aemo_fcas_prices, raise_fcas_records, lower_fcas_records, extended_times


def process_prices_by_interval(current, custom_flag, battery, k, fcas_flag):
    """Extract prices and extend horizon.

    Args:
        current (datetime.datetime): current datetime
        custom_flag (bool): use our custom results or not
        battery (helpers.Battery): battery instance
        k (int): iteration number

    Returns:
        (list, list, datetime.datetime, list, dict, dict, datetime.datetime, dict, dict): times, prices,
        predispatch time, AEMO prices, FCAS prices, AEMO FCAS prices, end, RAISE FCAS records, LOWER FCAS records
    """
    times, predispatch_time, prices, aemo_prices, fcas_prices, aemo_fcas_prices, raise_fcas_records, lower_fcas_records = preprocess_prices(current, custom_flag, battery, k)
    times, prices, aemo_prices, fcas_prices, aemo_fcas_prices, raise_fcas_records, lower_fcas_records, extended_times = extend_forcast_horizon(current, times, prices, aemo_prices, fcas_prices, aemo_fcas_prices, custom_flag, battery, k, raise_fcas_records, lower_fcas_records, fcas_flag)
    return times, prices, predispatch_time, aemo_prices, fcas_prices, aemo_fcas_prices, raise_fcas_records, lower_fcas_records, extended_times


def process_given_prices_by_interval(current, custom_flag, battery, k, p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices):
    """Extend given prices.

    Args:
        current (datetime.datetime): current datetime
        custom_flag (bool): use our custom results or not
        battery (helpers.Battery): battery instance
        k (int): iteration number
        p5min_times (list): given P5MIN datetimes
        p5min_prices (list): given P5MIN prices
        aemo_p5min_prices (list): given AEMO P5MIN price records
        predispatch_times (list): given PREDISPATCH datetimes
        predispatch_prices (list): given PREDISPATCH prices
        aemo_predispatch_prices (list): given AEMO PREDISPATCH price records

    Returns:
        (list, list, list, list, datetime.datetime, list, datetime.datetime): datetimes, prices, P5MIN prices,
        PREDISPATCH prices, PREDISPATCH datetime, AEMO prices, end datetime
    """
    predispatch_times, predispatch_prices, aemo_predispatch_prices = predispatch_times[2:], predispatch_prices[2:], aemo_predispatch_prices[2:]
    predispatch_time = default.get_predispatch_time(current)
    times, prices, aemo_prices = extend_forcast_horizon(current, p5min_times + predispatch_times, p5min_prices + predispatch_prices, aemo_p5min_prices + aemo_predispatch_prices, custom_flag, battery, k)
    return times, prices, p5min_prices, predispatch_prices, predispatch_time, aemo_prices


def process_prices_by_period(current, horizon, custom_flag, battery, k):
    """ Used to extract predispatch prices and calculate average prices as period prices. No longer applicable because
        NEMDE has been upgraded to 5min settlement.
    """
    r = horizon % 6
    p5min_times, predispatch_times, p5min_prices, predispatch_prices, predispatch_time, aemo_p5min_prices, aemo_predispatch_prices, raise_fcas_records, lower_fcas_records = preprocess_prices(current, custom_flag, battery, k)
    times = p5min_times + predispatch_times
    price1 = sum([read.read_dispatch_prices(current - n * default.FIVE_MIN, 'dispatch', custom_flag, battery.generator.region_id, k=0, path_to_out=default.OUT_DIR)[0] for n in range(1, r + 1)] + p5min_prices[:6-r]) / 6
    aemo_price1 = sum([read.read_dispatch_prices(current - n * default.FIVE_MIN, 'dispatch', custom_flag, battery.generator.region_id, k=0, path_to_out=default.OUT_DIR)[1] for n in range(1, r + 1)] + aemo_p5min_prices[:6-r]) / 6
    price2 = sum(p5min_prices[6 - r: 12 - r]) / 6
    aemo_price2 = sum(aemo_p5min_prices[6 - r: 12 - r]) / 6
    price3 = (sum(p5min_prices[-r:]) + (6 - r) * predispatch_prices[0]) / 6
    aemo_price3 = (sum(aemo_p5min_prices[-r:]) + (6 - r) * predispatch_prices[0]) / 6
    prices = [price1] * (6 - r) + [price2] * 6 + [price3] * (r + 1) + predispatch_prices[1:]
    aemo_prices = [aemo_price1] * (6 - r) + [aemo_price2] * 6 + [aemo_price3] * (r + 1) + aemo_predispatch_prices[1:]
    times, prices, aemo_prices, end = extend_forcast_horizon(current, times, prices, aemo_prices, custom_flag, battery, k)
    return times, prices, p5min_prices, predispatch_prices, predispatch_time, aemo_prices


if __name__ == '__main__':
    import datetime
    from helpers import Battery
    current = datetime.datetime(2021, 9, 12, 6, 10)
    custom_flag = False
    battery = Battery(30, 20, usage='Basic price-taker')

    times, prices, predispatch_time, aemo_prices, fcas_prices, aemo_fcas_prices, raise_fcas_records, lower_fcas_records, extended_times = process_prices_by_interval(
        current, custom_flag, battery, k=0, fcas_flag=False)
    for t1, t2 in zip(times, extended_times):
        print(t1, t2)

