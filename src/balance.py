import csv
import datetime
from debug import debug_infeasible_model
import default
from dispatchold import Problem
import gurobipy as gp
import helpers
import offer
import parse
import preprocess
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
import matplotlib.pyplot as plt
plt.style.use(['science', 'ieee', 'no-latex'])
plt.rcParams['axes.unicode_minus']=False
import matplotlib.dates as mdates

region_id = 'VIC1'
T, W, intervals = 24, 4, 60
unit_list_temp = [
    'GANGARR1',  # Solar; Max Cap: 120MW; Max ROC: 24 MW/min
    'SMCSF1',  # Solar; 112; 25
    'FINLYSF1',  # Solar
    'COOPGWF1',  # Wind; 169; 100
    'MEWF1',  # Wind; 126; 159
    'OAKEY1',  # Fossil; 173; 30
    'DDPS1',  # Fossil; 280; 10
    'GSTONE1',  # Fossil; 285; 57
    'BARKIPS1',  # Fossil; 210; 42
    'W/HOE#1',  # Hydro; 285; 300
    'BARRON-1'  # Hydro; 33; 4
    # 'HPRG1',  # Battery; 150; 30
    # 'HPRL1'  # Battery; 120; 24
]
unit_list = set()
# unit_list = {'YWPS2', 'YWPS3', 'LOYYB1', 'LYA1', 'YWPS1', 'LYA3', 'LYA4', 'LYA2', 'LOYYB2', 'YWPS4', 'NPS'}
demand_scale = 1
ramp_scale = 1


def scale_demand(d):
    return d * demand_scale


def scale_ramp_rate(up, down):
    return up * ramp_scale, down * ramp_scale


def read_dispatch_demand(t):
    dispatch_dir = preprocess.download_dispatch_summary(t)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGIONSUM' and row[6] == region_id:
                return float(row[9])


def read_predispatch_demand(t, j):
    dispatch_dir = preprocess.download_predispatch(t)
    with dispatch_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and row[2] == 'REGION_SOLUTION' and int(row[7]) == j + 1 and row[6] == region_id:
                return float(row[9])


def get_demand(current, start, interval, predispatch_flag=False):
    if predispatch_flag:
        return read_dispatch_demand(current)
    if 4 < start.hour < 13:
        if interval == 0:
            demand = read_dispatch_demand(start)
        elif current <= datetime.datetime(start.year, start.month, start.day + 1, 4, 0):
            demand = read_predispatch_demand(start, interval * 2)
        else:
            demand = read_dispatch_demand(datetime.datetime(current.year, current.month, current.day - 1, current.hour, current.minute))
    else:
        demand = (read_dispatch_demand(start) if interval == 0 else read_predispatch_demand(start, interval * 2))
    return demand


def plot_demand(start):
    demands = []
    # start = datetime.datetime(2021, 7, 18, 4, 30)

    fig, ax1 = plt.subplots(figsize=(6, 2))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    ax1.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 48, 6)))

    ax1.set_xlabel('Time')
    ax1.set_ylabel('Demand (MW)')

    for i, c in zip(range(24), default.COLOR_LIST * 3):
        t = start + i * default.ONE_HOUR
        demands.append(read_dispatch_demand(t))
        # for j in range(2, (24 - i) * 2, 2):
        #     print(read_predispatch_demand(t, j))
        if t < datetime.datetime(start.year, start.month, start.day, 13, 0):
            predispatch_demand = [read_predispatch_demand(t, j) for j in range(2, (24 - i) * 2, 2)]
            ax1.plot([t + k * default.ONE_HOUR for k in range(24)], predispatch_demand + demands, alpha=0.4, linewidth=0.8, color=c)
        else:
            predispatch_demand = [read_predispatch_demand(t, j) for j in range(2, 48, 2)]
            ax1.plot([t + k * default.ONE_HOUR for k in range(24)], demands[-1:] + predispatch_demand, alpha=0.4, linewidth=0.5, color=c)
    ax1.plot([start + k * default.ONE_HOUR for k in range(24)], demands, linewidth=2, label='Actual Demand', color=default.RED)
    plt.legend()
    # ax1.legend(frameon=True, loc=2)
    plt.show()
    plt.close(fig)


def read_units(units, path_to_unit):
    with path_to_unit.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                units[row[1]].initial_mw = float(row[2])
    return units


def balance(current, start, interval, model, path_to_out, last_prob_id, batteries, path_to_unit):
    total_initial_mw = 0
    prob = Problem(current, 'dispatch', batteries, False)
    parse.add_nemspdoutputs(current, prob.units, prob.links, False, 'dispatch')
    offer.get_units(current, start, interval, 'dispatch', prob.units, prob.links,
                    fcas_flag=False, dispatchload_flag=False, agc_flag=False, debug_flag=True,
                    path_to_out=path_to_out, daily_energy_flag=False)
    if path_to_unit:
        prob.units = read_units(prob.units, path_to_unit)
    demand = get_demand(current, start, interval)
    generation = 0
    if unit_list == set():
        for unit in prob.units.values():
            if unit.region_id == region_id and unit.energy is not None and unit.dispatch_type == 'GENERATOR':
                unit_list.add(unit.duid)
    for duid in unit_list:
        unit = prob.units[duid]
        if last_prob_id is not None:
            unit.initial_mw = model.getVarByName(f'Total_Cleared_{unit.duid}_{last_prob_id}')
            if unit.initial_mw is None:
                unit.initial_mw = 0.0
        else:
            total_initial_mw += unit.initial_mw
        if unit.energy is not None:
            unit.offers = []
            for no, (avail, p) in enumerate(zip(unit.energy.band_avail, unit.energy.price_band)):
                # if unit.renewable_flag and renewable_flag and p > 0:
                # if unit.renewable_flag and renewable_flag:
                #     avail *= RENEWABLE_RATE
                bid_offer = model.addVar(name=f'Energy_Avail{no}_{unit.duid}_{prob.problem_id}')
                unit.offers.append(bid_offer)
                model.addLConstr(bid_offer <= avail, name=f'ENERGY_AVAIL{no}_{unit.duid}_{prob.problem_id}')
            # Total dispatch total_cleared
            unit.total_cleared = model.addVar(name=f'Total_Cleared_{unit.duid}_{prob.problem_id}')
            # Max avail constr
            if unit.energy.max_avail is not None:
                model.addLConstr(unit.total_cleared <= unit.energy.max_avail, name=f'MAX_AVAIL_{unit.duid}_{prob.problem_id}')
            # Total band constr
            model.addLConstr(unit.total_cleared, sense=gp.GRB.EQUAL, rhs=sum(unit.offers), name=f'TOTAL_BAND_MW_OFFER_{unit.duid}_{prob.problem_id}')
            # Renewable UIGF constr
            if unit.forecast_poe50 is not None:
                model.addLConstr(unit.total_cleared <= unit.forecast_poe50, name=f'UIGF_{unit.duid}_{prob.problem_id}')
            # Ramp rate
            up_rate = unit.energy.roc_up if unit.ramp_up_rate is None else unit.ramp_up_rate / 60
            down_rate = unit.energy.roc_down if unit.ramp_down_rate is None else unit.ramp_down_rate / 60
            up_rate, down_rate = scale_ramp_rate(up_rate, down_rate)
            # Ramping up constr
            model.addLConstr(- unit.total_cleared >= -(unit.initial_mw + intervals * up_rate), name=f'ROC_UP_{unit.duid}_{prob.problem_id}')
            # Ramping down constr
            model.addLConstr(unit.total_cleared >= unit.initial_mw - intervals * down_rate, name=f'ROC_DOWN_{unit.duid}_{prob.problem_id}')
            # Calculate costs
            # unit.cost = sum([o * (p / unit.transmission_loss_factor) for o, p in zip(unit.offers, unit.energy.price_band)])
            unit.cost = sum([o * p for o, p in zip(unit.offers, unit.energy.price_band)])
            if unit.dispatch_type == 'GENERATOR':
                # Add cost to objective
                prob.cost += unit.cost
                # demand -= unit.total_cleared
                generation += unit.total_cleared
            elif unit.dispatch_type == 'LOAD':
                # Minus cost from objective
                prob.cost -= unit.cost
                demand += unit.total_cleared
        else:
            print(f'{duid}')
        # else:
        #     prob.units[duid] = None
    # model.addLConstr(demand, gp.GRB.EQUAL, 0, name=f'BALANCE_{prob.problem_id}')
    demand = scale_demand(demand)
    model.addLConstr(generation, gp.GRB.EQUAL, demand, name=f'BALANCE_{prob.problem_id}')
    # if interval == 0:
    #     print(start, 'Total Initial MW: ', total_initial_mw)
    return prob, model, demand


def get_x_value(var):
    return var if type(var) == float or type(var) == int else var.x


def calculate_mbp(unit, mbp):
    for a, p in zip(unit.offers, unit.energy.price_band):
        if a.x != 0:
            mbp = max(p, mbp)
    return mbp


def calculate_dlmp(dual, dlmp):
    return max(dlmp, dlmp + dual)


def forward(start, e, usage, path_to_unit):
    problems, demands = [], []
    last_prob_id = None
    with gp.Env() as env, gp.Model(env=env, name=f'Forward {default.get_case_datetime(start)}') as model:
        model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
        # Initiate cost and penalty of objective function
        total_costs = 0
        for j in range(W):
            battery = helpers.Battery(e, int(e / 3 * 2), usage=usage)
            current = start + j * default.ONE_HOUR
            prob, model, demand = balance(current, start, j, model, battery.bat_dir, last_prob_id, {battery.bat_id: battery}, path_to_unit)
            problems.append(prob)
            demands.append(demand)
            total_costs += prob.cost
            last_prob_id = prob.problem_id
            model.update()
        model.setObjective(total_costs, gp.GRB.MINIMIZE)
        model.optimize()
        # model.setParam('DualReductions', 0)
        if model.status != gp.GRB.Status.OPTIMAL:
            print(f'Model Status Code: {model.status}')
            path_to_model = battery.bat_dir / f'{default.get_case_datetime(start)}.lp'
            model.write(str(path_to_model))
            if model.status == gp.GRB.Status.INFEASIBLE:
                print('Infeasible')
            elif model.status == gp.GRB.Status.UNBOUNDED:
                print('Unbounded')
            elif model.status == gp.GRB.Status.INF_OR_UNBD:
                print('Either')
            debug_infeasible_model(model)
        current_prob, next_prob = problems[0], problems[1]
        lmp = model.getConstrByName(f'BALANCE_{problems[0].problem_id}').pi
        mbp, dlmp = 0, lmp
        path_to_unit = battery.bat_dir / f'Unit_{default.get_case_datetime(start)}.csv'
        with path_to_unit.open('w') as f:
            writer = csv.writer(f)
            for duid in unit_list:
                current_unit = current_prob.units[duid]
                writer.writerow(['I', duid, 'Target', 'Avail', 'Ramp Up', 'Ramp Down'] + current_unit.energy.price_band + ['Up', 'Down'])
                up_constr = model.getConstrByName(f'ROC_UP_{duid}_{next_prob.problem_id}')
                down_constr = model.getConstrByName(f'ROC_DOWN_{duid}_{next_prob.problem_id}')
                writer.writerow(['D', duid, current_unit.total_cleared.x, current_unit.energy.max_avail, next_prob.units[duid].ramp_up_rate, next_prob.units[duid].ramp_down_rate] + [f'{o.x} ({a})' for o, a in zip(current_unit.offers, current_unit.energy.band_avail)] + [up_constr.pi, down_constr.pi])
                if up_constr.pi != 0 or down_constr.pi != 0:
                    # print(f'!!! Ramping constr binding {current_prob.current}!!!')
                    dlmp = calculate_dlmp(abs(up_constr.pi), dlmp)
                    dlmp = calculate_dlmp(- abs(down_constr.pi), dlmp)
                if current_unit.total_cleared.x != 0:
                    mbp = calculate_mbp(current_unit, mbp)
            writer.writerow(['Price', lmp, mbp, dlmp])
            print(current_prob.current, 'LMP:', lmp, 'MBP:', mbp, 'DLMP:', dlmp, 'Demand:', demands[0])
        return path_to_unit


def recede():
    start_datetime = datetime.datetime.now()
    print(f'Start: {start_datetime}')
    # initial_time = datetime.datetime(2021, 7, 18, 4, 30)
    initial_time = datetime.datetime(2021, 9, 12, 4, 30)
    energy = 0
    usage = f'DLMP length = {W}'
    path_to_unit = None
    for i in range(T):
        path_to_unit = forward(initial_time + i * default.ONE_HOUR, energy, usage, path_to_unit)
    end_datetime = datetime.datetime.now()
    print(f'End: {end_datetime}')
    print(f'Cost: {end_datetime - start_datetime}')


def filter_units():
    unit_set = set()
    e = 0
    usage = f'DLMP length = {W}'
    battery = helpers.Battery(e, int(e / 3 * 2), usage=usage)
    start = datetime.datetime(2021, 7, 18, 4, 30)
    for i in range(T):
        path_to_unit = battery.bat_dir / f'Unit_{default.get_case_datetime(start)}.csv'
        with path_to_unit.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == 'D' and float(row[2]) != 0:
                    unit_set.add(row[1])
    print(len(unit_set))
    print(unit_set)


if __name__ == '__main__':
    recede()
    # filter_units()