from price import process_prices_by_interval, process_prices_by_period
from dispatchold import dispatch, update_formulation, formulate_sequence
from offer import BiUnit
import default
import gurobipy as gp
import datetime
from multiprocessing.pool import ThreadPool as Pool
from itertools import repeat
import csv
from plot import plot_optimisation_with_bids
from helpers import Battery
from plot import plot_soc
from read import read_der


def optimise_horizon(start, battery, fcas_flag, first_horizon_flag=False):
    times, prices, predispatch_time, _, _, _, _, _, extended_times = process_prices_by_interval(start, True, battery, 0, fcas_flag)
    last_prob_id = None
    problems = []
    total_costs, total_penalty = 0, 0
    constr_flag = False
    with gp.Env() as env, gp.Model(env=env, name=f'BiUnit {default.get_case_datetime(start)}') as model:
        model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
        # Initiate cost and penalty of objective function
        for j, (t, et) in enumerate(zip(times, extended_times)):
            if j < 6:
                current = t
                process = 'dispatch' if j == 0 else 'p5min'
                pre_start = start
                intervals = None
                pre_t = None
                constr_flag = True
            elif et is None:
                current = t - default.TWENTYFIVE_MIN
                process = 'predispatch'
                pre_start = predispatch_time
                # j = j - 10
                # intervals = (t - start - default.ONE_HOUR + default.FIVE_MIN) / default.ONE_MIN if j == 2 else None
                j = j - 5
                intervals = (t - start - default.THIRTY_MIN + default.FIVE_MIN) / default.ONE_MIN if j == 1 else None
                pre_t = t
            else:
                current = et
                process = 'dispatch'
                pre_start = et
                intervals = None
                pre_t = None
            prob, model, cvp = dispatch(current, pre_start, pre_t, j, process, model, path_to_out=battery.bat_dir,
                                        dispatchload_flag=(j == 0 and not first_horizon_flag), dispatchload_record=True,
                                        fcas_flag=fcas_flag, last_prob_id=last_prob_id,
                                        dual_flag=True, biunit=battery, constr_flag=constr_flag,
                                        intervals=intervals, link_flag=False)
            total_costs, total_penalty, last_prob_id = update_formulation(prob, problems, model, total_costs, total_penalty, cvp)

        model.setObjective(total_costs + total_penalty, gp.GRB.MINIMIZE)
        model.optimize()
        path_to_model = battery.bat_dir / f'DER_{default.get_case_datetime(start)}.lp'
        model.write(str(path_to_model))

        # prices = []
        # for prob_num, prob in enumerate(problems):
        #     prices.append(prob.regions[battery.region_id].rrp_constr.pi)
        path_to_csv = battery.bat_dir / f'DER_{battery.size}MWh_{default.get_case_datetime(start)}.csv'
        with path_to_csv.open('w') as f:
            writer = csv.writer(f)
            for prob, p in zip(problems, prices):
                writer.writerow([prob.current, prob.process, model.getVarByName(f'E_{battery.duid}_{prob.problem_id}').x, model.getVarByName(f'Total_Cleared_{battery.duid}_{prob.problem_id}').x, p, prob.regions[battery.region_id].rrp_constr.pi])
        plot_optimisation_with_bids(battery, None, None, der_flag=True, e=battery.size, t=start, bat_dir=battery.bat_dir)


def multiformulate(times, start, predispatch_start):
    problems = []
    currents, processes, pre_starts, pre_ts, constr_flags, js = [], [], [], [], [], []
    with gp.Env() as env, gp.Model(env=env, name=f'Test') as model:
        model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
        # for j, t in enumerate(times):
        #     if j < 6:
        #         currents.append(t)
        #         processes.append('dispatch' if j == 0 else 'p5min')
        #         pre_starts.append(start)
        #         pre_ts.append(None)
        #         constr_flags.append(True)
        #         js.append(j)
        #     else:
        #         currents.append(t - default.TWENTYFIVE_MIN)
        #         processes.append('predispatch')
        #         pre_starts.append(predispatch_start)
        #         pre_ts.append(t)
        #         js.append(j - 5)
        currents = times[:2]
        pre_starts = [start, start]
        pre_ts = [None, None]
        js = [0, 1]
        processes = ['dispatch', 'dispatch']
        results = pool.starmap(dispatch, zip(currents, pre_starts, pre_ts, js, processes, repeat(model)))
        print(results)


def rolling_horizons(e, initial_time, iterations, usage, method):
    # batt_unit = BiUnit(e, usage, method)
    battery = Battery(e, int(e * 2 / 3), usage=usage)
    for i in range(iterations):
        start = initial_time + i * default.THIRTY_MIN
        # times, _, _, _, _, _, _, _, extended_times = process_prices_by_period(start, True, battery, 0, False)
        times = [start + j * default.THIRTY_MIN for j in range(48)]
        results = [None for _ in times]
        extended_times = [None for _ in times]
        print(initial_time)
        # formulate_sequence(start, e, usage, results, times, extended_times, first_horizon_flag=(i==0), link_flag=False, dual_flag=False)
        # _, socs, prices, _ = read_der(e, start, battery.bat_dir)
        # plot_soc(times, [prices, original_prices], socs, path_to_fig=None, price_flag=True, soc_flag=True)
        # optimise_horizon(start, batt_unit, 'FCAS' in usage, (i == 0))
        # plot_optimisation_with_bids(batt_unit, None, None, der_flag=True, e=batt_unit.size, t=start, bat_dir=batt_unit.bat_dir)
        # multiformulate(times, start, predispatch_time)
        # formulate_sequence(start, battery.size, usage, results, times, extended_times, E_initial=battery.size * 0.5, first_horizon_flag=True, link_flag=False, dual_flag=False, dispatchload_path=None)


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
    formulate_sequence(start, e, usage, results, times, extended_times, E_initial=e * 0.5, first_horizon_flag=True, link_flag=True, dual_flag=False, dispatchload_path=None)


if __name__ == '__main__':
    print(datetime.datetime.now())
    initial_time = datetime.datetime(2020, 9, 1, 4, 30)
    iterations = 1
    # usage = 'BiUnit'
    usage = 'DER None Integration Test Hour FCAS every 1st'
    method = 0
    energies = 0
    # initial_times = [initial_time + i * default.THIRTY_MIN * 2 for i in range(18, 24)]
    # print(initial_times)
    # for i in range(48):
    #     print(i, initial_times[i])
    initial_times = [initial_time]
    with Pool(len(initial_times)) as pool:
        # pool.starmap(rolling_horizons, zip(repeat(energies), repeat(initial_times), repeat(iterations), repeat(usage), repeat(method)))
        pool.starmap(rolling_horizon, zip(repeat(energies), initial_times, repeat(usage)))
    print(datetime.datetime.now())

