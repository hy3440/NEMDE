from gurobipy import *

with Env() as env, Model(env=env, name='Test0') as m:
    G0 = m.addVar(lb=0, ub=200, name='G0')
    G1 = m.addVar(lb=0, ub=200, name='G1')
    B0 = m.addVar(lb=0, ub=200, name='B0')
    B1 = m.addVar(lb=0, ub=200, name='B1')

    D0 = 300
    D1 = 100
    balance_constr0 = m.addLConstr(G0 + B0, GRB.EQUAL, D0)
    balance_constr1 = m.addLConstr(G1 + B1, GRB.EQUAL, D1)
    m.addConstr(G1 <= G0 + 10)
    objective = G0 * 100 + G1 * 5 + B0 * 10 + B1 * 20
    m.setObjective(objective, GRB.MINIMIZE)
    m.optimize()

    print(f'D1 = {D1} and dual value is {balance_constr0.pi}')
    print(G0, G1, B0, B1)

with Env() as env, Model(env=env, name='Test1') as m:
    G0 = m.addVar(lb=0, ub=200, name='G0')
    G1 = m.addVar(lb=0, ub=200, name='G1')
    B0 = m.addVar(lb=0, ub=200, name='B0')
    B1 = m.addVar(lb=0, ub=200, name='B1')

    D0 = 300
    D1 = 200
    balance_constr0 = m.addLConstr(G0 + B0, GRB.EQUAL, D0)
    balance_constr1 = m.addLConstr(G1 + B1, GRB.EQUAL, D1)
    m.addConstr(G1 <= G0 + 10)
    objective = G0 * 100 + G1 * 5 + B0 * 10 + B1 * 20
    m.setObjective(objective, GRB.MINIMIZE)
    m.optimize()

    print(f'D1 = {D1} and dual value is {balance_constr0.pi}')
    print(G0, G1, B0, B1)
