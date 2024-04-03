# # maximize
# #       x +    y + 2 z
# # subject to
# #       x + 2  y + 3 z <= 4
# #       x +    y       >= 1
# #       x,  y, z binary
#
# from gurobipy import *
# import default
# from multiprocessing.pool import ThreadPool as Pool
# from itertools import repeat
#
# try:
#
#     # create a new model
#     # m = Model("mip1")
#     with Env() as env, Model(env=env, name='Integration') as m:
#
#         # create variables
#         x = m.addVar(name="x")
#         y = m.addVar(name="y")
#         z = m.addVar(name="z")
#
#         # set objective
#         m.setObjective(x + y + 2 * z, GRB.MAXIMIZE)
#
#         # add constraint: x + 2 y + 3 z <= 4
#         m.addLConstr(-(x + 2 * y + 3 * z) >= -4, "c0")
#
#         m.addLConstr(x == 4, 'linear')
#         # m.addQConstr(x * x == 16, 'quadratic')
#         # m.setParam(GRB.Param.QCPDual, 1)
#
#         # optimize model
#         m.optimize()
#
#         for v in m.getVars():
#             print(f'{v.varName} {v.x:g}')
#
#         for c in m.getConstrs():
#             # if c.slack != 0:
#             print(c.slack)
#             print(c.constrName)
#             print(c.pi)
#
#         for c in m.getQConstrs():
#             # print(c.slack)
#             print(c.QCName)
#             print(c.qcpi)
#
#         print(f'Obj: {m.objVal:g}')
#
#
# except GurobiError as e:
#     print('Error code ' + str(e.errno) + ": " + str(e))
#
# # except AttributeError:
# #     print('Encountered an attribute error')
#

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

def plot_data(x, y):
    plt.plot(x, y)
    plt.xlabel('X-axis')
    plt.ylabel('Y-axis')
    plt.title('Plot with Scientific Notation on Y-axis')

    # Set the y-axis formatter to scientific notation
    formatter = ticker.ScalarFormatter(useMathText=True)
    formatter.set_powerlimits((-3, 3))  # Adjust the power limits as needed
    plt.gca().yaxis.set_major_formatter(formatter)

    plt.show()

# Example data
x = [1, 2, 3, 4, 5]
y = [1000000, 2000000, 3000000, 4000000, 5000000]

# Call the function to plot the data
plot_data(x, y)
