import gurobipy
from helpers import Battery
import default
import datetime
import pandas as pd
import numpy as np

# start = datetime.datetime(2020, 9, 1, 4, 30)
start = datetime.datetime(2021, 7, 18, 4, 30)
e = 30
battery = Battery(e, int(e * 2 / 3), usage='DER None Bilevel Test Hour every 1st')
path_to_model = battery.bat_dir / f'DER_{e}MWh_{default.get_case_datetime(start)}-copy.lp'

if not path_to_model.is_file():
    path_to_original = battery.bat_dir / f'DER_{e}MWh_{default.get_case_datetime(start)}.lp'
    with path_to_model.open('w') as wf:
        with path_to_original.open() as f:
            for l in f.readlines():
                wf.write(l.replace('_extension_', '_predispatch_'))

model = gurobipy.read(str(path_to_model))
process = 'dispatch'
problem_id = f'{process}_{default.get_case_datetime(start)}'
model.optimize()
print(model.IsMIP == 0)

# constr = model.getConstrByName(f'REGION_BALANCE_NSW1_{problem_id}')
# print(constr.pi)
#
# for constr in model.getConstrs():
#     if 'REGION_BALANCE_NSW1' in constr.constrName:
#         print(constr.constrName, constr.pi)

for var in model.getVars():
    # if 'Total_Cleared' in var.varName:
    #     print(var.varName, var.x)
    if 'Dual_REGION_BALANCE_NSW1' in var.varName:
        print(var.varName, var.x)
