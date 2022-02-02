# Compare DispatchLoad results with bids from two different capacities of batteries.

import datetime
import default
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Current interval
current = datetime.datetime(2020, 9, 1, 4, 5, 0)

# Battery MW capacity
mw_batt = 10
mw_nobatt = 0

# Input filenames.
fn_batt = default.OUT_DIR / 'single' / f'{mw_batt}' / 'dispatch' / f'dispatchload_{default.get_case_datetime(current + default.FIVE_MIN)}.csv'
fn_nobatt = default.OUT_DIR / 'single' / f'{mw_nobatt}' / 'dispatch' / f'dispatchload_{default.get_case_datetime(current + default.FIVE_MIN)}.csv'
fn_units = default.DATA_DIR / 'dvd' / 'DVD_DUDETAILSUMMARY_202009010000.csv'

# Parse input files into Pandas dataframes.
df_batt = pd.read_csv(fn_batt, sep=',')
df_nobatt = pd.read_csv(fn_nobatt, sep=',')
df_units = pd.read_csv(fn_units, sep=',', skiprows=1)

# Take only the most up to date records in the units data.
df_units = df_units[df_units.iloc[:, 0] != 'C']
df_units = df_units[
    df_units.groupby(['DUID'])['START_DATE'].transform(max) == df_units['START_DATE']
]
# df_units = df_units[
#     df_units.groupby(['DUID'])['VERSIONNO'].transform(max) == df_units['VERSIONNO']
# ]

# Index the dataframes by DUID.
df_batt = df_batt.set_index('DUID')
df_nobatt = df_nobatt.set_index('DUID')
df_units = df_units.set_index('DUID')

# Add the battery (gen) to all data, with zero dispatch, so they match.
df_nobatt = df_nobatt.append(pd.Series(0, index=df_nobatt.columns, name='G'))
df_units = df_units.append(pd.Series(0, index=df_units.columns, name='G'))
df_units.loc['G', 'DISPATCHTYPE'] = 'GENERATOR'
df_units.loc['G', 'REGIONID'] = 'NSW1'

# Get an index of all generators and loads.
gens = df_units[df_units.loc[:, 'DISPATCHTYPE'] == 'GENERATOR'].index.intersection(df_batt.index)
loads = df_units[df_units.loc[:, 'DISPATCHTYPE'] == 'LOAD'].index.intersection(df_batt.index)

# Multiply the dispatch of loads by -1 so we have a consistent convention.
df_batt.loc[loads, 'TOTALCLEARED'] *= -1
df_nobatt.loc[loads, 'TOTALCLEARED'] *= -1

# Find the total dispatch.
total_nobatt = sum(df_nobatt.loc[:, "TOTALCLEARED"])
total_batt = sum(df_batt.loc[:, "TOTALCLEARED"])
delta_total = total_batt - total_nobatt
print(f'Total (without battery)       = {total_batt}')
print(f'Total (with battery)          = {total_nobatt}')
print(f'Change (battery - no battery) = {delta_total}\n')

# Total generation
gens_nobatt = sum(df_nobatt.loc[gens, "TOTALCLEARED"])
gens_batt = sum(df_batt.loc[gens, "TOTALCLEARED"])
print(f'Total generation (no batt)   = {gens_nobatt}')
print(f'Total generation (with batt) = {gens_batt}\n')

# Total loads
loads_nobatt = sum(df_nobatt.loc[loads, "TOTALCLEARED"])
loads_batt = sum(df_batt.loc[loads, "TOTALCLEARED"])
print(f'Total loads (no batt)   = {loads_nobatt}')
print(f'Total loads (with batt) = {loads_batt}\n')

# Different regions
for region_id in ['NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']:
    region = df_units[df_units.loc[:, 'REGIONID'] == region_id].index.intersection(df_batt.index)
    region_nobatt = sum(df_nobatt.loc[region, "TOTALCLEARED"])
    region_batt = sum(df_batt.loc[region, "TOTALCLEARED"])
    print(f'{region_id} (no batt)   = {region_nobatt}')
    print(f'{region_id} (with batt) = {region_batt}\n')

# Plot.
delta = df_batt.loc[:, 'TOTALCLEARED'] - df_nobatt.loc[:, 'TOTALCLEARED']
delta_nz = delta[delta != 0]
plt.bar(delta_nz.index, delta_nz)
plt.show()
