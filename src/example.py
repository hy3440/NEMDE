from gurobipy import *

# create a new model
# m = Model("mip1")
with Env() as env, Model(env=env, name='Integration') as m:

    # create variables
    pg0 = m.addVar(name="pg0")
    ph0 = m.addVar(name="ph0")
    pg1 = m.addVar(name="pg1")
    ph1 = m.addVar(name="ph1")

    m.update()
    for var in [pg0, ph0, pg1, ph1]:
        m.addLConstr(var >= 0, name=f'LB_{var.varName}')
        m.addLConstr(var <= 8, name=f'UB_{var.varName}')

    d0 = 10.1
    balance_constr1 = m.addLConstr(pg0 + ph0, GRB.EQUAL, d0, name='BALANCE_1')
    balance_constr2 = m.addLConstr(pg1 + ph1, GRB.EQUAL, 10, name='BALANCE_2')
    m.addConstr(pg1 - pg0 <= 1, name='RAMP_UP_PG')
    objective = pg0 * 10 + ph0 * 1 + pg1 * 1 + ph1 * 100
    m.setObjective(objective, GRB.MINIMIZE)
    m.optimize()

    for constr in m.getConstrs():
        print(f'Dual {constr.constrName}: {constr.pi}')