import datetime
import interconnect
import numpy as np
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
x_s = np.arange(x_min, x_max, 0.1)
# y_s = [(-0.0468 + 3.5206E-06 * nd + 5.3555E-06 * qd) * x_i + 9.5859E-05 * (x_i ** 2) for x_i in x_s]
y_s = [(0.0657 - 3.1523E-05 * vd + 2.1734E-05 * nd - 6.5967E-05 * sd) * x_i + 8.5133E-05 * (x_i ** 2) for x_i in x_s]
lambda_s = [model.addVar(lb=0.0) for i in x_s]

x = model.addVar(lb=-gurobipy.GRB.INFINITY)
model.addConstr(x == sum([x_i * lambda_i for x_i, lambda_i in zip(x_s, lambda_s)]))

y = model.addVar(lb=-gurobipy.GRB.INFINITY)
model.addConstr(y == sum([y_i * lambda_i for y_i, lambda_i in zip(y_s, lambda_s)]))

model.addConstr(sum(lambda_s) == 1)
model.addSOS(gurobipy.GRB.SOS_TYPE2, lambda_s)

model.addConstr(x == interconnectors['VIC1-NSW1'].mw_flow_record)
model.setObjective(1)

model.optimize()
print(len(x_s))
print(x.x)
print(y.x)
print("Flow record: {}".format(interconnectors['VIC1-NSW1'].mw_flow_record))
print(interconnectors['VIC1-NSW1'].mw_losses_record)
