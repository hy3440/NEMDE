# Battery operation model

import gurobipy as gp
import default, write
from helpers import marginal_costs
from price import process_prices_by_interval, process_given_prices_by_interval


# relationship between number of cycles and DoD (see paper Omar2014Lithium)
# socs = [k / 100 for k in range(0, 100, 5)]
# degradations = [get_degradations(s) for s in socs]


def get_cycles(dod):
    """ Battery degradation model from paper Duggal2015Short. """
    return 1591.1 * pow(dod, -2.089)


def get_degradations(x):
    """ Convert number of cycles versus DoD to degradation percentage versus SoC (see paper Ying2016Stochastic). """
    return 1 / get_cycles(1 - x)


dods = [20, 40, 60, 80, 100]
cycles = [34957, 19985, 10019, 3221, 2600]
socs = [0.8, 0.6, 0.2, 0]
degradations = [1 / 34957, 1 / 19985, 1 / 10019, 1 / 3221, 1 / 2600]


def schedule(current, battery, p5min_times=None, p5min_prices=None, aemo_p5min_prices=None, predispatch_times=None,
             predispatch_prices=None, aemo_predispatch_prices=None, custom_flag=True, horizon=None, k=0, E_initial=None,
             method=None, band=None, fcas_flag=False, fcas_type=None, multi_flag=False, der_flag=False, prices=None):
    """ Battery operation optimisation.

    Args:
        current (datetime.datetime): current datetime
        battery (helpers.Battery): Battery instance
        p5min_times (list): given P5MIN times
        p5min_prices (list): given P5MIN prices
        aemo_p5min_prices (list): given AEMO P5MIN prices
        predispatch_times (list): given PREDISPATCH times
        predispatch_prices (list): given PREDISPATCH prices
        aemo_predispatch_prices (list): given AEMO PREDISPATCH prices
        custom_flag (bool): use custom results or AEMO records
        horizon (int): horizon number
        k (int): iteration numbere
        E_initial (float): initial E (charge level)
        method (int): degradation method number (0, 1, or 2)
        band (float): replace price of the first interval by the band price
        fcas_flag (bool): consider FCAS or not
        fcas_type (str): replaced FCAS type
        multi_flag (bool): participate in multiple FCAS markets or not
        der_flag (bool): participate in redesigned NEMDE

    Returns:
        (float, float, float): discharging (positive) / charging (negative) power value, raise FCAS value, lower FCAS value
    """
    tstep = 5 / 60  # Time step (in hour)
    cost = 20  # Operation cost ($/MWh)
    fee = 300000  # Replacement fee ($/MWh) used for battery degradation model
    obj = 0  # Initial objective value
    SOC_MIN = 0.15  # Minimum battery SOC
    SOC_MAX = 0.95  # Maximum battery SOC
    horizon = default.datetime_to_interval(current)[1] - 1 if horizon is None else horizon  # Horizon number
    # Battery initial charge level
    if E_initial is None or horizon == 0:
        E_initial = 0.5 * battery.size
    # Battery degradation model coefficients
    M = 16  # Number of segments
    R = 300000  # Replacement cost ($/MWh)
    if prices is None:
        intervals = None
        if p5min_times is None:
            times, prices, predispatch_time, aemo_prices, fcas_prices, aemo_fcas_prices, raise_fcas_records, lower_fcas_records, extended_times = process_prices_by_interval(current, custom_flag, battery, k, fcas_flag)
        else:
            times, prices, p5min_prices, predispatch_prices, predispatch_time, aemo_prices = process_given_prices_by_interval(current, custom_flag, battery, k, p5min_times, p5min_prices, aemo_p5min_prices, predispatch_times, predispatch_prices, aemo_predispatch_prices)
    else:
        intervals = 60 / 60
    # Cost-reflective bidding strategy: Replace the price of the first interval by corresponding band price
    if band is not None:
        if fcas_type is None:
            prices[0] = band
        else:
            fcas_prices[fcas_type][0] = band
    # Horizon and interval
    remainder = horizon % 6  # Number of intervals at the first PREDISPATCH
    # T1 = 12  # Total number of P5MIN intervals
    T1 = 6
    T = len(prices)  # Total number of intervals
    # Formulate battery operation optimisation problem using gurobi
    with gp.Env() as env, gp.Model(env=env, name=f'operation_{battery.name}_{horizon}{fcas_type}{band}') as model:
        model.setParam("OutputFlag", 0)  # 0 if no log information; otherwise 1
        # Battery variables
        soc = [model.addVar(lb=SOC_MIN, ub=SOC_MAX, name=f'SOC_{j}') for j in range(T)]  # Battery SOC (%)
        E = [soc[j] * battery.size for j in range(T)]  # Battery charge level (MWh)
        pgen = [model.addVar(ub=battery.generator.max_capacity,
                             name=f'energy_pgen_{j}') for j in range(T)]  # Generator / discharging power (MW)
        pload = [model.addVar(ub=battery.load.max_capacity,
                              name=f'energy_pload_{j}') for j in range(T)]  # Load / charging power (MW)
        if fcas_flag:
            raise_fcas = [model.addVar(ub=battery.generator.max_capacity+battery.load.max_capacity,
                                       name=f'raise_{j}') for j in range(T)]  # RAISE FCAS power (MW)
            lower_fcas = [model.addVar(lb=-battery.generator.max_capacity-battery.load.max_capacity, ub=0,
                                       name=f'lower_{j}') for j in range(T)]  # LOWER FCAS power (MW)
        degradation = [model.addVar(name=f'degradation_{j}') for j in range(T)]  # Battery degradation costs
        # Battery constraints
        model.addLConstr(E[0], gp.GRB.EQUAL,
                         E_initial + tstep * (pload[0] * battery.eff - pgen[0] / battery.eff),
                         'TRANSITION_0')  # First transition
        model.addLConstr(E[T - 1], gp.GRB.EQUAL, E_initial, 'FINAL_STATE')  # Final state
        for j in range(T):
            model.addSOS(type=gp.GRB.SOS_TYPE1, vars=[pgen[j], pload[j]])  # Charge or discharge
            if intervals is None:
                # Different length of forecast horizon
                if j == T1:
                    tstep = (6 - remainder) * 5 / 60  # First interval of PREDISPATCH
                # 30min-based
                # elif remainder != 0 and j == T - 1:
                #     tstep = remainder * 5 / 60
                # elif T1 < j:
                elif j == T - 1:
                    tstep = remainder * 5 / 60
                elif T1 < j < T:
                    tstep = 30 / 60
                else:
                    tstep = 5 / 6
            else:
                tstep = intervals
            # Transition between horizons
            if j >= 1:
                model.addLConstr(E[j], gp.GRB.EQUAL,
                                 E[j - 1] + tstep * (pload[j] * battery.eff - pgen[j] / battery.eff), f'TRANSITION_{j}')
                # model.addLConstr(pgen[j] <= pgen[j - 1] + tstep * battery.generator.ramp_up_rate / 60)
                # model.addLConstr(pgen[j] >= pgen[j - 1] - tstep * battery.generator.ramp_down_rate / 60)
                # model.addLConstr(pload[j] <= pload[j - 1] + tstep * battery.load.ramp_up_rate / 60)
                # model.addLConstr(pload[j] >= pload[j - 1] - tstep * battery.load.ramp_up_rate / 60)
            # Objective
            obj += prices[j] * (battery.generator.transmission_loss_factor * pgen[j] -
                                battery.load.transmission_loss_factor * pload[j]) * tstep
            # Method 0: Add operational cost to objective function
            if method == 0:
                obj -= (pgen[j] + pload[j]) * tstep * cost
            # Method 1: Battery degradation model (see paper Ying2016Stochastic)
            elif method == 1:
                alpha = [model.addVar(name=f'alpha_{j}_{k}') for k in range(len(socs))]
                model.addLConstr(soc[j], gp.GRB.EQUAL, sum([s * a for s, a in zip(socs, alpha)]))
                model.addLConstr(degradation[j], gp.GRB.EQUAL, sum([d * a for d, a in zip(degradations, alpha)]))
                model.addLConstr(sum(alpha), gp.GRB.EQUAL, 1)
                model.addSOS(gp.GRB.SOS_TYPE2, alpha)
                # Method (a): Add degradation constraint
                # model.addLConstr(degradation[j] <= 1 / 10 / 365)
                # Method (b): Add degradation cost to objective function
                obj -= fee * degradation[j] * battery.size
            # Method 2: Add factorised aging cost to objective function (Xu2018Factoring)
            elif method == 2:
                pgens = [model.addVar(ub=battery.generator.max_capacity, name=f'pgen_{j}_segment_{m + 1}') for m in range(M)]
                model.addLConstr(pgen[j] == sum(pgens))
                obj -= tstep * sum([pgens[m] * marginal_costs(R, battery.eff, M, m + 1) for m in range(M)])
            # FCAS co-optimisation
            if fcas_flag:
                model.addLConstr(raise_fcas[j] <= raise_fcas_records[j], f'RAISE_RECORD_{j}')  # Max regional RAISE FCAS
                model.addLConstr(lower_fcas[j] >= - lower_fcas_records[j], f'LOWER_RECORD_{j}')  # Max regional LOWER FCAS
                model.addLConstr(pgen[j] - pload[j] + raise_fcas[j] <= battery.generator.max_capacity, f'RAISE_{j}')
                model.addLConstr(pgen[j] - pload[j] + lower_fcas[j] >= - battery.load.max_capacity, f'LOWER_{j}')
                model.addLConstr(E[j] - lower_fcas[j] * tstep * battery.eff <= battery.Emax, f'RAISE_EMAX_{j}')
                model.addLConstr(E[j] - raise_fcas[j] * tstep / battery.eff >= battery.Emin, f'LOWER_EMIN_{j}')
                if multi_flag:
                    obj += raise_fcas[j] * (fcas_prices['RAISE5MIN'][j] + fcas_prices['RAISE6SEC'][j] +
                                            fcas_prices['RAISE60SEC'][j]) * tstep - lower_fcas[j] * (
                                       fcas_prices['LOWER5MIN'][j] + fcas_prices['LOWER60SEC'][j] +
                                       fcas_prices['LOWER6SEC'][j]) * tstep
                else:
                    obj += raise_fcas[j] * fcas_prices['RAISE5MIN'][j] * tstep - lower_fcas[j] * fcas_prices['LOWER5MIN'][j] * tstep
        # Optimise
        model.setObjective(obj, gp.GRB.MAXIMIZE)
        model.optimize()
        if model.status == gp.GRB.Status.INFEASIBLE:
            print('Infeasible Model')
            model.computeIIS()
            print('\nThe following constraint(s) cannot be satisfied:')
            for c in model.getConstrs():
                if c.IISConstr:
                    print(f'Constraint name: {c.constrName}')
                    print(f'Constraint sense: {c.sense}')
                    print(f'Constraint rhs: {c.rhs}')
        elif model.status == gp.GRB.Status.INF_OR_UNBD:
            print('Unbounded Model!')
        # Debug part
        # print(f'E initial: {E_initial}')
        # for i in range(len(E)):
        #     print(f'E{i}: {E[i].getValue()}')
        #     print(f'{pgen[i].x - pload[i].x}')
        #     print(f'soc{i}: {soc[i].x}')
        #     break
        # path_to_model = default.MODEL_DIR / 'check.lp'
        # path_to_model = battery.bat_dir / f'{default.get_case_datetime(current)}.lp'
        # model.write(str(path_to_model))
        # Write results
        # if fcas_flag:
        #     write.write_forecasts(current, soc, times, prices, pgen, pload, predispatch_time, T1, T,
        #                           battery.bat_dir, k, band, raise_fcas, lower_fcas, fcas_type)
        # else:
        #     write.write_forecasts(current, soc, times, prices, pgen, pload, predispatch_time, T1, T, battery.bat_dir, k, band)
        # # return write.write_forecasts(current, soc, times, prices, pgen, pload, predispatch_time, T1, T2, battery.bat_dir, k, band), E[0].getValue()
        # Plot results
        # import plot
        # if band is None:
        #     path_to_fig = battery.bat_dir / ('forecast' if k == 0 else f'forecast_{k}') / f'{default.get_case_datetime(current)}.jpg'
        # else:
        #   path_to_fig = battery.bat_dir / ('forecast' if k == 0 else f'forecast_{k}') / f'{default.get_case_datetime(current)}_{fcas_type}_{band}.jpg'
        # plot.plot_soc(times, prices, [soc[j].x * 100 for j in range(T)], path_to_fig)
        # path_to_fig = battery.bat_dir / 'forecast' / f'ENERGY_{default.get_case_datetime(current)}.jpg'
        # plot.plot_power(times, prices, [p.x - l.x for p, l in zip(pgen, pload)], 'ENERGY', path_to_fig)
        # path_to_fig = battery.bat_dir / 'forecast' / f'RAISE5MIN_{default.get_case_datetime(current)}.jpg'
        # plot.plot_power(times, fcas_prices['RAISE5MIN'], [f.x for f in raise_fcas], 'RAISE5MIN', path_to_fig)
        # path_to_fig = battery.bat_dir / 'forecast' / f'LOWER5MIN_{default.get_case_datetime(current)}.jpg'
        # plot.plot_power(times, fcas_prices['LOWER5MIN'], [f.x for f in lower_fcas], 'LOWER5MIN', path_to_fig)
        if der_flag:
            write.write_schedule(times, pgen, pload, battery.bat_dir)
            return times, [[pgen[j].x, pload[j].x] for j in range(T)], extended_times
        elif fcas_flag:
            return pgen[0].x - pload[0].x, raise_fcas[0].x, lower_fcas[0].x
        return pgen[0].x - pload[0].x
        # return None, pgen[0].x - pload[0].x, None


if __name__ == '__main__':
    from helpers import Battery
    import datetime
    b = Battery(30, 20, usage='DER Price-taker TT')
    current = datetime.datetime(2021, 9, 12, 4, 5)
    schedule(current, b)