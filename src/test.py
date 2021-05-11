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
    model.addLConstr(link.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    link.losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    model.addLConstr(link.losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    model.addLConstr(sum(lambda_s) == 1)
    model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)
    link.total_losses = (1 - link.from_region_tlf) * (link.mw_flow + link.losses) + link.losses + (1 - link.to_region_tlf) * link.mw_flow

    # link = links['BLNKTAS']
    # link.mw_flow = model.addVar(lb=0, ub=link.max_cap, name=link.link_id)
    # x_s = range(-link.max_cap, 0)
    # y_s = [-3.92E-03 * x_i + 1.0393E-04 * (x_i ** 2) + 4 for x_i in x_s]
    # lambda_s = [model.addVar(lb=0.0) for i in x_s]
    # model.addLConstr(-link.mw_flow == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))
    # link.losses = model.addVar(lb=-gurobipy.GRB.INFINITY)
    # model.addLConstr(link.losses == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))
    # model.addLConstr(sum(lambda_s) == 1)
    # model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)
    # link.total_losses = (1 - link.from_region_tlf) * (-link.mw_flow + link.losses) + link.losses + (1 - link.to_region_tlf) * (-link.mw_flow)

    # model.addSOS(gurobipy.GRB.SOS_TYPE1, [links['BLNKVIC'].mw_flow, links['BLNKTAS'].mw_flow])
    # mw_losses = links['BLNKVIC'].total_losses + links['BLNKVIC'].total_losses - 4
    # model.addLConstr(-426.19289 == links['BLNKVIC'].mw_flow - links['BLNKTAS'].mw_flow)
    model.addLConstr(100 == links['BLNKVIC'].mw_flow)
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


def test_objective(t):
    #TODO: Calculate objective to verify
    import constrain
    all_cost = 0
    total_energy, total_fcas, total_link = 0, 0, 0
    model = gurobipy.Model()
    regions, interconnectors, solution, links = interconnect.get_regions_and_interconnectors(t, t, 0, 'dispatch')
    # model.addLConstr(interconnectors['T-V-MNSP1'].mw_flow_record == links['BLNKTAS'].mw_flow - links['BLNKVIC'].mw_flow, name='BASSLINK_CONSTR')

    for link_id, link in links.items():
        # Avail at each price band
        link.offers = [model.addVar(ub=avail, name=f'Target{no}_{link_id}') for no, avail in enumerate(link.band_avail)]
        # Link flow
        link.mw_flow = model.addVar(name=f'Link_Flow_{link_id}')
        model.addLConstr(link.mw_flow == sum(link.offers))

        link.from_cost = sum([o * (p / link.from_region_tlf) for o, p in zip(link.offers, link.price_band)])
        link.to_cost = sum([o * (p / link.to_region_tlf) for o, p in zip(link.offers, link.price_band)])
        # Add cost to objective
        total_link -= link.from_cost  # As load for from_region
        total_link += link.to_cost  # As generator for to_region
        all_cost -= link.from_cost
        all_cost += link.to_cost

        model.addLConstr(link.mw_flow == link.mw_flow_record)

    units, connection_points = offer.get_units(t, t, 0, 'dispatch')
    for unit in units.values():
        if unit.energy is not None:
            for no, avail in enumerate(unit.energy.band_avail):
                bid_offer = model.addVar(name=f'Energy_Avail{no}_{unit.duid}')
                unit.offers.append(bid_offer)
                model.addLConstr(bid_offer <= avail, name=f'ENERGY_AVAIL{no}_{unit.duid}')
            # Total dispatch total_cleared
            unit.total_cleared = model.addVar(name=f'Total_Cleared_{unit.duid}')
            model.addLConstr(unit.total_cleared, gurobipy.GRB.EQUAL, sum(unit.offers))
            model.addLConstr(unit.total_cleared, gurobipy.GRB.EQUAL, unit.total_cleared_record)
            unit.cost = sum(
                [o * (p / unit.transmission_loss_factor) for o, p in zip(unit.offers, unit.energy.price_band)])
            if unit.dispatch_type == 'GENERATOR':
                total_energy += unit.cost
                all_cost += unit.cost
            elif unit.dispatch_type == 'LOAD':
                total_energy -= unit.cost
                all_cost += unit.cost
            else:
                print('Error!')

        if unit.fcas_bids != {}:
            for bid_type, fcas in unit.fcas_bids.items():
                fcas.value = model.addVar(name=f'{fcas.bid_type}_Target_{unit.duid}')
                for no, avail in enumerate(fcas.band_avail):
                    bid_offer = model.addVar(name=f'{bid_type}_Avail{no}_{unit.duid}')
                    fcas.offers.append(bid_offer)
                    model.addLConstr(bid_offer <= avail, name=f'{bid_type}_AVAIL{no}_{unit.duid}')
                model.addLConstr(fcas.value, sense=gurobipy.GRB.EQUAL, rhs=sum(fcas.offers),
                                name=f'{bid_type}_SUM_{unit.duid}')
                # Add cost to objective
                fcas.cost = sum([o * p for o, p in zip(fcas.offers, fcas.price_band)])

                total_fcas += fcas.cost
                all_cost += fcas.cost

                model.addLConstr(fcas.value == unit.target_record[bid_type])
    model.setObjective(all_cost, gurobipy.GRB.MINIMIZE)
    model.optimize()

    total_cost = total_energy + total_fcas + total_link


    print(f'value {total_cost.getValue()}')
    print(f'total energy {total_energy.getValue()}')
    print(f'total fcas {total_fcas.getValue()}')
    print(f'total link {total_link.getValue()}')
    # for link_id, link in links.items():
    #     print(f'{link_id} {link.price_band} {link.offers}')
    all_energy, all_fcas, all_link = 0, 0, 0
    for index in range(all_cost.size()):
        coeff = all_cost.getCoeff(index)
        var = all_cost.getVar(index)
        if var.x != 0:
            if 'Energy' in var.varName:
                all_energy += var.x * coeff
            elif 'BLNK' in var.varName:
                # print(var)
                # print(coeff)
                all_link += var.x * coeff
            else:
                all_fcas += var.x * coeff
    print(f'all cost {all_cost.getValue()}')
    print(f'all energy {all_energy}')
    print(f'all fcas {all_fcas}')
    print(f'all link {all_link}')


def test_obj():
    path_to_out = default.OUT_DIR / 'obj' / 'rate.csv'
    start = datetime.datetime(2020, 9, 1, 4, 5, 0)
    with path_to_out.open('w') as wf:
        writer = csv.writer(wf)
        writer.writerow(['Datetime', 'Our Obj', 'AEMO Obj', 'Rate (AEMO/Our)', '> 4?', 'Our Violation', 'AEMO Violation'])
        for i in range(288):
            current = start + i * default.FIVE_MIN
            path_to_file = default.OUT_DIR / 'dispatch' / f'dispatch_{default.get_case_datetime(current)}.csv'
            with path_to_file.open() as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == 'Value':
                        our = float(row[1])
                        aemo = float(row[2])
                        rate = aemo / our
                        writer.writerow([current, our, aemo, rate, abs(rate - 4) > 1, row[3], row[4]])
                        continue


def test_trading_prices():
    import read
    region = 'NSW1'
    start = datetime.datetime(2020, 9, 1, 4, 5, 0)
    for i in range(288):
        if i % 6 == 0:
            ours = []
            aemos = []
        t = start + i * default.FIVE_MIN
        our, aemo = read.read_dispatch_prices(t, 'dispatch', True, region)
        ours.append(our)
        aemos.append(aemo)
        if i % 6 == 5:
            trad = read.read_trading_prices(t, region)
            print(f'{t} {sum(ours) / 6} {sum(aemos) / 6} {trad}')


if __name__ == '__main__':
    start = datetime.datetime(2020, 9, 1, 9, 25, 0)
    # test_objective(start)
    # test_obj()
    test_trading_prices()