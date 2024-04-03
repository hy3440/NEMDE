import pandas as pd
import preprocess


def pre(item):
    if pd.isnull(item):
        return ' '
    else:
        return str(item)


def extract_registration_information():
    """ Add registration information.

    Args:
        units (dict): The dictionary of un      its

    Returns:
        None
    """
    generators_file = preprocess.download_registration(False)
    with pd.ExcelFile(generators_file) as xls:
        df = pd.read_excel(xls, 'ExistingGeneration&NewDevs', skiprows=[0])
        for index, row in df.iterrows():
            if row['Region'] == 'TAS1' and (row['FuelBucketSummary'] == 'Solar' or row['FuelBucketSummary'] == 'Battery Storage'):
                print(row['Site Name'] + ' & ' + pre(row['DUID']) + ' & ' + row['Asset Type'] + ' & ' + pre(row['Nameplate Capacity (MW)']) + ' & ' + pre(row['Storage Capacity (MWh)']) + ' & ' + row['FuelBucketSummary'] + ' \\\\')
                # print(pre(row['DUID']))


if __name__ == '__main__':
    extract_registration_information()