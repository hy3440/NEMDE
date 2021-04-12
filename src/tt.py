import gurobipy


def get_cycles(dod):
    return 1591.1 * pow(dod, -2.089)


def get_degradations(x):
    return 1 / get_cycles(1 - x)

# dods = [20, 40, 60, 80, 100]
# cycles = [34957, 19985, 10019, 3221, 2600]
dods = range(5, 100, 5)
cycles = [get_cycles(d / 100) for d in dods]
print(cycles)
# socs = [80, 60, 20, 0]
# degradations = [1 / 34957, 1 / 19985, 1 / 10019, 1 / 3221, 1 / 2600]
socs = [k / 100 for k in range(0, 100, 10)]
degradations = [get_degradations(s) for s in socs]
print(degradations)
model = gurobipy.Model(f'TEST')
soc = model.addVar(ub=1)
degradation = model.addVar()
cycle = model.addVar()
for j in range(1):
    alpha = [model.addVar(name=f'alpha_{j}_{k}') for k in range(len(socs))]
    beta = [model.addVar(name=f'beta_{j}_{k}') for k in range(len(socs))]
    degradation = model.addVar(name=f'degradation_{j}')
    # model.addConstr(100 * soc, gurobipy.GRB.EQUAL, sum([s * a for s, a in zip(socs, alpha)]))
    # model.addConstr(degradation, gurobipy.GRB.EQUAL, sum([d * a for d, a in zip(degradations, alpha)]))
    model.addConstr((1 - soc) * 100, gurobipy.GRB.EQUAL, sum([dod * a for dod, a in zip(dods, alpha)]))
    model.addConstr(cycle, gurobipy.GRB.EQUAL, sum([c * a for c, a in zip(cycles, alpha)]))
    model.addConstr(sum(alpha), gurobipy.GRB.EQUAL, 1)
    model.addSOS(gurobipy.GRB.SOS_TYPE2, alpha)
    model.addConstr(soc == 0.8)
    # model.setObjective(obj, gurobipy.GRB.MAXIMIZE)
    model.optimize()
    print(degradation)
    # print(cycle)