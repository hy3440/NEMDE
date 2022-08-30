import gurobipy
from helpers import Battery
import default
import datetime
import pandas as pd
import numpy as np

# start = datetime.datetime(2020, 9, 1, 4, 30)
# # start = datetime.datetime(2020, 9, 1, 4, 5)
# e = 0
# battery = Battery(e, int(e * 2 / 3), usage='DER None Integration Test Perfect every 1st')
# path_to_model = battery.bat_dir / f'DER_{e}MWh_{default.get_case_datetime(start)}-copy.lp'
#
# if not path_to_model.is_file():
#     path_to_original = battery.bat_dir / f'DER_{e}MWh_{default.get_case_datetime(start)}.lp'
#     with path_to_model.open('w') as wf:
#         with path_to_original.open() as f:
#             for l in f.readlines():
#                 wf.write(l.replace('_extension_', '_predispatch_'))

# model = gurobipy.read(str(path_to_model))
# process = 'dispatch'
# problem_id = f'{process}_{default.get_case_datetime(start)}'
# model.optimize()
# print(model.IsMIP == 0)

# constr = model.getConstrByName(f'REGION_BALANCE_NSW1_{problem_id}')
# print(constr.pi)

# for constr in model.getConstrs():
#     if 'REGION_BALANCE_NSW1' in constr.constrName:
#         print(constr.constrName, constr.pi)

# for var in model.getVars():
#     if 'Total_Cleared' in var.varName:
#         print(var.varName, var.x)

i = 189
t = datetime.datetime(2020, 9, 1, 4, 5) + i * default.FIVE_MIN
case_date = default.get_case_date(t)
path_to_file1 = default.DATA_DIR / case_date / f'PUBLIC_NEXT_DAY_DISPATCH_{case_date}.csv'
df1 = pd.read_csv(path_to_file1, skiprows=1)
interval = int(f'{t.year}{t.month:02d}{t.day:02d}{(i + 1):03d}')
df1 = df1.loc[df1['DISPATCHINTERVAL'] == interval]

dt = t.strftime('%Y%m%d%H%M')
path_to_file2 = default.DATA_DIR / case_date / f'PUBLIC_DVD_DISPATCHLOAD_{dt}.csv'
df2 = pd.read_csv(path_to_file2)

# for duid in df2['DUID'].astype(str):
#     if df1.loc[df1['DUID'] == duid]['INITIALMW'] != df2.loc[df2['DUID'] == duid]['INITIALMW']:
#         print(duid)
df1['prices_match'] = np.where(df1['INITIALMW'] == df2['INITIALMW'], 'True', 'False')
print(df1.loc[df1['prices_match'] == False])