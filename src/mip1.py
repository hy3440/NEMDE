# maximize
#       x +    y + 2 z
# subject to
#       x + 2  y + 3 z <= 4
#       x +    y       >= 1
#       x,  y, z binary

from gurobipy import *
import default
from multiprocessing.pool import ThreadPool as Pool
from itertools import repeat


def test(m, x, y):
    # add constraint: x + y >= 1
    l = [x, y]
    m.addLConstr(sum(l) >= 1, "c1")


def roll(v, model, c):
    model.addLConstr(v <= c, f"{c}")
    return 1, 2, 3

try:

    # create a new model
    # m = Model("mip1")
    with Env() as env, Model(env=env, name='Integration') as m:

        # create variables
        x = m.addVar(vtype=GRB.BINARY, name="x")
        y = m.addVar(vtype=GRB.BINARY, name="y")
        z = m.addVar(vtype=GRB.BINARY, name="z")

        # set objective
        m.setObjective(x + y + 2 * z, GRB.MAXIMIZE)

        # add constraint: x + 2 y + 3 z <= 4
        m.addLConstr(x + 2 * y + 3 * z <= 4, "c0")

        test(m, x, y)

        constants = [1, 2]
        with Pool(len(constants)) as pool:
            t = pool.starmap(roll, zip(repeat(x), repeat(m), constants))
        print(t)

        path_to_model = default.MODEL_DIR / f'mip1.lp'
        m.write(str(path_to_model))

        # optimize model
        m.optimize()

        for v in m.getVars():
            print(f'{v.varName} {v.x:g}')

        for c in m.getConstrs():
            # if c.slack != 0:
            print(c.slack)
            print(c.constrName)

        print(f'Obj: {m.objVal:g}')

        a = m.getVarByName('tt')
        print(a == 0)

except GurobiError as e:
    print('Error code ' + str(e.errno) + ": " + str(e))

except AttributeError:
    print('Encountered an attribute error')
