#!/usr/bin/env python3

import pandas as pd
import default

infile = default.OUT_DIR / 'all_units_tiebreak.csv'

# Read in data
df: pd.DataFrame = pd.read_csv(infile).transpose() # Read in CSV and transpose so columns are time series.
df.columns = pd.MultiIndex.from_arrays((df.loc['ID'], df.loc['Battery'])) # Change to multi-index on columns.
df = df.iloc[2:, :] # Drop duplicated row headings.
df.index = pd.to_datetime(df.index, format='%Y-%m-%d %H:%M:%S') # Convert to datetimes.
df.sort_index(inplace=True) # Make sure sorted by datetime.
df_batt1 = df.xs('batt1', axis=1, level=1) # Separate dataframe for batt1
df_batt2 = df.xs('batt2', axis=1, level=1) # Separate dataframe for batt2

# Analyse differences between the two cases
diff = df_batt1 - df_batt2 # Difference in unit dispatch batt1 and batt2

# Select timesteps where the total dispatch is different for batt1 and batt2 
sel_different = abs(diff.sum(axis=1)) >= 1e-3
different = diff[sel_different]

for time, row in different.iterrows():
    row_nz = row[row != 0]
    print(f'{time}: {sum(row)}')
    for uid, d in row_nz.iteritems():
        print(f'    {uid}, {d}')
