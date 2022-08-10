import gurobipy
from helpers import Battery
import default
import datetime

# start = datetime.datetime(2020, 9, 1, 10, 55)
start = datetime.datetime(2020, 9, 1, 4, 5)
battery = Battery(30, 20, usage='DER None temp')
path_to_model = battery.bat_dir / f'DER_30MWh_{default.get_case_datetime(start)}-copy.mip'

if not path_to_model.is_file():
    path_to_original = battery.bat_dir / f'DER_30MWh_{default.get_case_datetime(start)}.lp'
    with path_to_model.open('w') as wf:
        with path_to_original.open() as f:
            for l in f.readlines():
                wf.write(l.replace('^', ''))

model = gurobipy.read(str(path_to_model))
process = 'dispatch'
problem_id = f'{process}_{default.get_case_datetime(start)}'
model.optimize()

# constr = model.getConstrByName(f'REGION_BALANCE_NSW1_{problem_id}')
# print(constr.pi)

for constr in model.getConstrs():
    if 'REGION_BALANCE_NSW1' in constr.constrName:
        print(constr.constrName, constr.pi)

print('test')