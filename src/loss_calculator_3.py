import datetime
import interconnect
import gurobipy


t = datetime.datetime(2019, 7, 19, 4, 10, 0)
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
k_s = [8.5133E-05 * 2 * x_i + (0.0657 - 3.1523E-05 * vd + 2.1734E-05 * nd - 6.5967E-05 * sd) for x_i in x_s]

x = model.addVar(lb=x_min, ub=x_max)
y = model.addVar(lb=-gurobipy.GRB.INFINITY)
model.addConstr(x == interconnectors['VIC1-NSW1'].mw_flow_record)
# est = [k_s[i] * (x - x_s[i]) + y_s[i] for i in range(len(x_s))]
for i in range(len(x_s)):
    model.addConstr(y >= k_s[i] * (x - x_s[i]) + y_s[i])
# for i in range(len(x_s) - 1):
#     model.addConstr(y <= (y_s[i+1] - y_s[i]) * (x - x_s[i]) / (x_s[i+1] - x_s[i]) + y_s[i+1])
# model.setObjective(y, gurobipy.GRB.MINIMIZE)
model.setObjective(0)
model.optimize()
# print('!!!: {}'.format(model.isLP))
print(x.x)
print(y.x)
print(interconnectors['VIC1-NSW1'].mw_losses_record)
