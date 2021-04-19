# import bid
import csv
import datetime
import default
# import dispatch
import gurobipy
import interconnect
# import logging
# import matplotlib.pyplot as plt
# import pandas as pd
import pathlib
import preprocess
import requests
import zipfile
import io
import offer
import price_taker_2
import logging


class Link:
    """ MNSP link class.

    Attributes:
        link_id (str): Identifier for each of the two MNSP Interconnector Links
        from_region (str): Nominated source region for interconnector
        to_region (str): Nominated destination region for interconnector
        max_cap (float): Maximum capacity
        from_region_tlf (float): Transmission loss factor for link "From Region" end
        to_region_tlf (float): Transmission loss factor for link at "To Region" end

    """
    def __init__(self,
                 link_id,
                 from_region,
                 to_region,
                 max_cap,
                 from_region_tlf,
                 to_region_tlf):
        self.link_id = link_id
        self.from_region = from_region
        self.to_region = to_region
        self.max_cap = max_cap
        self.from_region_tlf = from_region_tlf
        self.to_region_tlf = to_region_tlf
        self.value = None

    def calculate_losses(self):
        return -3.92E-03 * self.value + 1.0393E-04 * (self.value ** 2) + 4


def init_links():
    """Initiate the dictionary for links.

    Returns:
        dict: A dictionary of links

    """
    return {'BLNKTAS': Link('BLNKTAS', 'VIC1', 'TAS1', 478, 0.9789, 1.0),
            'BLNKVIC': Link('BLNKVIC', 'TAS1', 'VIC1', 594, 1.0, 0.9728)}


def test_regional_energy_balance_equation(t):
    for i in range(1):
        regions, interconnectors, obj_record = interconnect.get_regions_and_interconnectors(t)

        for interconnector in interconnectors.values():
            if interconnector.interconnector_id == 'T-V-MNSP1':
                # losses = -3.92E-03 * interconnector.mw_flow_record + 1.0393E-04 * (interconnector.mw_flow_record ** 2) + 4
                # if interconnector.mw_flow_record >= 0:
                #     from_region_tlf = 1
                #     to_region_tlf = 0.9728
                #     from_flow = interconnector.mw_flow_record + interconnector.mw_losses_record
                #     to_flow = interconnector.mw_flow_record
                #     regions[interconnector.region_to].losses += (1 - from_region_tlf) * from_flow
                #     regions[interconnector.region_to].losses += (1 - to_region_tlf) * to_flow
                #     regions[interconnector.region_to].losses += (1 - 1) * 0
                #     regions[interconnector.region_to].losses += (1 - 0.9789) * (0 + 4)
                # else:
                #     from_region_tlf = 1
                #     to_region_tlf = 0.9789
                #     to_flow = interconnector.mw_flow_record + interconnector.mw_losses_record
                #     from_flow = interconnector.mw_flow_record
                #     regions[interconnector.region_to].losses += (1 - from_region_tlf) * from_flow
                #     regions[interconnector.region_to].losses += (1 - to_region_tlf) * to_flow
                #     regions[interconnector.region_to].losses += (1 - 1) * (0 + 4)
                #     regions[interconnector.region_to].losses += (1 - 0.9728) * 0
                # interconnector.mw_losses_record = (1 - from_region_tlf) * (interconnector.mw_flow_record + losses) + losses - 4 + (1 - to_region_tlf) * interconnector.mw_flow_record
                if interconnector.metered_mw_flow >= 0:
                    interconnector.from_region_loss_share = 1.0
                else:
                    interconnector.from_region_loss_share = 0.0
                links = init_links()
                if interconnector.mw_flow_record >= 0:
                    links['BLNKTAS'].value = 0
                    links['BLNKVIC'].value = interconnector.mw_flow_record
                    links['BLNKVIC'].temp = 4
                else:
                    links['BLNKTAS'].value = interconnector.mw_flow_record
                    links['BLNKTAS'].temp = 4
                    links['BLNKVIC'].value = 0
                for link in links.values():
                    regions[link.from_region].losses += (1 - link.from_region_tlf) * (link.value + link.calculate_losses())
                    regions[link.to_region].losses += (1 - link.to_region_tlf) * link.value

            regions[interconnector.from_region].losses += interconnector.mw_losses_record * interconnector.from_region_loss_share
            regions[interconnector.to_region].losses += interconnector.mw_losses_record * (1 - interconnector.from_region_loss_share)
            regions[interconnector.to_region].net_mw_flow_record += interconnector.mw_flow_record
            regions[interconnector.from_region].net_mw_flow_record -= interconnector.mw_flow_record

        result_dir = default.OUT_DIR.joinpath('equations.csv')
        with result_dir.open(mode='w') as result_file:
            writer = csv.writer(result_file, delimiter=',')

            writer.writerow(['Region', 'LHS', 'RHS', 'Difference'])

            # for region in [regions['TAS1'], regions['VIC1']]:
            for name, region in regions.items():
                # print(name)
                # print('G: {} Net: {} Record Net: {} Demand: {} Load: {}'.format(region.dispatchable_generation_record,
                #                                                                 region.net_mw_flow_record,
                #                                                                 region.net_interchange_record,
                #                                                                 region.total_demand,
                #                                                                 region.dispatchable_load_record))
                lhs = region.dispatchable_generation_record + region.net_mw_flow_record
                rhs = region.total_demand + region.dispatchable_load_record + region.losses
                writer.writerow([name, lhs, rhs, lhs - rhs])
                # error += abs(lhs - rhs)
            writer.writerow([interconnectors['T-V-MNSP1'].metered_mw_flow])
            writer.writerow([interconnectors['T-V-MNSP1'].mw_flow_record])
        t += preprocess.FIVE_MIN
    # print(error)


def test_model():
    m = gurobipy.Model('test')
    N = 3
    l1 = [m.addVar(ub=2) for i in range(N)]
    l2 = [m.addVar(ub=4) for i in range(N)]
    for i in range(N):
        m.addSOS(type=gurobipy.GRB.SOS_TYPE1, vars=[l1[i], l2[i]])
    m.addConstr(l1[0] == 1)
    m.addConstr(l2[1] == 0)
    obj = sum(l1) + sum(l2)
    m.setObjective(obj, gurobipy.GRB.MAXIMIZE)
    m.optimize()
    for i in range(N):
        print(f'{i} l1:{l1[i].x} l2:{l2[i].x}')


def test_download_zip():
    start = datetime.datetime(2019, 7, 10, 0, 0, 0)
    preprocess.download_5min_predispatch(start)
    # url = 'http://nemweb.com.au/Reports/Archive/P5_Reports/PUBLIC_P5MIN_20190709.zip'
    # result = requests.get(url)
    # file = OUT_DIR.joinpath('lala.csv')
    # if result.ok:
    #     with zipfile.ZipFile(io.BytesIO(result.content)) as zf:
    #         # zzf = zipfile.ZipFile(zf.read('PUBLIC_P5MIN_201907090400_20190709035532.zip'))
    #         zzf = zipfile.ZipFile(io.BytesIO(zf.read('PUBLIC_P5MIN_201907090400_20190709035532.zip')))
    #         csv_name = zzf.namelist()[0]
    #         with file.open('wb') as f:
    #             f.write(zzf.read(csv_name))


def test_extract_e_record():
    time = datetime.datetime(2019, 7, 9, 4, 0, 0)
    price_taker_2.extract_e_record(time)
    print(price_taker_2.E_record)


def test_mnsp_losses():
    links = interconnect.init_links()
    model = gurobipy.Model('test')

    link = links['BLNKVIC']
    link.mw_flow = model.addVar(lb=0, ub=link.max_cap, name=link.link_id)
    x_s = range(link.max_cap + 1)
    y_s = [-3.92E-03 * x_i + 1.0393E-04 * (x_i ** 2) + 4 for x_i in x_s]
    lambda_s = [model.addVar(lb=0.0) for i in x_s]
    model.addConstr(link.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    link.losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addConstr(link.losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    model.addConstr(sum(lambda_s) == 1)
    model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)
    link.total_losses = (1 - link.from_region_tlf) * (link.mw_flow + link.losses) + link.losses + (1 - link.to_region_tlf) * link.mw_flow

    # link = links['BLNKTAS']
    # link.mw_flow = model.addVar(lb=0, ub=link.max_cap, name=link.link_id)
    # x_s = range(-link.max_cap, 0)
    # y_s = [-3.92E-03 * x_i + 1.0393E-04 * (x_i ** 2) + 4 for x_i in x_s]
    # lambda_s = [model.addVar(lb=0.0) for i in x_s]
    # model.addConstr(-link.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    # link.losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    # model.addConstr(link.losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    # model.addConstr(sum(lambda_s) == 1)
    # model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)
    # link.total_losses = (1 - link.from_region_tlf) * (-link.mw_flow + link.losses) + link.losses + (1 - link.to_region_tlf) * (-link.mw_flow)

    # model.addSOS(gurobipy.GRB.SOS_TYPE1, [links['BLNKVIC'].mw_flow, links['BLNKTAS'].mw_flow])
    # mw_losses = links['BLNKVIC'].total_losses + links['BLNKVIC'].total_losses - 4
    # model.addConstr(-426.19289 == links['BLNKVIC'].mw_flow - links['BLNKTAS'].mw_flow)
    model.addConstr(100 == links['BLNKVIC'].mw_flow)
    model.setObjective(1)
    model.optimize()
    print(f'loss: {link.total_losses.getValue()}')


def test_basslink_losses(t):
    # t = datetime.datetime(2019, 7, 9, 10, 5, 0)
    for i in range(1):
        # t = START + preprocess.FIVE_MIN * i
        dispatch_dir = preprocess.download_dispatch_summary(t)
        with dispatch_dir.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == 'D' and row[2] == 'INTERCONNECTORRES' and row[6] == 'T-V-MNSP1' and row[8] == '0':
                    metered_mw_flow = float(row[9])
                    flow = float(row[10])
                    losses_record = float(row[11])
                    marginal_loss_record = float(row[17])
        losses = -3.92E-03 * flow + 1.0393E-04 * (flow * flow) + 4
        if flow >= 0:
            from_region_tlf = 1
            to_region_tlf = 0.9728
        else:
            from_region_tlf = 0.9789
            to_region_tlf = 1
        total_losses = (1 - from_region_tlf) * (flow + losses) + losses + (1 - to_region_tlf) * flow
        loss_factor = 0.99608 + 2.0786E-04 * flow
        yield (t, flow, total_losses, losses - 4, losses_record)

    # print('Flow: {}'.format(flow))
    # print('Losses: {}, Total losses: {}'.format(losses, total_losses))
    # print('Guess: {}, Record: {}'.format(losses - 4, losses_record))
    # print('Factor: {}, Record: {}'.format(loss_factor, marginal_loss_record))


def test_losses(t):
    result_dir = default.OUT_DIR.joinpath('basslink_losses.csv')
    with result_dir.open(mode='w') as f:
        writer = csv.writer(f, delimiter=',')
        writer.writerow(['Datetime',
                         'Flow',
                         'Total Losses',
                         'Guess',
                         'Record',
                         'Difference'])
        for tt, flow, total_losses, guess, losses_record in test_basslink_losses(t):
            writer.writerow([default.get_case_datetime(t),
                             flow,
                             total_losses,
                             guess,
                             losses_record,
                             losses_record - guess])


def negative_basslink():
    t = datetime.datetime(2019, 7, 22, 16, 30, 0)
    while True:
        t -= preprocess.THIRTY_MIN
        dispatch_dir = preprocess.download_dispatch_summary(t)
        with dispatch_dir.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == 'D' and row[2] == 'INTERCONNECTORRES' and row[6] == 'T-V-MNSP1' and row[8] == '0':
                    flow = float(row[10])
                    if flow < 0:
                        print(t)
                        return None


def test_ramp_rate(t):
    units = bid.get_units(t)
    for duid, unit in units.items():
        if unit.energy is not None:
            if unit.total_cleared_record > unit.initial_mw + 5 * unit.energy.roc_up:
                print(f'{duid} overflow')
            if unit.total_cleared_record < unit.initial_mw - 5 * unit.energy.roc_down:
                print(f'{duid} underflow')


def test_max_avail(t):
    units = bid.get_units(t)
    for duid, unit in units.items():
        if unit.energy is not None:
            if unit.total_cleared_record > unit.energy.max_avail:
                print(duid)
                print(f'{unit.total_cleared_record} {unit.energy.max_avail}')


def test_fcas_local_dispatch(t):
    regions, interconnectors, obj_record = interconnect.get_regions_and_interconnectors(t)
    units = bid.get_units(t)
    for unit in units.values():
        if unit.region is None:
            print(f'{unit.duid} without region')
        else:
            regions[unit.region].lower60sec_local_dispatch_temp += unit.lower60sec_record
            regions[unit.region].raise60sec_local_dispatch_temp += unit.raise60sec_record
    for name, region in regions.items():
        print(f'{name} record: {region.lower60sec_local_dispatch_record} our: {region.lower60sec_local_dispatch_temp}')


def test_fcas_only(t):
    units = bid.get_units(t)
    for name, unit in units.items():
        if unit.energy is None:
            print(name)


def test_p5min_predispatch_times():
    ttimes = []
    time = datetime.datetime(2019, 7, 19, 4, 0, 0)
    for i in range(12):
        print(f'i = {i}')
        print(time)
        price_taker_2.calculate_energy_prices(i, time, ttimes)
        ttimes.append(time + FIVE_MIN)
        time += FIVE_MIN

    # k = i % 6
    # print('i: {}, k: {}'.format(i, k))
    # print(time)
    # p5min_times, _ = price_taker.extract_5min_predispatch(time + FIVE_MIN)
    # print(p5min_times)
    # predispatch_times, _ = price_taker.extract_predispatch(k, time)
    # print(predispatch_times)
    

def test_energy_prices_calculator(i, k, ttimes):
    p5min_energy_prices, p5min_times = price_taker_2.extract_5min_predispatch(t + FIVE_MIN)
    predispatch_energy_prices, predispatch_times = price_taker_2.extract_predispatch(k, t)
    print('Dispatch: ')
    if k == 0:
        print(0)
    else:
        print(ttimes[-k:])
    print('5min: ')
    print(p5min_times[:6-k])
    print('---------------------------------------')
    print('5min: ')
    print(p5min_times[6-k:12-k])
    print('---------------------------------------')
    print('5min: ')
    if k == 0:
        print(0)
    else:
        print(p5min_times[12-k:])
    print('30min: ')
    print([predispatch_times[0] for _ in range(6-k)])


def test_trading_prices(t):
    records = []
    for i in range(288):
        price_taker_2.extract_dispatch(t + FIVE_MIN, records)
        if i % 6 == 0:
            rrp = price_taker_2.extract_trading(t + THIRTY_MIN)  # Get spot price for period
        elif i % 6 == 5:
            period_price = sum(records[-6:]) / 6
            if abs(period_price - rrp) > 0.01:
                print(t + FIVE_MIN)
                print(f'Trading: {rrp}')
                print(f'Calculating: {period_price}')
        t += FIVE_MIN


def test_telemetered_ramp_rate(t):
    for _ in range(288):
        units = {}
        bid.add_unit_bids(units, t)
        bid.add_dispatch_record(units, t)
        for unit in units.values():
            if unit.energy is not None:
                if unit.energy.roc_up == unit.ramp_up_rate:
                    print(f'{unit.duid} at {t} up rate warning.')
                if unit.energy.roc_down == unit.ramp_down_rate:
                    print(f'{unit.duid} at {t} down rate warning.')
        t += FIVE_MIN


def test_dvd_download():
    p = preprocess.download_interconnector_constraint()
    print(p)


def test_log():
    p = default.LOG_DIR / 'test.log'
    logging.basicConfig(filename=p, filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)
    logging.debug('test')


def read_record(units, current):
    interval_datetime = default.get_case_datetime(current + datetime.timedelta(minutes=5))
    record_dir = default.OUT_DIR / 'dispatch' / f'dispatch_{interval_datetime}.csv'
    with record_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                duid = row[1]
                if duid in units:
                    unit = units[duid]
                    unit.temp = float(row[2])


def test_ramp_rate_constr(start, interval):
    current = start + interval * datetime.timedelta(minutes=5)
    units, connection_points = offer.get_units(current, start, interval, 'dispatch', True)
    read_record(units, current)
    for duid, unit in units.items():
        down_rate = unit.energy.roc_down if unit.ramp_down_rate is None else unit.ramp_down_rate / 60
        if unit.temp < unit.initial_mw - 5 * down_rate and abs(unit.temp - unit.initial_mw + 5 * down_rate) > 1:
            print(f'{unit.dispatch_type} {unit.duid} below down ramp rate constraint')
            print(f'{unit.dispatch_type} {unit.duid} energy target {unit.temp} initial {unit.initial_mw} rate {down_rate}')


def compare_dispatch_and_predispatch_result():
    units = {}
    for process in ('dispatch', 'p5min', 'predispatch'):
        t = datetime.datetime(2020, 9, 1, 4, 30 if process == 'predispatch' else 5, 0)
        interval_datetime = default.get_case_datetime(
            t + preprocess.THIRTY_MIN) if process == 'predispatch' else default.get_case_datetime(
            t + preprocess.FIVE_MIN)
        if process == 'dispatch':
            p = default.OUT_DIR / f'{process}_{default.get_case_datetime(t)}'
        else:
            p = default.OUT_DIR / process / f'{process}_{default.get_case_datetime(t)}'
        result_dir = p / f'dispatchload_{interval_datetime}.csv'
        with result_dir.open(mode='r') as result_file:
            reader = csv.reader(result_file)
            for row in reader:
                if row[0] == 'D':
                    if row[1] not in units:
                        units[row[1]] = []
                    units[row[1]].append(float(row[3]))
    for duid, l in units.items():
        def different(l):
            return l[0] != l[1] or l[1] != l[2] or l[0] != l[2]
        if different(l):
            print(f'{duid} {l}')
    print(units)


if __name__ == '__main__':
    # test_mnsp_losses()
    start = datetime.datetime(2020, 6, 1, 14, 5, 0)
    # test_losses(t)
    # test_regional_energy_balance_equation(t)
    # negative_basslink()
    # test_max_avail(t)
    # test_fcas_local_dispatch(t)
    # test_fcas_only(t)
    # test_p5min_predispatch_times()
    # test_trading_prices(t)
    # test_telemetered_ramp_rate(t+FIVE_MIN)
    # test_dvd_download()
    # test_log()
    # test_ramp_rate_constr(start, 2)
    compare_dispatch_and_predispatch_result()


