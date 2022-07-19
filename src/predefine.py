import csv
import preprocess
import default


def simplify_dudetailsummary(t, out_file):
    all_units = {}
    dds_dir = preprocess.download_dvd_data('DUDETAILSUMMARY', t)
    with dds_dir.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and default.extract_datetime(row[5]) <= t < default.extract_datetime(row[6]):
                duid = row[4]
                all_units[duid] = (row[9], float(row[13]))
                # unit.region_id = row[9]
                # unit.transmission_loss_factor = float(row[13])
    # out_file = default.DATA_DIR / 'predefined' / f'DUDETAILSUMMARY_{t.year}{t.month:02d}01.csv'
    with out_file.open('w') as wf:
        writer = csv.writer(wf)
        writer.writerow(['I', 'DUID', 'REGION ID', 'TRANSMISSION LOSS FACTOR'])
        for duid, value in all_units.items():
            writer.writerow(['D', duid, value[0], value[1]])


def add_simplified_dudetailsummary(units, t):
    in_file = default.DATA_DIR / 'predefined' / f'DUDETAILSUMMARY_{t.year}{t.month:02d}01.csv'
    if not in_file.is_file():
        simplify_dudetailsummary(t, in_file)
    with in_file.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                unit = units.get(row[1])
                if unit:
                    unit.region_id = row[2]
                    unit.transmission_loss_factor = float(row[3])


def add_simplified_interconnector_constraint(interconnectors, t):
    out_file = default.DATA_DIR / 'predefined' / f'INTERCONNECTORCONSTRAINT_{t.year}{t.month:02d}01.csv'
    if not out_file.is_file():
        ic_dir = preprocess.download_dvd_data('INTERCONNECTORCONSTRAINT', t)
        rows = {}
        with ic_dir.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == 'I':
                    rows['I'] = row
                elif row[0] == 'D' and row[8] in interconnectors:
                    rows[row[8]] = row
        with out_file.open('w') as wf:
            writer = csv.writer(wf)
            writer.writerows([r for r in rows.values()])
    with out_file.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                ic = interconnectors.get(row[8])
                if ic:
                    ic.from_region_loss_share = float(row[5])
                    # ic.max_mw_in = float(row[9])
                    # ic.max_mw_out = float(row[10])
                    ic.loss_constant = float(row[11])
                    ic.loss_flow_coefficient = float(row[12])
                    ic.import_limit = int(row[17])
                    ic.export_limit = int(row[18])
                    # ic.fcas_support_unavailable = int(row[24])
                    # ic.ic_type = row[25]


def add_simplified_loss_factor_model(interconnectors, t):
    out_file = default.DATA_DIR / 'predefined' / f'LOSSFACTORMODEL_{t.year}{t.month:02d}01.csv'
    if not out_file.is_file():
        lfm_dir = preprocess.download_dvd_data('LOSSFACTORMODEL', t)
        rows = {}
        with lfm_dir.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == 'I':
                    rows['I'] = row
                elif row[0] == 'D' and row[6] in interconnectors:
                    rows[row[6]+row[7]] = row
        with out_file.open('w') as wf:
            writer = csv.writer(wf)
            writer.writerows([r for r in rows.values()])
    with out_file.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                ic = interconnectors.get(row[6])
                if ic:
                    ic.demand_coefficient[row[7]] = float(row[8])


def add_simplified_loss_model(interconnectors, t):
    out_file = default.DATA_DIR / 'predefined' / f'LOSSMODEL_{t.year}{t.month:02d}01.csv'
    if not out_file.is_file():
        lm_dir = preprocess.download_dvd_data('LOSSMODEL', t)
        rows = {}
        with lm_dir.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == 'I':
                    rows['I'] = row
                elif row[0] == 'D' and row[6] in interconnectors:
                    rows[row[6] + row[8]] = row
        with out_file.open('w') as wf:
            writer = csv.writer(wf)
            writer.writerows([r for r in rows.values()])
    with out_file.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D':
                ic = interconnectors.get(row[6])
                if ic:
                    ic.mw_breakpoint[int(row[8])] = float(row[9])


def add_simplified_mnsp_interconnector(links, t):
    """Add MNSP interconnector information.

    Args:
        links (dict): dictionary of links
        t (datetime.datetime): current datetime

    Returns:
        None
    """
    out_file = default.DATA_DIR / 'predefined' / f'MNSP_INTERCONNECTOR_{t.year}{t.month:02d}01.csv'
    if not out_file.is_file():
        mnsp_dir = preprocess.download_dvd_data('MNSP_INTERCONNECTOR', t)
        rows = {}
        with mnsp_dir.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == 'I':
                    rows['I'] = row
                elif row [0] == 'D' and row[4] in links:
                    rows [row[4]] = row
        with out_file.open('w') as wf:
            writer = csv.writer(wf)
            writer.writerows([r for r in rows.values()])
    with out_file.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == 'D' and default.extract_datetime(row[5]) <= t:
                link = links.get(row[4])
                if link:
                    link.interconnector_id = row[7]
                    link.from_region = row[8]
                    link.to_region = row[9]
                    link.max_capacity = int(row[10])
                    link.lhs_factor = float(row[12])
                    link.from_region_tlf = float(row[17]) if row[17] else None
                    link.to_region_tlf = float(row[18]) if row[18] else None