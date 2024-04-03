import csv
import datetime
import default
from gurobipy import *
# from balance import get_demand
import pandas as pd
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
import matplotlib.pyplot as plt
plt.style.use(['science', 'ieee', 'no-latex'])
plt.rcParams['axes.unicode_minus']=False
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
from pathlib import Path


def plot_demand():
    from balance import read_dispatch_demand, read_predispatch_demand
    from matplotlib.pyplot import MultipleLocator
    demand_scale = 1
    fig, ax1 = plt.subplots(figsize=(6, 2))
    ax1.xaxis.set_major_locator(MultipleLocator(24))
    c1, c2, c3 = default.PURPLE, default.BLUE, default.BROWN
    initial_time = datetime.datetime(2022, 1, 2, 4, 30)
    week1_prices = [read_dispatch_demand(initial_time + default.ONE_HOUR * i) / demand_scale for i in range(24 * 7)]
    days = np.arange(len(week1_prices))
    plt.plot(days, week1_prices, label='Summer Week', color=c1)
    for k in range(7):
        t = initial_time + default.ONE_HOUR * k * 24
        demands = [read_predispatch_demand(t, j * 2) / demand_scale for j in range(24)]
        if k == 0:
            plt.plot(np.arange(k * 24, k * 24 + 24), demands, color=c1, alpha=0.3, linewidth=4, linestyle='solid',
                     label='Summer Week Forecast')
        else:
            plt.plot(np.arange(k * 24, k * 24 + 24), demands, color=c1, alpha=0.3, linewidth=4, linestyle='solid')
    initial_time = datetime.datetime(2021, 7, 18, 4, 30)
    week2_prices = [read_dispatch_demand(initial_time + default.ONE_HOUR * i) / demand_scale for i in range(24 * 7)]
    plt.plot(days, week2_prices, label='Winter Week', color=c2)
    for k in range(7):
        t = initial_time + default.ONE_HOUR * k * 24
        demands = [read_predispatch_demand(t, j * 2) / demand_scale for j in range(24)]
        if k == 0:
            plt.plot(np.arange(k * 24, k * 24 + 24), demands, color=c2, alpha=0.3, linewidth=4, linestyle='solid',
                     label='Winter Week Forecast')
        else:
            plt.plot(np.arange(k * 24, k * 24 + 24), demands, color=c2, alpha=0.3, linewidth=4, linestyle='solid')
    initial_time = datetime.datetime(2021, 9, 12, 4, 30)
    week3_prices = [read_dispatch_demand(initial_time + default.ONE_HOUR * i) / demand_scale for i in range(24 * 7)]
    plt.plot(days, week3_prices, label='Moderate Week', color=c3)
    for k in range(7):
        t = initial_time + default.ONE_HOUR * k * 24
        demands = [read_predispatch_demand(t, j * 2) / demand_scale for j in range(24)]
        if k == 0:
            plt.plot(np.arange(k * 24, k * 24 + 24), demands, color=c3, alpha=0.3, linewidth=4, linestyle='solid',
                     label='Moderate Week Forecast')
        else:
            plt.plot(np.arange(k * 24, k * 24 + 24), demands, color=c3, alpha=0.3, linewidth=4, linestyle='solid')
    plt.xlabel('Period (Hour)')
    plt.ylabel('Demand (MW)')
    # plt.title('Comparison of Market Prices for Three Weeks')
    # plt.legend()
    plt.legend(loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize='small')
    plt.grid(True)
    # plt.show()
    plt.savefig(default.EXPERIMENT_DIR / 'pricing' / 'demand.jpg')
    plt.close(fig)


def up_toy():
    with Env() as env, Model(env=env, name='Test0') as m:
        A1 = m.addVar(lb=-GRB.INFINITY, name='A1')
        A2 = m.addVar(lb=-GRB.INFINITY, name='A2')
        B1 = m.addVar(lb=-GRB.INFINITY, name='B1')
        B2 = m.addVar(lb=-GRB.INFINITY, name='B2')
        m.update()
        for var in [A1, A2, B1, B2]:
            m.addLConstr(var >= 0, name=f'LB_{var.varName}')
            m.addLConstr(var <= 200, name=f'UB_{var.varName}')

        D1 = 300
        D2 = 100
        balance_constr1 = m.addLConstr(A1 + B1, GRB.EQUAL, D1, name='BALANCE_1')
        balance_constr2 = m.addLConstr(A2 + B2, GRB.EQUAL, D2, name='BALANCE_2')
        m.addConstr(A2 <= A1 + 10, name='RAMP_UP_A2')
        objective = A1 * 100 + A2 * 5 + B1 * 10 + B2 * 20
        m.setObjective(objective, GRB.MINIMIZE)
        m.optimize()

        print(f'D2 = {D2} and dual value is {balance_constr1.pi}')
        print(A1, A2, B1, B2)
        for constr in m.getConstrs():
            print(f'Dual {constr.constrName}: {constr.pi}')
        for var in m.getVars():
            print(f'{var.varName}: {var.RC}')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')

    with Env() as env, Model(env=env, name='Test1') as m:
        A1 = m.addVar(lb=-GRB.INFINITY, name='A1')
        A2 = m.addVar(lb=-GRB.INFINITY, name='A2')
        B1 = m.addVar(lb=-GRB.INFINITY, name='B1')
        B2 = m.addVar(lb=-GRB.INFINITY, name='B2')
        m.update()
        for var in [A1, A2, B1, B2]:
            m.addLConstr(var >= 0, name=f'LB_{var.varName}')
            m.addLConstr(-var >= -200, name=f'UB_{var.varName}')

        D1 = 300
        D2 = 200
        balance_constr1 = m.addLConstr(A1 + B1, GRB.EQUAL, D1, name='BALANCE_1')
        balance_constr2 = m.addLConstr(A2 + B2, GRB.EQUAL, D2, name='BALANCE_2')
        m.addConstr(A2 <= A1 + 10, name='RAMP_UP_A2')
        objective = A1 * 100 + A2 * 5 + B1 * 10 + B2 * 20
        m.setObjective(objective, GRB.MINIMIZE)
        m.optimize()

        print(f'D2 = {D2} and dual value is {balance_constr1.pi}')
        print(A1, A2, B1, B2)
        for constr in m.getConstrs():
            print(f'Dual {constr.constrName}: {constr.pi}')
        for var in m.getVars():
            print(f'{var.varName}: {var.RC}')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')

    with Env() as env, Model(env=env, name='Test1') as m:
        A1 = m.addVar(lb=-GRB.INFINITY, ub=GRB.INFINITY, name='A1')
        B1 = m.addVar(lb=-GRB.INFINITY, ub=GRB.INFINITY, name='B1')
        D1 = 300

        m.addLConstr(A1 <= 200, name='UB_A1')
        m.addLConstr(B1 <= 200, name='UB_B2')
        m.addLConstr(A1 >= 0, name='LB_A1')
        m.addLConstr(B1 >= 0, name='LB_B2')
        m.addLConstr(A1 <= 180, name='RAMP_UP_A1')
        m.addLConstr(A1 >= 50, name='RAMP_DOWN_A1')
        m.addLConstr(B1 <= 120, name='RAMP_UP_B1')
        m.addLConstr(B1 >= 50, name='RAMP_DOWN_B1')
        m.addLConstr(A1 + B1, GRB.EQUAL, D1, name='BALANCE_1')
        objective = A1 * 15 + B1 * 10
        m.setObjective(objective, GRB.MINIMIZE)
        m.optimize()
        for constr in m.getConstrs():
            print(f'Dual {constr.constrName}: {constr.pi}')
        for var in m.getVars():
            print(f'{var.varName}: {var.RC}')
        print(A1,  B1)


def down_toy():
    with Env() as env, Model(env=env, name='Test0') as m:
        A1 = m.addVar(lb=-GRB.INFINITY, name='A1')
        A2 = m.addVar(lb=-GRB.INFINITY, name='A2')
        B1 = m.addVar(lb=-GRB.INFINITY, name='B1')
        B2 = m.addVar(lb=-GRB.INFINITY, name='B2')
        m.update()
        for var in [A1, A2, B1, B2]:
            m.addLConstr(var >= 0, name=f'LB_{var.varName}')
            m.addLConstr(var <= 200, name=f'UB_{var.varName}')

        D1 = 350
        D2 = 100
        balance_constr1 = m.addLConstr(A1 + B1, GRB.EQUAL, D1, name='BALANCE_1')
        balance_constr2 = m.addLConstr(A2 + B2, GRB.EQUAL, D2, name='BALANCE_2')
        m.addConstr(A2 >= A1 - 150, name='RAMP_UP_A2')
        objective = A1 * 5 + A2 * 80 + B1 * 20 + B2 * 30
        m.setObjective(objective, GRB.MINIMIZE)
        m.optimize()

        print(f'D2 = {D2} and dual value is {balance_constr1.pi}')
        print(A1, A2, B1, B2)
        for constr in m.getConstrs():
            print(f'Dual {constr.constrName}: {constr.pi}')
        for var in m.getVars():
            print(f'{var.varName}: {var.RC}')

    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    with Env() as env, Model(env=env, name='Test0') as m:
        A1 = m.addVar(lb=-GRB.INFINITY, name='A1')
        A2 = m.addVar(lb=-GRB.INFINITY, name='A2')
        B1 = m.addVar(lb=-GRB.INFINITY, name='B1')
        B2 = m.addVar(lb=-GRB.INFINITY, name='B2')
        m.update()
        for var in [A1, A2, B1, B2]:
            m.addLConstr(var >= 0, name=f'LB_{var.varName}')
            m.addLConstr(var <= 200, name=f'UB_{var.varName}')

        D1 = 350
        D2 = 50
        balance_constr1 = m.addLConstr(A1 + B1, GRB.EQUAL, D1, name='BALANCE_1')
        balance_constr2 = m.addLConstr(A2 + B2, GRB.EQUAL, D2, name='BALANCE_2')
        m.addConstr(A2 >= A1 - 150, name='RAMP_UP_A2')
        objective = A1 * 5 + A2 * 80 + B1 * 20 + B2 * 30
        m.setObjective(objective, GRB.MINIMIZE)
        m.optimize()

        print(f'D2 = {D2} and dual value is {balance_constr1.pi}')
        print(A1, A2, B1, B2)
        for constr in m.getConstrs():
            print(f'Dual {constr.constrName}: {constr.pi}')
        for var in m.getVars():
            print(f'{var.varName}: {var.RC}')


def vary_toy():
    with Env() as env, Model(env=env, name='VARY') as m:
        A1 = m.addVar(lb=-GRB.INFINITY, name='A1')
        A2 = m.addVar(lb=-GRB.INFINITY, name='A2')
        B1 = m.addVar(lb=-GRB.INFINITY, name='B1')
        B2 = m.addVar(lb=-GRB.INFINITY, name='B2')
        m.update()
        for var in [A1, A2, B1, B2]:
            m.addLConstr(var >= 0, name=f'LB_{var.varName}')
            m.addLConstr(var <= 200, name=f'UB_{var.varName}')
        D1 = 350
        D2 = 50
        balance_constr1 = m.addLConstr(A1 + B1, GRB.EQUAL, D1, name='BALANCE_1')
        balance_constr2 = m.addLConstr(A2 + B2, GRB.EQUAL, D2, name='BALANCE_2')
        m.addConstr(A2 >= A1 - 150, name='RAMP_DOWN_A2')
        m.addConstr(A2 <= A1 + 10, name='RAMP_UP_A2')
        objective = A1 * 5 + A2 * 80 + B1 * 20 + B2 * 30
        m.setObjective(objective, GRB.MINIMIZE)
        m.optimize()

        print(f'D2 = {D2} and dual value is {balance_constr1.pi}')
        print(A1, A2, B1, B2)
        for constr in m.getConstrs():
            print(f'Dual {constr.constrName}: {constr.pi}')
        for var in m.getVars():
            print(f'{var.varName}: {var.RC}')


GENERATOR_NAMES = ['G1', 'G2', 'G3']
GENERATOR_CAPACITY = [300, 300, 300]
GENERATOR_PRICES = [80, 60, 100]
GENERATOR_RAMP_RATE = [30, 35, 85]
BATT_GEN_PRICE = 90
BATT_LOAD_PRICE = 70
E_MAX = 450
P_MAX = 300
eta = 0.95
T, W = 24, 24
PATH_TO_DIR = default.EXPERIMENT_DIR / 'pricing' / ('long' if W == 24 else 'short')


def get_marginal(prices, results):
    return max([p * int(r > 0) for p, r in zip(prices, results)])


def complicate_toy(initial, batt_flag=False, simplify_flag=True, scale=None):
    g_initial = [150 for _ in range(len(GENERATOR_NAMES))]
    E_initial = E_MAX * 0.5
    path_to_file = PATH_TO_DIR / f'toy_{scale}_{default.get_case_datetime(initial)}.csv'
    if path_to_file.is_file():
        return None
    with path_to_file.open('w') as f:
        writer = csv.writer(f)
        sublist = ['InterRampUp', 'InterRampDown', 'IntraRampUp', 'IntraRampDown', 'UpperBound', 'LowerBound']
        row = ['Datetime', 'LMP', 'Marginal']
        for name in GENERATOR_NAMES:
            row += [name] + ([] if simplify_flag else [f'{name} {s}' for s in sublist])
        if batt_flag:
            row += ['Discharge', 'DischargeDual', 'Charge', 'ChargeDual']
        writer.writerow(row)
        for w in range(T):
            start = initial + default.ONE_HOUR * w
            demands = [get_demand(start + default.ONE_HOUR * interval, start, interval, scale is None) / 10 for interval in range(W)]
            if scale is not None:
                # demands += np.random.normal(loc=0, scale=scale, size=len(demands))
                noise = np.random.normal(loc=0, scale=scale, size=len(demands))
                demands = [d + sum(noise[:n + 1]) for n,  d in enumerate(demands)]
            obj = 0
            with Env() as env, Model(env=env, name=f'Balance_{w}') as model:
                generators = [[model.addVar(lb=-GRB.INFINITY, name=f'{name}_{w}_{t}') for t in range(W)] for name in
                              GENERATOR_NAMES]
                model.update()
                for ub, generator in zip(GENERATOR_CAPACITY, generators):
                    for var in generator:
                        model.addLConstr(var >= 0, name=f'LB_{var.varName}')
                        model.addLConstr(-var >= -ub, name=f'UB_{var.varName}')
                if batt_flag:
                    pl = [model.addVar(lb=-GRB.INFINITY, name=f'PL_{w}_{t}') for t in range(W)]
                    pg = [model.addVar(lb=-GRB.INFINITY, name=f'PG_{w}_{t}') for t in range(W)]
                    model.update()
                    for p in [pl, pg]:
                        for var in p:
                            model.addLConstr(var >= 0, name=f'LB_{var.varName}')
                            model.addLConstr(var <= P_MAX, name=f'UB_{var.varName}')
                    for pload, pgen in zip(pl, pg):
                        model.addSOS(GRB.SOS_TYPE1, [pload, pgen])
                    E = [model.addVar(ub=E_MAX, name=f'E_{w}_{t}') for t in range(W)]
                for t in range(W):
                    if batt_flag:
                        model.addLConstr(E[t], GRB.EQUAL, (E_initial if t == 0 else E[t - 1]) + (eta * pl[t] - pg[t] / eta),
                                         name=f'E_TRANSITION_{w}_{t}')
                        model.addLConstr(sum([g[t] for g in generators]) + pg[t], GRB.EQUAL, pl[t] + demands[t],
                                         name=f'BALANCE_{w}_{t}')
                    else:
                        model.addLConstr(sum([g[t] for g in generators]), GRB.EQUAL, demands[t], name=f'BALANCE_{w}_{t}')
                    for i in range(len(GENERATOR_NAMES)):
                        model.addLConstr(
                            - generators[i][t] >= - (g_initial[i] if t == 0 else generators[i][t - 1]) - GENERATOR_RAMP_RATE[i],
                            name=f'RAMP_UP_G{i + 1}_{w}_{t}')
                        model.addLConstr(
                            generators[i][t] >= (g_initial[i] if t == 0 else generators[i][t - 1]) - GENERATOR_RAMP_RATE[i],
                            name=f'RAMP_DOWN_G{i + 1}_{w}_{t}')
                for p, g in zip(GENERATOR_PRICES, generators):
                    obj += p * sum(g)
                if batt_flag:
                    obj += BATT_GEN_PRICE * sum(pg) - BATT_LOAD_PRICE * sum(pl)
                model.setObjective(obj, GRB.MINIMIZE)
                model.optimize()
                if batt_flag:
                    model = model.fixed()
                    model.optimize()
                # print('Obj:', model.getObjective().getValue())
                print(start)
                constr = model.getConstrByName(f'BALANCE_{w}_0')
                print(f'Dual {constr.constrName}: {constr.pi}')
                if batt_flag:
                    row = [start, constr.pi, get_marginal(GENERATOR_PRICES + [BATT_GEN_PRICE, BATT_LOAD_PRICE],
                                                          [model.getVarByName(f'{name}_{w}_0').x for name in
                                                           GENERATOR_NAMES] + [pg[0].x, pl[0].x])]
                else:
                    row = [start, constr.pi, get_marginal(GENERATOR_PRICES, [model.getVarByName(f'{name}_{w}_0').x for name in GENERATOR_NAMES])]
                for name in GENERATOR_NAMES:
                    var = model.getVarByName(f'{name}_{w}_0')
                    print(f'{name}: {var.x}')
                    inter_up_constr = model.getConstrByName(f'RAMP_UP_{name}_{w}_0')
                    print(f'InterUp: {inter_up_constr.pi}')
                    inter_down_constr = model.getConstrByName(f'RAMP_DOWN_{name}_{w}_0')
                    print(f'InterDown: {inter_down_constr.pi}')
                    if W != 1:
                        up_constr = model.getConstrByName(f'RAMP_UP_{name}_{w}_1')
                        print(f'Up: {up_constr.pi}')
                        down_constr = model.getConstrByName(f'RAMP_DOWN_{name}_{w}_1')
                        print(f'Down: {down_constr.pi}')
                    upper_constr = model.getConstrByName(f'UB_{var.varName}')
                    print(f'UpperBound: {upper_constr.pi}')
                    lower_constr = model.getConstrByName(f'LB_{var.varName}')
                    print(f'LowerBound: {lower_constr.pi}')
                    if simplify_flag:
                        row += [var.x]
                    else:
                        row += [var.x, inter_up_constr.pi, inter_down_constr.pi, '-' if W == 1 else up_constr.pi, '-' if W == 1 else down_constr.pi, upper_constr.pi, lower_constr.pi]
                if batt_flag:
                    row += [pg[0].x, model.getConstrByName(f'E_TRANSITION_{w}_1').pi * eta, pl[0].x, model.getConstrByName(f'E_TRANSITION_{w}_1').pi / eta]
                    E_initial = E[0].x
                g_initial = [generators[i][0].x for i in range(len(GENERATOR_NAMES))]
                writer.writerow(row)


def read_toy(initial, scale=None):
    path_to_file = PATH_TO_DIR / f'toy_{scale}_{default.get_case_datetime(initial)}.csv'
    df = pd.read_csv(path_to_file)
    df = df[(df.Datetime != 'Datetime')]
    lmps = df['LMP'].astype(float)
    ihlmps = df['Marginal'].astype(float)
    generator_dispatch = [list(df[name].astype(float)) for name in GENERATOR_NAMES]
    dis = df['Discharge'].astype(float)
    cha = df['Charge'].astype(float)
    return list(lmps), list(ihlmps), generator_dispatch, list(dis), list(cha)


def plot_price(prices, labels, filename):
    fig, ax1 = plt.subplots(figsize=(6, 2))
    ax1.set_xlabel('Period (Hour)')
    ax1.set_ylabel('Price ($/MWh)')
    for price, label, color in zip(prices, labels, default.COLOR_LIST):
        ax1.plot(range(1, len(price) + 1), price, label=label, color=color)
    ax1.legend(frameon=True)
    # plt.show()
    path_to_fig = PATH_TO_DIR / f'{filename}.jpg'
    plt.savefig(path_to_fig)
    plt.close(fig)


def calculate_tlmp(results, lmps, ihlmps, bid):
    tlmps = []
    for result, lmp, ihlmp, in zip(results, lmps, ihlmps):
        if result == 0:
            tlmps.append(lmp)
        elif lmp <= bid:
            tlmps.append(bid)
        elif bid == ihlmp:
            tlmps.append(bid)
        else:
            tlmps.append(lmp)
    return tlmps


def calculate_batt_tlmp(diss, chas, lmps, ihlmps):
    batt_tlmps = []
    for dis, cha, lmp, ihlmp in zip(diss, chas, lmps, ihlmps):
        if dis == 0 and cha == 0:
            batt_tlmps.append(lmp)
        else:
            bid = BATT_GEN_PRICE if dis > 0 else BATT_LOAD_PRICE
            if lmp <= bid:
                batt_tlmps.append(bid)
            elif bid == ihlmp:
                batt_tlmps.append(bid)
            else:
                batt_tlmps.append(lmp)
    return batt_tlmps


def plot_bar(xaxis, yaxis, ylabel, filename):
    fig, ax = plt.subplots()
    # ax.set_xlabel('Time (Hour)')
    ax.set_ylabel(ylabel)
    plt.bar(xaxis, yaxis, color=default.COLOR_LIST[4:])
    # plt.show()
    path_to_fig = PATH_TO_DIR / f'{filename}.jpg'
    plt.savefig(path_to_fig)
    plt.close(fig)


def plot_grouped_bar(values, types, ylabel, categories=None, filename=None, path_to_fig=None, colors=None, ylim=None):
    # Sample data
    if categories is None:
        categories = ['LMP', 'TLMP', 'TDLMP']

    # Determine the width of each bar
    bar_width = 0.2

    # Create a figure and axes
    # fig, ax = plt.subplots()
    fig, ax = plt.subplots(figsize=(4, 2))

    # Generate the x-axis positions for each category and type
    x_positions = np.arange(len(categories))

    if colors is None:
        colors = [default.BLUE, default.PURPLE, default.BROWN]

    if ylim is not None:
        if type(ylim) == list:
            ax.set_ylim(ylim)
        else:
            plt.ylim(0, ylim)

    formatter = ticker.ScalarFormatter(useMathText=True)
    formatter.set_powerlimits((-3, 3))  # Adjust the power limits as needed
    plt.gca().yaxis.set_major_formatter(formatter)

    # Plot the bars for each type
    for i in range(len(types)):
        bars = ax.bar(x_positions + i * bar_width, values[:, i], width=bar_width, label=types[i], color=colors[i], alpha=0.65)
        # for rect in bars:
        #     height = rect.get_height()
        #     plt.text(rect.get_x() + rect.get_width() / 2.0, height, '%d' % int(height), ha='center', va='bottom')

    # Customize the plot
    # ax.set_xlabel('Categories')
    ax.set_ylabel(ylabel)
    ax.set_xticks(x_positions + (len(types) - 1) * bar_width / 2)
    ax.set_xticklabels(categories)
    # ax.legend()
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), ncol=(4 if len(types) == 4 else 3), fontsize='small')
    # Display the plot
    if filename is None:
        if path_to_fig is None:
            plt.show()
        else:
            plt.savefig(path_to_fig)
    else:
        plt.savefig(default.EXPERIMENT_DIR / 'pricing' / f'{filename}.jpg')
        plt.close(fig)


def process_price(initial, scale):
    lmps, ihlmps, generator_results, diss, chas = read_toy(initial, scale)
    generator_tlmps = [calculate_tlmp(results, lmps, ihlmps, bid) for results, bid in zip(generator_results, GENERATOR_PRICES)]
    batt_tlmps = calculate_batt_tlmp(diss, chas, lmps, ihlmps)
    all_tlmps = []
    for tlmps in generator_tlmps:
        all_tlmps += tlmps
    all_tlmps += batt_tlmps
    plot_price(generator_tlmps + [batt_tlmps], [f'{name} TLMP' for name in (GENERATOR_NAMES + ['Batt'])], 'TLMP' if scale is None else f'TLMP_{scale}')
    plot_price([lmps, ihlmps, ihlmps], ['LMP', 'TDLMP', '$C_t$'], 'IHLMP' if scale is None else f'IHLMP_{scale}')
    # plot_price([[lmp - ihlmp for lmp, ihlmp in zip(lmps, ihlmps)]], ['Factor'], 'Factor')

    lmp_mwp, lmp_extra, ihlmp_mwp, ihlmp_extra, tlmp_mwp, tlmp_extra, lmp_loc, ihlmp_loc, tlmp_loc = 0, 0, 0, 0, 0, 0, 0, 0, 0
    for no, (lmp, ihlmp, dis, cha, batt_tlmp) in enumerate(zip(lmps, ihlmps, diss, chas, batt_tlmps)):
        for generator_price, generator_result, tlmps, ramp, capacity in zip(GENERATOR_PRICES, generator_results, generator_tlmps, GENERATOR_RAMP_RATE, GENERATOR_CAPACITY):
            lmp_mwp += max(0, generator_price - lmp) * generator_result[no]
            ihlmp_mwp += max(0, generator_price - ihlmp) * generator_result[no]
            tlmp_mwp += max(0, generator_price - tlmps[no]) * generator_result[no]
            lmp_extra += max(0, lmp - ihlmp) * generator_result[no]
            ihlmp_extra += max(0, ihlmp - ihlmp) * generator_result[no]
            tlmp_extra += max(0, tlmps[no] - ihlmp) * generator_result[no]
            lmp_loc += max(0, lmp - generator_price) * max(min(capacity, (150 if no == 0 else generator_result[no - 1]) + ramp) - generator_result[no], 0)
            ihlmp_loc += max(0, ihlmp - generator_price) * max(min(capacity, (150 if no == 0 else generator_result[no - 1]) + ramp) - generator_result[no], 0)
            tlmp_loc += max(0, tlmps[no] - generator_price) * max(min(capacity, (150 if no == 0 else generator_result[no - 1]) + ramp) - generator_result[no], 0)
        if lmp != ihlmp:
            row = f'{no + 1} & '
            for generator_result, tlmps in zip(generator_results, generator_tlmps):
                row += f'{generator_result[no]:.2f} & {(tlmps[no] - lmp):.2f} & {tlmps[no]:.2f} & '
            row += f'{dis:.2f} & {(batt_tlmp - lmp):.2f} & {batt_tlmp:.2f} & {cha:.2f} & {(batt_tlmp - lmp):.2f} & {batt_tlmp:.2f} & {lmp:.2f} & {ihlmp:.2f} \\\\'
            # print(row.replace('.00', ''))
    plot_bar(['LMP', 'TLMP', 'IHLMP'], [lmp_mwp, tlmp_mwp, ihlmp_mwp], 'Make-Whole Payment ($)', 'MWP' if scale is None else f'MWP_{scale}')
    plot_bar(['LMP', 'TLMP', 'IHLMP'], [lmp_extra, tlmp_extra, ihlmp_extra], 'Extra Payment ($)', 'EXTRA' if scale is None else f'EXTRA_{scale}')
    # print(f'{initial} & {np.mean(lmps):.2f} & {np.std(lmps):.2f} & {lmp_mwp:.2f} & {lmp_extra:.2f} & {np.mean(ihlmps):.2f} & {np.std(ihlmps):.2f} & {ihlmp_mwp:.2f} & {ihlmp_extra:.2f} & {tlmp_mwp:.2f} & {tlmp_extra:.2f}')
    return lmp_mwp, tlmp_mwp, ihlmp_mwp, lmp_extra, tlmp_extra, ihlmp_extra, lmp_loc, ihlmp_loc, tlmp_loc
    # return lmps, ihlmps, all_tlmps


def forecast(start):
    forecasts = [get_demand(start + default.ONE_HOUR * interval, start, interval) / 10 for interval in range(W)]

    # Assume you have generated forecasts stored in a list or array called 'forecasts'
    # Generate random noise based on a normal distribution with mean 0 and standard deviation 0.1
    noise = np.random.normal(loc=0, scale=10, size=len(forecasts))

    # Add the random noise to the forecasts
    forecasts_with_noise = forecasts + noise

    fig, ax1 = plt.subplots(figsize=(6, 2))
    ax1.set_xlabel('Time (Hour)')
    ax1.set_ylabel('Demand (MW)')
    for price, label, color in zip([forecasts, forecasts_with_noise], ['Actual', 'Error'], default.COLOR_LIST):
        ax1.plot(range(1, len(price) + 1), price, label=label, color=color)
    ax1.legend(frameon=True)
    plt.show()


def different_scales():
    initial = datetime.datetime(2021, 7, 18, 4, 30)
    scales = [0, 0.001, 0.006, 0.06, 0.5, 1, 10]
    mwps = [[], [], []]
    extras = [[], [], []]
    for scale in scales:
        for d in range(1):
            complicate_toy(initial + default.ONE_DAY * d, batt_flag=True, simplify_flag=False, scale=scale)
        lmp_mwp, tlmp_mwp, ihlmp_mwp, lmp_extra, tlmp_extra, ihlmp_extra, lmp_loc, ihlmp_loc, tlmp_loc  = process_price(initial, scale)
        for mwp, value in zip(mwps, [lmp_mwp, tlmp_mwp, ihlmp_mwp]):
            mwp.append(value)
        for extra, value in zip(extras, [lmp_extra, tlmp_extra, ihlmp_extra]):
            extra.append(value)
    plot_grouped_bar(np.array(mwps), scales, 'Make-Whole Payment ($)')
    plot_grouped_bar(np.array(extras), scales, 'Extra Payment ($)')


def different_dates(initial):
    scale = None
    all_lmps, all_tlmps, all_ihlmps = [], [], []
    all_lmp_mwp, all_lmp_extra, all_tlmp_extra = 0, 0, 0
    all_lmp_loc, all_ihlmp_loc, all_tlmp_loc = 0, 0, 0
    for d in range(7):
        complicate_toy(initial + default.ONE_DAY * d, batt_flag=True, simplify_flag=False, scale=scale)
        # lmps, ihlmps, tlmps = process_price(initial + default.ONE_DAY * d, scale)
        # all_lmps += lmps
        # all_tlmps += tlmps
        # all_ihlmps += ihlmps

        lmp_mwp, tlmp_mwp, ihlmp_mwp, lmp_extra, tlmp_extra, ihlmp_extra, lmp_loc, ihlmp_loc, tlmp_loc = process_price(initial + default.ONE_DAY * d, scale)
        all_lmp_mwp += lmp_mwp
        all_lmp_extra += lmp_extra
        all_tlmp_extra += tlmp_extra
        all_lmp_loc += lmp_loc
        all_ihlmp_loc += ihlmp_loc
        all_tlmp_loc += tlmp_loc
    # print(f'{initial} & {np.std(all_lmps) / np.mean(all_lmps):.4f} & {np.std(all_tlmps) / np.mean(all_tlmps):.4f} & {np.std(all_ihlmps) / np.mean(all_ihlmps):.4f}')
    # print(f'{initial} & {np.mean(all_lmps):.2f} & {np.std(all_lmps):.2f} & {np.mean(all_tlmps):.2f} & {np.std(all_tlmps):.2f} & {np.mean(all_ihlmps):.2f} & {np.std(all_ihlmps):.2f}')
    # print(f'{initial} & {all_lmp_mwp:.2f} & {all_lmp_extra:.2f} & {all_tlmp_extra:.2f}')
    print(f'{initial} & {all_lmp_loc:.2f} & {all_ihlmp_loc:.2f} & {all_tlmp_loc:.2f}')

def plot_volatility():
    volatility = [
        [0.1349, 0.1012, 0.1208, 0.1178, 0.0983, 0.1160],
        [0.1265, 0.0933, 0.1111, 0.1143, 0.0911, 0.1066],
        [0.1014, 0.0684, 0.0771, 0.1057, 0.0673, 0.0676]
    ]
    volatility = [[vola[0], vola[3], vola[1], vola[4], vola[2], vola[5]] for vola in volatility]
    categories = ['Winter\nShort', 'Winter\nLong', 'Summer\nShort', 'Summer\nLong', 'Moderate\nShort', 'Moderate\nLong']
    # categories = ['WS', 'WL', 'SS', 'SL', 'MS', 'ML']
    types = ['LMP', 'TLMP', 'TDLMP']
    plot_grouped_bar(np.array(volatility).transpose(), types, 'Normalised Standard Deviation', categories, 'volatility')


def plot_extra():
    extra = [
        [8.902, 10.00, 11.41, 6.512, 9.376, 7.537],
        [6.001, 6.120, 6.890, 4.811, 5.820, 5.250],
        [0, 0, 0, 0, 0, 0]
    ]
    extra = [[element * 100000 for element in row] for row in extra]
    extra = [[vola[0], vola[3], vola[1], vola[4], vola[2], vola[5]] for vola in extra]
    categories = ['Winter\nShort', 'Winter\nLong', 'Summer\nShort', 'Summer\nLong', 'Moderate\nShort', 'Moderate\nLong']
    # categories = ['WS', 'WL', 'SS', 'SL', 'MS', 'ML']
    types = ['LMP', 'TLMP', 'TDLMP']
    plot_grouped_bar(np.array(extra).transpose(), types, 'Extra Payment (\$)', categories, 'extra')


def plot_loc():
    loc = [
        [5.817, 2.286, 7.973, 8.639, 12.569, 11.531],
        [3.781, 1.394, 3.533, 4.331, 7.163, 8.696],
        [0, 0, 0, 0, 0, 0]
    ]
    loc = [[element * 100000 for element in row] for row in loc]
    loc = [[vola[0], vola[3], vola[1], vola[4], vola[2], vola[5]] for vola in loc]
    categories = ['Winter\nShort', 'Winter\nLong', 'Summer\nShort', 'Summer\nLong', 'Moderate\nShort', 'Moderate\nLong']
    # categories = ['WS', 'WL', 'SS', 'SL', 'MS', 'ML']
    types = ['LMP', 'TDLMP', 'NTDLMP']
    plot_grouped_bar(np.array(loc).transpose(), types, 'Lost Opportunity Cost (\$)', categories, 'loc')


if __name__ == '__main__':
    start_datetime = datetime.datetime.now()
    print(f'Start: {start_datetime}')
    initial1 = datetime.datetime(2021, 7, 18, 4, 30)
    initial2 = datetime.datetime(2022, 1, 2, 4, 30)
    initial3 = datetime.datetime(2021, 9, 12, 4, 30)
    # for initial in [initial1, initial2, initial3]:
    #     different_dates(initial)
    # plot_bar(None, None)
    # plot_demand()
    # plot_volatility()
    plot_extra()
    # plot_loc()
    end_datetime = datetime.datetime.now()
    print(f'End: {end_datetime}')
    print(f'Cost: {end_datetime - start_datetime}')
