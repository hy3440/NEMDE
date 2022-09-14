from price import process_prices_by_period
import default
import gurobipy as gp
import datetime
from multiprocessing.pool import ThreadPool as Pool
from itertools import repeat
import csv
from helpers import Battery
from plot import plot_soc
from dispatchold import add_regional_energy_demand_supply_balance_constr, dispatch
import helpers
import result


def update_formulation(prob, problems, model, total_costs, total_penalty, cvp):
    for region_id, region in prob.regions.items():
        prob.penalty = add_regional_energy_demand_supply_balance_constr(model, region, region_id, prob.problem_id,
                                                                        False, prob.penalty, cvp)
    problems.append(prob)
    last_prob_id = prob.problem_id
    total_costs += prob.cost
    total_penalty += prob.penalty
    model.update()
    return total_costs, total_penalty, last_prob_id


def battery_bid(battery, avails, fcas_flag=False, bands=None):
    if avails is None:
        battery.add_energy_bid([0], [battery.generator.max_capacity], [0], [battery.load.max_capacity])
        if fcas_flag:
            for load_flag in [True, False]:
                for bid_type in default.CONTINGENCY_FCAS_TYPES:
                    battery.add_fcas_bid(bid_type, [0], [battery.generator.max_capacity], load_flag)
    elif bands is None:
        battery.add_energy_bid([0], [avails[0]], [500], [avails[1]])


def formulate_sequence(start, e, usage, results=None, times=None, extended_times=None, first_horizon_flag=False, predefined_battery=None, link_flag=False, dual_flag=True, E_initial=None, dispatchload_path=None):
    """Time-stepped NEMDE which looks ahead for 24hrs (6 intervals of P5MIN and 47 periods of Predispatch).

    Args:
        start (datetime.datetime): start datetime
        e (float): battery size
        usage (str): battery usage
        results (list): battery optimisation results
        times (list): datetimes

    Returns:
        (pathlib.Path, flaot, dict): path to DISPATCHLOAD file, RRP, FCAS RRP
    """
    problems = []
    last_prob_id = None
    fcas_flag = 'FCAS' in usage
    with gp.Env() as env, gp.Model(env=env, name=f'Integration {default.get_case_datetime(start)}') as model:
        model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
        # Initiate cost and penalty of objective function
        total_costs, total_penalty = 0, 0
        # predispatch_start = default.get_predispatch_time(start)
        for j, (t, r, et) in enumerate(zip(times, results, extended_times)):
            constr_flag = True
            if predefined_battery is not None and j == 0:
                battery = predefined_battery
            else:
                battery = helpers.Battery(e, int(e / 3 * 2), usage=usage)
                battery_bid(battery, None if 'None' in usage else r, fcas_flag)
            # # if j < 12:
            # if j < 6:
            #     if j == 0:
            #         battery.initial_E = E_initial
            #     current = t
            #     process = 'dispatch' if j == 0 else 'p5min'
            #     pre_start = start
            #     intervals = None
            #     pre_t = None
            #     constr_flag = True
            # elif et is None:
            #     current = t - default.TWENTYFIVE_MIN
            #     process = 'predispatch'
            #     pre_start = predispatch_start
            #     # j = j - 10
            #     # intervals = (t - start - default.ONE_HOUR + default.FIVE_MIN) / default.ONE_MIN if j == 2 else None
            #     j = j - 5
            #     intervals = (t - start - default.THIRTY_MIN + default.FIVE_MIN) / default.ONE_MIN if j == 1 else None
            #     pre_t = t
            # else:
            #     current = et
            #     process = 'dispatch'
            #     pre_start = et
            #     intervals = 30
            #     pre_t = None
            if j % 2 != 0:
                continue
            if j == 0:
                battery.initial_E = E_initial
                current = t
                process = 'dispatch'
                pre_start = start
                intervals = 30
                pre_t = None
                constr_flag = True
                if not first_horizon_flag and dispatchload_path is None:
                    time_gap = (default.TWENTYFIVE_MIN + default.THIRTY_MIN) if 'Hour' in usage else default.TWENTYFIVE_MIN
                    dispatchload_path = battery.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(start - time_gap)}.csv'
            elif et is None:
                # current = t - default.TWENTYFIVE_MIN
                current = t
                process = 'extension' if 'Perfect' in usage else 'predispatch'
                pre_start = start
                # j = j - 10
                # intervals = (t - start - default.ONE_HOUR + default.FIVE_MIN) / default.ONE_MIN if j == 2 else None
                intervals = 30
                pre_t = t
            else:
                current = t if 'Perfect' in usage else et
                process = 'extension'
                pre_start = start if 'Perfect' in usage else et
                intervals = 30
                pre_t = None
            intervals = 60
            if 'Simplified' in usage:
                prob, model, cvp = dispatch(current, pre_start, pre_t, j, process, model, path_to_out=battery.bat_dir,
                                            dispatchload_flag=(j == 0 and not first_horizon_flag),
                                            dispatchload_record=True, fcas_flag=fcas_flag, der_flag=True,
                                            last_prob_id=last_prob_id, dual_flag=True, bilevel_flag=False,
                                            losses_flag=False, constr_flag=False, link_flag=False,
                                            batteries={battery.bat_id: battery}, dispatchload_path=dispatchload_path,
                                            intervals=intervals, utility_flag=('Utility' in usage))
            else:
                prob, model, cvp = dispatch(current, pre_start, pre_t, j, process, model, path_to_out=battery.bat_dir,
                                            dispatchload_flag=(j == 0 and not first_horizon_flag), dispatchload_record=True,
                                            fcas_flag=fcas_flag, der_flag=True, last_prob_id=last_prob_id, dual_flag=dual_flag, bilevel_flag=False,
                                            batteries={battery.bat_id: battery}, constr_flag=constr_flag, dispatchload_path=dispatchload_path,
                                            intervals=intervals, link_flag=link_flag, utility_flag=('Utility' in usage))
            first_horizon_flag = False
            total_costs, total_penalty, last_prob_id = update_formulation(prob, problems, model, total_costs, total_penalty, cvp)
            # print(f'Finished {process} {current}: {datetime.datetime.now()}')
        for bat_id, battery in problems[-1].batteries.items():
            model.addLConstr(battery.E >= battery.size * 0.5, f'FINAL_STATE_{bat_id}_{prob.problem_id}')
        model.setObjective(total_costs + total_penalty, gp.GRB.MINIMIZE)
        # print(f'Finished formulation: {datetime.datetime.now()}')

        model.optimize()
        if 'Test' in usage:
            path_to_model = battery.bat_dir / f'DER_{e}MWh_{default.get_case_datetime(start)}.lp'
            model.write(str(path_to_model))
        # print(f'Finished {start} optimisation: {datetime.datetime.now()}')
        base = model.getObjective().getValue()
        fixed = model.fixed()
        fixed.optimize()
        prices, subprices, fixedprices = [], [], []
        region_id = 'NSW1'
        fcas_prices = {fcas_type: [] for fcas_type in default.FCAS_TYPES} if fcas_flag else None
        for prob in problems:
            prob.base = prob.cost.getValue() + prob.penalty.getValue()
            for b in prob.batteries.values():
                cost = 0 if type(b.degradation_cost) == int else b.degradation_cost.getValue()
            c = fixed.getConstrByName(f'REGION_BALANCE_{region_id}_{prob.problem_id}')
            fixedprices.append(c.pi)
            # if '1st' not in usage:
            #     break
        dispatchload_path = result.write_dispatchload(problems[0].units, problems[0].links, times[0], times[0], 'dispatch',
                                                      path_to_out=battery.bat_dir)
        for prob_num, prob in enumerate(problems):
            region = prob.regions[region_id]
            if fcas_flag:
                for fcas_type, fcas_price in fcas_prices.items():
                    p = - fixed.getConstrByName(f'LOCAL_DISPATCH_SUM_{fcas_type}_{region_id}_{prob.problem_id}').pi
                    fcas_price.append(p)
                    region.fcas_rrp[fcas_type] = p
            if dual_flag:
                prices.append(region.rrp_constr.pi)
                if prob_num == 0:
                    for b in prob.batteries.values():
                        result.write_dispatchis(None, start, prob.regions, {region_id: prices[0]}, k=0, path_to_out=b.bat_dir)
                        # print(f'Finished first interval: {datetime.datetime.now()}')
                        if '1st' not in usage:
                            return prices[0], dispatchload_path, b.E.x, 0
            else:
                # Increase regional demand by 1
                model.remove(region.rrp_constr)
                region.rrp_constr = model.addLConstr(
                    region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen == region.total_demand + 1 + region.dispatchable_load + region.losses,
                    name=f'REGION_BALANCE_{region_id}_{prob.problem_id}')

                model.setObjective(total_costs + total_penalty, gp.GRB.MINIMIZE)
                # model.addLConstr(total_penalty == 0, name='HARD_CONSTR')
                model.optimize()
                prices.append(model.getObjective().getValue() - base)
                subprices.append(prob.cost.getValue() + prob.penalty.getValue() - prob.base)

                if prob_num == 0:
                    for b in prob.batteries.values():
                        result.write_dispatchis(None, start, prob.regions, {region_id: subprices[0]}, k=0, path_to_out=b.bat_dir)
                        # print(f'Finished first interval: {datetime.datetime.now()}')
                        # return b.generator.total_cleared.x, b.load.total_cleared.x, prices[0], dispatchload_path, b.E.x
                        if '1st' not in usage:
                            return prices[0], dispatchload_path, b.E.x, subprices[0], fixedprices[0], region.fcas_rrp, cost, fixedprices

                # Reset constr state
                model.remove(region.rrp_constr)
                region.rrp_constr = model.addLConstr(
                    region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen == region.total_demand + region.dispatchable_load + region.losses,
                    name=f'REGION_BALANCE_{region_id}_{prob.problem_id}')
        socs = []
        path_to_csv = battery.bat_dir / f'DER_{battery.size}MWh_{default.get_case_datetime(start)}.csv'
        with path_to_csv.open('w') as f:
            writer = csv.writer(f)
            writer.writerow(['Datetime', 'Process Type', 'Charge level (MWh)', 'Generation', 'Load', 'Price', 'Sub price', 'Fix price'] + (list(fcas_prices.keys()) if fcas_flag else []))
            for num, (prob, p, sp, fp) in enumerate(zip(problems, prices, subprices, fixedprices)):
                for b in prob.batteries.values():
                    writer.writerow([prob.current, prob.process, b.E.x, b.generator.total_cleared.x, b.load.total_cleared.x, p, sp, fp] + ([value[num] for value in fcas_prices.values()] if fcas_flag else []))
                    socs.append(0 if e == 0 else b.E.x * 100 / e)
        # plot_optimisation_with_bids(battery, None, None, der_flag=True, e=battery.size, t=start, bat_dir=b.bat_dir)
        path_to_fig = battery.bat_dir / f'DER_{e}MWh_{default.get_case_datetime(t)}.jpg'
        plot_soc([times[i] for i in range(48) if i % 2 == 0], fixedprices, socs, path_to_fig, price_flag=True, soc_flag=True, labels=None)
        print(f'Finished all intervals: {datetime.datetime.now()}')


def formulate_bilevel(start, e, usage, results=None, times=None, extended_times=None, first_horizon_flag=False, predefined_battery=None, link_flag=False, dual_flag=True, E_initial=None, dispatchload_path=None):
    """Bilevel time-stepped NEMDE which looks ahead for 24hrs (24 periods of Predispatch whose length is 1hr).

    Args:
        start (datetime.datetime): start datetime
        e (float): battery size
        usage (str): battery usage
        results (list): battery optimisation results
        times (list): datetimes

    Returns:
        (pathlib.Path, flaot, dict): path to DISPATCHLOAD file, RRP, FCAS RRP
    """
    L = 1e10
    problems = []
    last_prob_id = None
    fcas_flag = 'FCAS' in usage
    with gp.Env() as env, gp.Model(env=env, name=f'Bilevel {default.get_case_datetime(start)}') as model:
        model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
        # Initiate cost and penalty of objective function
        total_costs, total_penalty = 0, 0
        for j, (t, r, et) in enumerate(zip(times, results, extended_times)):
            if predefined_battery is not None and j == 0:
                battery = predefined_battery
            else:
                battery = helpers.Battery(e, int(e / 3 * 2), usage=usage)
                battery_bid(battery, None if 'None' in usage else r, fcas_flag)
            if j % 2 != 0:
                continue
            if j == 0:
                battery.initial_E = E_initial
                current = t
                process = 'dispatch'
                pre_start = start
                pre_t = None
                if not first_horizon_flag and dispatchload_path is None:
                    time_gap = (default.TWENTYFIVE_MIN + default.THIRTY_MIN) if 'Hour' in usage else default.TWENTYFIVE_MIN
                    dispatchload_path = battery.bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(start - time_gap)}.csv'
            elif et is None:
                # current = t - default.TWENTYFIVE_MIN
                current = t
                process = 'extension' if 'Perfect' in usage else 'predispatch'
                pre_start = start
                # j = j - 10
                # intervals = (t - start - default.ONE_HOUR + default.FIVE_MIN) / default.ONE_MIN if j == 2 else None
                pre_t = t
            else:
                current = t if 'Perfect' in usage else et
                process = 'extension'
                pre_start = start if 'Perfect' in usage else et
                pre_t = None
            intervals = 60
            prob, model, cvp = dispatch(current, pre_start, pre_t, j, process, model, path_to_out=battery.bat_dir,
                                        dispatchload_flag=(j == 0 and not first_horizon_flag), dispatchload_record=True,
                                        fcas_flag=fcas_flag, der_flag=False, last_prob_id=last_prob_id, dual_flag=True,
                                        losses_flag=False, constr_flag=False, link_flag=False, bilevel_flag=True,
                                        batteries={battery.bat_id: battery}, dispatchload_path=dispatchload_path,
                                        intervals=intervals, utility_flag=('Utility' in usage))
            first_horizon_flag = False
            total_costs, total_penalty, last_prob_id = update_formulation(prob, problems, model, total_costs, total_penalty, cvp)
            # if j == 4:
            #     break
            # print(f'Finished {process} {current}: {datetime.datetime.now()}')

        model.setObjective(total_costs + total_penalty, gp.GRB.MINIMIZE)
        from bilevel import KKT
        _, _, dual_obj = KKT(model, False)
        model.update()
        # print(f'Finished KKT: {datetime.datetime.now()}')
        for constr in model.getConstrs():
            if 'Total_Cleared_G_' in constr.constrName or 'Total_Cleared_L_' in constr.constrName:
                # print(constr.constrName)
                # row = model.getRow(constr)
                # for k in range(row.size()):
                #     print("Variable %s, coefficient %f" % (row.getVar(k).VarName, row.getCoeff(k)))
                model.remove(constr)
        model.update()

        obj, last_prob_id = 0, None
        for prob in problems:
            dual_price = model.getVarByName(f'Dual_REGION_BALANCE_{battery.region_id}_{prob.problem_id}')
            for bat_id, battery in prob.batteries.items():
                obj += dual_price * (battery.generator.total_cleared - battery.load.total_cleared)

                battery.bidding_price = model.addVar(name=f'Bidding_Price_{battery.bat_id}_{prob.problem_id}')
                for unit in [battery.generator, battery.load]:
                    unit.ub = model.addVar(ub=unit.max_capacity, name=f'Ub_{unit.duid}_{prob.problem_id}')
                    model.addLConstr(unit.total_cleared <= unit.ub, name=f'UPPER_BOUND_{unit.duid}_{prob.problem_id}')
                    dual_ub = model.addVar(name=f'Dual_Ub_{unit.duid}_{prob.problem_id}')
                    binary = model.addVar(vtype=gp.GRB.BINARY, name=f'Binary_Ub_{unit.duid}_{prob.problem_id}')
                    model.addConstr(dual_ub <= (1 - binary) * L, name=f'COMPLEMENTARY_Ub_{unit.duid}_{prob.problem_id}')
                    model.addConstr(unit.ub - unit.total_cleared <= binary * L, name=f'COMPLEMENTARY2_Ub_{unit.duid}_{prob.problem_id}')

                    model.addLConstr(unit.total_cleared >= 0, name=f'LOWER_BOUND_{unit.duid}_{prob.problem_id}')
                    dual_lb = model.addVar(name=f'Dual_Lb_{unit.duid}_{prob.problem_id}')
                    binary = model.addVar(vtype=gp.GRB.BINARY, name=f'Binary_Lb_{unit.duid}_{prob.problem_id}')
                    model.addConstr(dual_lb <= (1 - binary) * L, name=f'COMPLEMENTARY_Lb_{unit.duid}_{prob.problem_id}')
                    model.addConstr(unit.total_cleared <= binary * L, name=f'COMPLEMENTARY2_Lb_{unit.duid}_{prob.problem_id}')

                    if unit.dispatch_type == 'LOAD':
                        model.addLConstr(- battery.bidding_price + dual_price - dual_lb + dual_ub == 0, name=f'GRADIENT_{unit.duid}_{prob.problem_id}')
                    else:
                        model.addLConstr(battery.bidding_price - dual_price - dual_lb + dual_ub == 0, name=f'GRADIENT_{unit.duid}_{prob.problem_id}')

                if last_prob_id is not None:
                    battery.initial_E = model.getVarByName(f'E_{bat_id}_{last_prob_id}')
                battery.E = model.addVar(name=f'E_{bat_id}_{prob.problem_id}')
                battery.min_avail_constr = model.addLConstr(battery.E >= battery.Emin, name=f'Emin_AVAIL_{bat_id}_{prob.problem_id}')
                battery.max_avail_constr = model.addLConstr(battery.E <= battery.Emax, name=f'Emax_AVAIL_{bat_id}_{prob.problem_id}')
                battery.transition_constr = model.addLConstr(battery.E, gp.GRB.EQUAL, battery.initial_E + intervals * (battery.load.total_cleared * battery.eff - battery.generator.total_cleared / battery.eff) / 60, f'TRANSITION_{bat_id}_{prob.problem_id}')
                # battery.E_record = model.addVar(name=f'E_record_{bat_id}_{prob.problem_id}')
                # model.addLConstr(battery.E_record == battery.initial_E_record + intervals * (battery.load.total_cleared_record * battery.eff - battery.generator.total_cleared_record / battery.eff) / 60, f'E_RECORD_{bat_id}_{prob.problem_id}')
                # Charge or discharge
                battery.sos_constr = model.addSOS(gp.GRB.SOS_TYPE1, [battery.generator.ub, battery.load.ub])
            last_prob_id = prob.problem_id
            model.update()
        for bat_id, battery in problems[-1].batteries.items():
            model.addLConstr(battery.E >= battery.size * 0.5, f'FINAL_STATE_{bat_id}_{prob.problem_id}')
        # model.setObjective(obj, gp.GRB.MAXIMIZE)
        # model.params.NonConvex = 2
        model.setObjective(dual_obj - (total_costs + total_penalty), gp.GRB.MAXIMIZE)
        # print(f'Finished bilevel formulation: {datetime.datetime.now()}')
        model.optimize()
        # print(f'Finished {start} bilevel optimisation: {datetime.datetime.now()}')
        if 'Test' in usage:
            path_to_model = battery.bat_dir / f'DER_{e}MWh_{default.get_case_datetime(start)}.lp'
            model.write(str(path_to_model))
        # print(f'model obj is {model.getObjective().getValue()} and formulated obj is {obj.getValue()}')
        path_to_csv = battery.bat_dir / f'DER_{battery.size}MWh_{default.get_case_datetime(start)}.csv'
        with path_to_csv.open('w') as f:
            writer = csv.writer(f)
            writer.writerow(['Datetime', 'Regional Price', 'SOC (%)', 'E (MWh)', 'Bidding Price', 'Generator', 'Generator UB', 'Load', 'Load UB'])
            for prob in problems:
                for battery in prob.batteries.values():
                    dual_price = model.getVarByName(f'Dual_REGION_BALANCE_{battery.region_id}_{prob.problem_id}')
                    writer.writerow([prob.current, dual_price.x, (0 if battery.size == 0 else battery.E.x * 100 / battery.size), battery.E.x, battery.bidding_price.x, battery.generator.total_cleared.x, battery.generator.ub.x, battery.load.total_cleared.x, battery.load.ub.x])

        if '1st' not in usage:
            prob = problems[0]
            for b in prob.batteries.values():
                price = model.getVarByName(f'Dual_REGION_BALANCE_{battery.region_id}_{prob.problem_id}').x
                result.write_dispatchis(None, start, prob.regions, {battery.region_id: price}, k=0, path_to_out=b.bat_dir)
                # print(f'Finished first interval: {datetime.datetime.now()}')
                dispatchload_path = result.write_dispatchload(prob.units, prob.links, start, start,
                                                              'dispatch', path_to_out=battery.bat_dir)
                return price, dispatchload_path, b.E.x, price, price, None, obj.getValue(), None


def rolling_horizon(e, start, usage):
    battery = Battery(e, int(e * 2 / 3), usage=usage)
    times, _, _, _, _, _, _, _, extended_times = process_prices_by_period(start, False, battery, 0, False)
    # times = [start + j * default.THIRTY_MIN for j in range(48)]
    results = [None for _ in times]
    # extended_times = [None for _ in times]
    # formulate_sequence(start, e, usage, results, times, extended_times, first_horizon_flag=(i==0), link_flag=False, dual_flag=False)
    # _, socs, prices, _ = read_der(e, start, battery.bat_dir)
    # plot_soc(times, [prices, original_prices], socs, path_to_fig=None, price_flag=True, soc_flag=True)
    # optimise_horizon(start, batt_unit, 'FCAS' in usage, (i == 0))
    # plot_optimisation_with_bids(batt_unit, None, None, der_flag=True, e=batt_unit.size, t=start, bat_dir=batt_unit.bat_dir)
    # multiformulate(times, start, predispatch_time)
    formulate_func = formulate_bilevel if 'Bilevel' in usage else formulate_sequence
    # formulate_func(start, e, usage, results, times, extended_times, E_initial=e * 0.5, first_horizon_flag=True, link_flag=True, dual_flag=False, dispatchload_path=None)
    formulate_func(start, e, usage, results, times, extended_times, E_initial=e * 0.5, first_horizon_flag=True)


if __name__ == '__main__':
    print(datetime.datetime.now())
    initial_time = datetime.datetime(2021, 7, 18, 4, 30)
    iterations = 1
    # usage = 'BiUnit'
    usage = 'DER None Bilevel Test Hour every 1st'
    # method = 0
    energies = 30
    # initial_times = [initial_time + i * default.THIRTY_MIN * 2 for i in range(18, 24)]
    # print(initial_times)
    # for i in range(48):
    #     print(i, initial_times[i])
    initial_times = [initial_time]
    with Pool(len(initial_times)) as pool:
        # pool.starmap(rolling_horizons, zip(repeat(energies), repeat(initial_times), repeat(iterations), repeat(usage), repeat(method)))
        pool.starmap(rolling_horizon, zip(repeat(energies), initial_times, repeat(usage)))
    print(datetime.datetime.now())

