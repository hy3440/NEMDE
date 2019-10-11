import gurobipy

x_s = range(1, 1000, 10)
y_s = [1 / i for i in x_s]

model = gurobipy.Model('LossCalculator')
# model.setParam('OutputFlag', 0)
x = model.addVar(name='x', ub=10)
y = model.addVar(name='y', ub=15)
# for i in range(len(x_s) - 1):
#     model.addConstr((y - y_s[i]) * (x_s[i + 1] - x_s[i]) <= (y_s[i + 1] - y_s[i]) * (x - x_s[i]))
model.addConstr(x + y == 12)
model.setObjective(3 * x + 5 * y, gurobipy.GRB.MINIMIZE)
model.optimize()
print(x)
print(y)
print(model.pi)

