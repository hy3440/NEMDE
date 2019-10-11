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

x_min = -2000
x_max = 2000
x_s = range(x_min, x_max+1)
# y_s = [(-0.0471 + 1.0044E-05 * qd - 3.5146E-07 * nd) * x_i + 9.8083E-05 * (x_i ** 2) for x_i in x_s]
y_s = [(0.0657 - 3.1523E-05 * vd + 2.1734E-05 * nd - 6.5967E-05 * sd) * x_i + 8.5133E-05 * (x_i ** 2) for x_i in x_s]
lambda_s = [model.addVar(lb=0.0) for i in x_s]

x = model.addVar(lb=-gurobipy.GRB.INFINITY)
model.addConstr(x == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))

y = model.addVar(lb=-gurobipy.GRB.INFINITY)
model.addConstr(y == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))

model.addConstr(sum(lambda_s) == 1)
model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)

model.addConstr(x == 806)
model.setObjective(1)

model.optimize()
print('!!!: {}'.format(model.isQP))
print(len(x_s))
print(x.x)
print(y.x)
