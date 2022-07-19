# Compare DispatchLoad results with bids from two different capacities of batteries.

import datetime
import default
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reflect import generate_batteries

# Current interval
current = datetime.datetime(2021, 9, 12, 18, 10, 0)

# Battery MW capacity
mw_batt = 10
mw_nobatt = 0

# Input filenames.
# fn_batt = default.OUT_DIR / 'single' / f'{mw_batt}' / 'dispatch' / f'dispatchload_{default.get_case_datetime(current + default.FIVE_MIN)}.csv'
# fn_nobatt = default.OUT_DIR / 'single' / f'{mw_nobatt}' / 'dispatch' / f'dispatchload_{default.get_case_datetime(current + default.FIVE_MIN)}.csv'
energies = [0.03, 0.06]
usage = 'Cost-reflective + multiple FCAS'
batteries = generate_batteries(energies, usage)
# fn_batt1 = default.OUT_DIR / batteries[0].bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(current + default.FIVE_MIN)}.csv'
# fn_batt2 = default.OUT_DIR / batteries[1].bat_dir / 'dispatch' / f'dispatchload_{default.get_case_datetime(current + default.FIVE_MIN)}.csv'
# fn_nobatt = default.OUT_DIR / 'record' / 'dispatch' / f'dispatchload_{default.get_case_datetime(current + default.FIVE_MIN)}.csv'
fn_batt1 = default.DEBUG_DIR / 'dispatch' / f'dispatchload_{default.get_case_datetime(current + default.FIVE_MIN)}-batt1.csv'
fn_batt2 = default.DEBUG_DIR / 'dispatch' / f'dispatchload_{default.get_case_datetime(current + default.FIVE_MIN)}-batt2.csv'
fn_nobatt = default.OUT_DIR / 'sequence' / 'dispatch' / f'dispatchload_{default.get_case_datetime(current + default.FIVE_MIN)}.csv'
fn_units = default.DATA_DIR / 'dvd' / 'DVD_DUDETAILSUMMARY_202109010000.csv'

# Parse input files into Pandas dataframes.
df_batt1 = pd.read_csv(fn_batt1, sep=',')
df_batt2 = pd.read_csv(fn_batt2, sep=',')
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
df_batt1 = df_batt1.set_index('DUID')
df_batt2 = df_batt2.set_index('DUID')
df_nobatt = df_nobatt.set_index('DUID')
df_units = df_units.set_index('DUID')

# Add the battery (gen) to all data, with zero dispatch, so they match.
df_nobatt = df_nobatt.append(pd.Series(0, index=df_nobatt.columns, name='G'))
df_nobatt = df_nobatt.append(pd.Series(0, index=df_nobatt.columns, name='L'))

df_units = df_units.append(pd.Series(0, index=df_units.columns, name='G'))
df_units.loc['G', 'DISPATCHTYPE'] = 'GENERATOR'
df_units.loc['G', 'REGIONID'] = 'NSW1'
df_units = df_units.append(pd.Series(0, index=df_units.columns, name='L'))
df_units.loc['L', 'DISPATCHTYPE'] = 'LOAD'
df_units.loc['L', 'REGIONID'] = 'NSW1'

# Get an index of all generators and loads.
gens = df_units[df_units.loc[:, 'DISPATCHTYPE'] == 'GENERATOR'].index.intersection(df_batt1.index)
loads = df_units[df_units.loc[:, 'DISPATCHTYPE'] == 'LOAD'].index.intersection(df_batt1.index)

# Multiply the dispatch of loads by -1 so we have a consistent convention.
df_batt1.loc[loads, 'TOTALCLEARED'] *= -1
df_batt2.loc[loads, 'TOTALCLEARED'] *= -1
df_nobatt.loc[loads, 'TOTALCLEARED'] *= -1

# Find the total dispatch.
total_nobatt = sum(df_nobatt.loc[:, "TOTALCLEARED"])
total_batt1 = sum(df_batt1.loc[:, "TOTALCLEARED"])
total_batt2 = sum(df_batt2.loc[:, "TOTALCLEARED"])
# delta_total = total_batt - total_nobatt
print(f'Total (without battery)       = {total_nobatt}')
print(f'Total (with battery 1)          = {total_batt1}')
print(f'Total (with battery 2)          = {total_batt2}\n')
# print(f'Change (battery - no battery) = {delta_total}\n')

# Total generation
gens_nobatt = sum(df_nobatt.loc[gens, "TOTALCLEARED"])
gens_batt1 = sum(df_batt1.loc[gens, "TOTALCLEARED"])
gens_batt2 = sum(df_batt2.loc[gens, "TOTALCLEARED"])
print(f'Total generation (no batt)   = {gens_nobatt}')
print(f'Total generation (with batt 1) = {gens_batt1}')
print(f'Total generation (with batt 2) = {gens_batt2}\n')


# Total loads
loads_nobatt = sum(df_nobatt.loc[loads, "TOTALCLEARED"])
loads_batt1 = sum(df_batt1.loc[loads, "TOTALCLEARED"])
loads_batt2 = sum(df_batt2.loc[loads, "TOTALCLEARED"])
print(f'Total loads (no batt)   = {loads_nobatt}')
print(f'Total loads (with batt 1) = {loads_batt1}')
print(f'Total loads (with batt 2) = {loads_batt2}\n')


# Different regions
for region_id in ['NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']:
    region = df_units[df_units.loc[:, 'REGIONID'] == region_id].index.intersection(df_batt1.index)
    region_nobatt = sum(df_nobatt.loc[region, "TOTALCLEARED"])
    region_batt1 = sum(df_batt1.loc[region, "TOTALCLEARED"])
    region_batt2 = sum(df_batt2.loc[region, "TOTALCLEARED"])
    print(f'{region_id} (no batt)   = {region_nobatt}')
    print(f'{region_id} (with batt 1) = {region_batt1}')
    print(f'{region_id} (with batt 2) = {region_batt2}\n')


# # Plot.
# delta = df_batt.loc[:, 'TOTALCLEARED'] - df_nobatt.loc[:, 'TOTALCLEARED']
# delta_nz = delta[delta != 0]
# plt.bar(delta_nz.index, delta_nz)
# plt.show()
