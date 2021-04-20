import offer
import csv
import datetime
import default
import gurobipy
import interconnect
import preprocess


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


def compare_initial_mw():
    # Compare initial MW of dispatch, p5min and predispatch
    t1 = datetime.datetime(2020, 9, 1, 4, 5, 0)
    t2 = datetime.datetime(2020, 9, 1, 4, 30, 0)
    d, _ = offer.get_units(t1, t1, 0, 'dispatch')
    p5, _ = offer.get_units(t1, t1, 0, 'p5min')
    pre, _ = offer.get_units(t1, t2, 0, 'predispatch')
    print('DUID DISPATCH P5MIN PREDISPATCH')
    for duid in d.keys():
        a = d[duid].initial_mw
        b = p5[duid].initial_mw
        c = pre[duid].initial_mw
        if not a == b == c:
            print(duid, a, b, c)


def test_predispatchload():
    # Compare initial MW and total cleared record
    start = datetime.datetime(2020, 9, 1, 13, 0, 0)
    process = 'predispatch'
    print('Datetime Initial MW  Total Cleared')
    for i in range(30, 35):
        intervals = 30 if process == 'predispatch' else 5
        current = start + i * datetime.timedelta(minutes=intervals)
        if process == 'predispatch':
            pt = current
            current -= datetime.timedelta(minutes=25)
        units, _ = offer.get_units(t=current, start=start, i=i, process=process, dispatchload_flag=False, daily_energy_flag=False)
        if i == 30:
            import random
            duid = random.choice(list(units.keys()))
            while units[duid].total_cleared_record == 0:
                duid = random.choice(list(units.keys()))
            print(duid)
        unit = units[duid]
        print(f'{current} {unit.initial_mw} {unit.total_cleared_record}')


if __name__ == '__main__':
    start = datetime.datetime(2020, 9, 1, 4, 30, 0)
    t = datetime.datetime(2020, 9, 1, 13, 0, 0)
    i = 0
    d, n = default.extract_from_interval_no('2020090108', True)
    print(d)
    print(n)
