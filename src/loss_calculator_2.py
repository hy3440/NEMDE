import datetime
import interconnect
# import numpy as np
import gurobipy

t = datetime.datetime(2019, 7, 7, 4, 5, 0)
regions, interconnectors, obj_record = interconnect.get_regions_and_interconnectors(t)
qd = regions['QLD1'].total_demand
vd = regions['VIC1'].total_demand
nd = regions['NSW1'].total_demand
sd = regions['SA1'].total_demand

model = gurobipy.Model('temp')

MIN = -2000
MAX = 2000
# y_s = [(-0.0471 + 1.0044E-05 * qd - 3.5146E-07 * nd) * x_i + 9.8083E-05 * (x_i ** 2) for x_i in x_s]
# y_s = [(0.0657 - 3.1523E-05 * vd + 2.1734E-05 * nd - 6.5967E-05 * sd) * x_i + 8.5133E-05 * (x_i ** 2) for x_i in x_s]

mw_flow = model.addVar(lb=-gurobipy.GRB.INFINITY)
mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)

flow = 0
losses = 0
for i in range(0, MAX):
    j = model.addVar(lb=0, ub=1, name='{}'.format(i))
    flow += j
    y_1 = (0.0657 - 3.1523E-05 * vd + 2.1734E-05 * nd - 6.5967E-05 * sd) * i + 8.5133E-05 * (i ** 2)
    y_2 = (0.0657 - 3.1523E-05 * vd + 2.1734E-05 * nd - 6.5967E-05 * sd) * (i + 1) + 8.5133E-05 * ((i + 1) ** 2)
    if y_1 > y_2:
        print('!!!!!!!!!!!!!!')
    losses += j * (y_2 - y_1)

model.addConstr(mw_flow == flow)
model.addConstr(mw_losses == losses)

model.addConstr(mw_flow == interconnectors['VIC1-NSW1'].mw_flow_record)
model.setObjective(1)

model.optimize()
# print('!!!: {}'.format(model.isMIP))
print('Our flow: {}'.format(mw_flow.x))
print('Our loss: {}'.format(mw_losses.x))
print('AEMO flow: {}'.format(interconnectors['VIC1-NSW1'].mw_flow_record))
print('AEMO loss: {}'.format(interconnectors['VIC1-NSW1'].mw_losses_record))
print((0.0657 - 3.1523E-05 * vd + 2.1734E-05 * nd - 6.5967E-05 * sd) * mw_flow.x + 8.5133E-05 * (mw_flow.x ** 2))
for var in model.getVars():
    print('{}: {}'.format(var.varName, var.x))


