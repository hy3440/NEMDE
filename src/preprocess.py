import csv
import datetime
import logging
import io
import pathlib
import re
import requests
import zipfile

log = logging.getLogger(__name__)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent  # Base directory
DATA_DIR = BASE_DIR / 'data'  # Data directory
OUT_DIR = BASE_DIR / 'out'  # Result directory
LOG_DIR = BASE_DIR / 'log'  # Log directory
all_dir = DATA_DIR / 'all'  # all directory in data directory
all_dir.mkdir(parents=True, exist_ok=True)
dvd_dir = DATA_DIR / 'dvd'
dvd_dir.mkdir(parents=True, exist_ok=True)
NEMSPDOutputs_dir = DATA_DIR / 'NEMSPDOutputs'
NEMSPDOutputs_dir.mkdir(parents=True, exist_ok=True)

CURRENT_URL = 'http://nemweb.com.au/Reports/Current'  # Base URL to download files
ARCHIVE_URL = 'http://nemweb.com.au/Reports/Archive/'  # Archive URL to download files
DVD_URL = 'http://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/{}/MMSDM_{}_{:02d}/MMSDM_Historical_Data_SQLLoader/DATA/'

ZERO = datetime.timedelta(seconds=0)
FIVE_MIN = datetime.timedelta(minutes=5)
THIRTY_MIN = datetime.timedelta(minutes=30)
FOUR_HOUR = datetime.timedelta(hours=4)
ONE_DAY = datetime.timedelta(days=1)

TOTAL_INTERVAL = 288


def new_dir(t):
    case_date = get_case_date(t)
    date_dir = DATA_DIR / case_date
    date_dir.mkdir(parents=True, exist_ok=True)
    return date_dir


def early_morning(t: datetime.datetime) -> bool:
    start = datetime.datetime(t.year, t.month, t.day, 0, 0, 0)
    return t - start <= FOUR_HOUR


def extract_datetime(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, '%Y/%m/%d %H:%M:%S')


def get_case_date(t: datetime.datetime) -> str:
    if early_morning(t):
        return (t - ONE_DAY).strftime('%Y%m%d')  # YYmmdd
    else:
        return t.strftime('%Y%m%d')  # YYmmdd


def get_current_date(t: datetime.datetime) -> str:
    if t.hour == 0 and t.minute == 0 and t.second == 0:
        return (t - ONE_DAY).strftime('%Y%m%d')  # YYmmdd
    else:
        return t.strftime('%Y%m%d')  # YYmmdd


def get_report_date(t: datetime.datetime) -> str:
    if early_morning(t):
        return t.strftime('%Y%m%d')
    else:
        return (t + ONE_DAY).strftime('%Y%m%d')


def get_case_datetime(t: datetime.datetime) -> str:
    return t.strftime('%Y%m%d%H%M')  # YYmmddHHMM


def get_interval_datetime(t: datetime.datetime) -> str:
    return t.strftime('%Y/%m/%d %H:%M:%S')  # YY/mm/dd HH:MM:SS


def get_result_datetime(t):
    return t.strftime('%Y-%m-%d %H-%M-%S')  # YY-mm-dd HH:MM:SS


def datetime_to_interval(t):
    last = t - ONE_DAY if early_morning(t) else t
    start = datetime.datetime(last.year, last.month, last.day, 4, 0)
    no = int((t - start) / FIVE_MIN)
    return last, no


def download_p5min_unit_solution(current):
    section = 'P5MIN_UNITSOLUTION'
    year = current.year
    month = current.month
    p = dvd_dir / f'DVD_{section}_{get_case_datetime(current)}.csv'
    if not p.is_file():
        url = (DVD_URL + '/PUBLIC_DVD_{}_{}{:02d}010000.zip').format(year, year, month, section, year, month)
        result = requests.get(url)
        if result.ok:
            with zipfile.ZipFile(io.BytesIO(result.content)) as zf:
                csv_name = zf.namelist()[0]
                # logging.info(f'Download {csv_name}')
                with p.open('w') as f:
                    writer = csv.writer(f, delimiter=',')
                    with zf.open(csv_name, 'r') as infile:
                        reader = csv.reader(io.TextIOWrapper(infile))
                        for row in reader:
                            if row[0] == 'I':
                                writer.writerow(row)
                            elif row[0] == 'D':
                                t = extract_datetime(row[4])
                                if t == current:
                                    writer.writerow(row)
                                elif t > current:
                                    return None


def download_from_url(url, file):
    """Download file from the given url.

    Args:
        url (str): URL download file from
        file: File path to save

    Returns:
        None

    """
    result = requests.get(url)
    if result.ok:
        with file.open('wb') as f:
            f.write(result.content)


def download_xml(t):
    last, no = datetime_to_interval(t)
    f = NEMSPDOutputs_dir / f'NEMSPDOutputs_{last.year}{last.month:02d}{last.day:02d}{no:03d}00.loaded'
    if not f.is_file():
        url = f'https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/NEMDE/{last.year}/NEMDE_{last.year}_{last.month:02d}/NEMDE_Market_Data/NEMDE_Files/NemSpdOutputs_{last.year}{last.month:02d}{last.day:02d}_loaded.zip'
        r = requests.get(url)
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        for xml_file in zf.infolist():
            if xml_file.filename == f'NEMSPDOutputs_{last.year}{last.month:02d}{last.day:02d}{no:03d}00.loaded':
                # with p.open('wb') as f:
                #     f.write(zf.read(xml_file))
                zf.extract(xml_file, NEMSPDOutputs_dir)
    return f


def download(url, p):
    """Unzip and download file from URL.

    Args:
        url (str): URL to download file from
        file (pathlib.Path): File path to save

    Returns:
        None

    """
    result = requests.get(url)
    # print(url)
    if result.ok:
        with zipfile.ZipFile(io.BytesIO(result.content)) as zf:
            csv_name = zf.namelist()[0]
            # logging.info(f'Download {csv_name}')
            with p.open('wb') as f:
                f.write(zf.read(csv_name))
            if not p.is_file():
                logging.error(f'Cannot download from URL: {url}.')


def download_file(section, file_pattern, date_pattern, file, t, archive_pattern=None):
    """Download a matched file from the section.

    Args:
        section (str): Section to download from
        file_pattern (str): Pattern of file name
        date_pattern (str):
        file (pathlib.Path): File path to save
        t: (datetime.datetime):

    Returns:
        None

    """
    page = requests.get(f'{CURRENT_URL}/{section}')
    regex = re.compile(f'{file_pattern}_{date_pattern}<')
    matches = regex.findall(page.text)
    if len(matches) == 0:
        current_date = get_current_date(t)
        p = requests.get(f'{ARCHIVE_URL}/{section}')
        r = re.compile(f'{file_pattern if archive_pattern is None else archive_pattern}_{current_date}.zip<')
        match = r.findall(p.text)[0]

        url = f'{ARCHIVE_URL}/{section}/{match[:-1]}'
        result = requests.get(url)
        if result.ok:
            with zipfile.ZipFile(io.BytesIO(result.content)) as zf:
                regex = re.compile(f'{file_pattern}_{date_pattern}')
                m = list(filter(regex.match, zf.namelist()))[0]
                zzf = zipfile.ZipFile(io.BytesIO(zf.read(m)))
                csv_name = zzf.namelist()[0]
                with file.open('wb') as f:
                    f.write(zzf.read(csv_name))
    else:
        match = matches[0]
        download(f'{CURRENT_URL}/{section}/{match[:-1]}', file)


def download_trading(t: datetime.datetime) -> None:
    """Download trading summary of the given datetime from
    <#VISIBILITY_ID>_TRADINGIS_<#CASE_DATETIME>_<#EVENT_QUEUE_ID>.zip

    e.g. http://nemweb.com.au/Reports/Current/TradingIS_Reports/PUBLIC_TRADINGIS_201907041130_0000000309915971.zip

    Args:
        t(datetime): Datetime of downloaded data

    Returns:
        Path to the downloaded file

    """
    case_datetime = get_case_datetime(t)
    trading_dir = new_dir(t) / f'PUBLIC_TRADINGIS_{case_datetime}.csv'
    if not trading_dir.is_file():
        section = 'TradingIS_Reports'
        visibility_id = 'PUBLIC'
        file_id = 'TRADINGIS'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = f'{case_datetime}_[0-9]{{16}}.zip'
        download_file(section, file_pattern, date_pattern, trading_dir, t)
    return trading_dir


def download_intermittent(t: datetime.datetime) -> None:
    """Download intermittent generation forecast of the given report date from
    <#CURRENT_URL>/<#SECTION>/<#VISIBILITY_ID>_NEXT_DAY_INTERMITTENT_DS_<#REPORT_DATETIME>.zip

    e.g. http://nemweb.com.au/Reports/Current/Next_Day_Intermittent_DS/PUBLIC_NEXT_DAY_INTERMITTENT_DS_20190410041023.zip

    Args:
        t: (datetime.datetime): Report date of downloaded data

    Returns:
        Path to the downloaded file

    """
    case_date = get_case_date(t)
    intermittent_dir = new_dir(t) / f'PUBLIC_NEXT_DAY_INTERMITTENT_DS_{case_date}.csv'
    if not intermittent_dir.is_file():
        section = 'Next_Day_Intermittent_DS'
        visibility_id = 'PUBLIC'
        file_id = 'NEXT_DAY_INTERMITTENT_DS'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = f'{case_date}_[0-9]{{16}}.zip'
        download_file(section, file_pattern, date_pattern, intermittent_dir, t)
    return intermittent_dir


def download_next_day_dispatch(t: datetime.datetime) -> None:
    """Download next day dispatch of the given date from
    <#CURRENT_URL>/<#SECTION>/<#VISIBILITY_ID>_NEXT_DAY_DISPATCH_<#CASE_DATE>_<#EVENT_QUEUE_ID>.zip

    e.g. http://nemweb.com.au/Reports/Current/Next_Day_Dispatch/PUBLIC_NEXT_DAY_DISPATCH_20190527_0000000308408731.zip

    Args:
        t: (datetime.datetime): Date of downloaded data

    Returns:
        Path to the downloaded file

    """
    case_date = get_case_date(t)
    record_dir = new_dir(t) / f'PUBLIC_NEXT_DAY_DISPATCH_{case_date}.csv'
    if not record_dir.is_file():
        section = 'Next_Day_Dispatch'
        visibility_id = 'PUBLIC'
        file_id = 'NEXT_DAY_DISPATCH'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = f'{case_date}_[0-9]{{16}}.zip'
        download_file(section, file_pattern, date_pattern, record_dir, t)
    return record_dir


def download_bidmove_summary(t: datetime.datetime) -> None:
    """Download bidmove summary of the given date from
    <#CURRENT_URL>/<#SECTION>/<#VISIBILITY_ID>_BIDMOVE_SUMMARY_<#CASE_DATE>_<#EVENT_QUEUE_ID>.zip

    e.g. http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_SUMMARY_20170201_0000000280589268.zip

    Args:
        t: (datetime.datetime): Date of downloaded data

    Returns:
        path to the downloaded file

    """
    case_date = get_case_date(t)
    bids_dir = new_dir(t) / f'PUBLIC_BIDMOVE_SUMMARY_{case_date}.csv'
    if not bids_dir.is_file():
        section = 'Bidmove_Summary'
        visibility_id = 'PUBLIC'
        file_id = 'BIDMOVE_SUMMARY'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = f'{case_date}_[0-9]{{16}}.zip'
        download_file(section, file_pattern, date_pattern, bids_dir, t)
    return bids_dir


def download_bidmove_complete(t: datetime.datetime) -> None:
    """Download bidmove complete of the given date from
    <#CURRENT_URL>/<#SECTION>/<#VISIBILITY_ID>_BIDMOVE_COMPLETE_<#CASE_DATE>_<#EVENT_QUEUE_ID>.zip

    e.g. http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_COMPLETE_20170201_0000000280589266.zip

    Args:
        t: (datetime.datetime): Date of downloaded data

    Returns:
        Path to the downloaded file

    """
    case_date = get_case_date(t)
    bids_dir = new_dir(t) / f'PUBLIC_BIDMOVE_COMPLETE_{case_date}.csv'
    if not bids_dir.is_file():
        section = 'Bidmove_Complete'
        visibility_id = 'PUBLIC'
        file_id = 'BIDMOVE_COMPLETE'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = f'{case_date}_[0-9]{{16}}.zip'
        download_file(section, file_pattern, date_pattern, bids_dir, t)
    return bids_dir


def download_mnsp_bids(t):
    """Download MNSP bids of the given date from
    <#CURRENT_URL>/<#SECTION>/<#VISIBILITY_ID>_YESTBIDMNSP_<#CASE_DATE>0000_<#EVENT_QUEUE_ID>.zip

    e.g. http://nemweb.com.au/Reports/Current/Yesterdays_MNSPBids_Reports/PUBLIC_YESTBIDMNSP_201907160000_20190717040529.zip

    Args:
        t: (datetime.datetime): Date of downloaded data

    Returns:
        path to the downloaded file

    """
    case_date = get_case_date(t)
    mnsp_dir = new_dir(t) / f'PUBLIC_YESTBIDMNSP_{case_date}.csv'
    if not mnsp_dir.is_file():
        section = 'Yesterdays_MNSPBids_Reports'
        visibility_id = 'PUBLIC'
        file_id = 'YESTBIDMNSP'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = f'{case_date}0000_[0-9]{{14}}.zip'
        download_file(section, file_pattern, date_pattern, mnsp_dir, t, 'PUBLIC_YESTMNSPBID')
    return mnsp_dir


def download_5min_predispatch(t: datetime.datetime) -> None:
    """Download 5-minute predispatch summary of the given datetime from
    <#CURRENT_URL>/<#SECTION>/<#VISIBILITY_ID>_P5MIN_<#CASE_DATETIME>_<#REPORT_DATETIME>.zip
    e.g. http://nemweb.com.au/Reports/Current/P5_Reports/PUBLIC_P5MIN_201904301445_20190430144045.zip

    Args:
        t: (datetime.datetime): Datetime of downloaded data

    Returns:
        Path to the downloaded file

    """
    case_datetime = get_case_datetime(t)
    p5_dir = new_dir(t) / f'PUBLIC_P5MIN_{case_datetime}.csv'
    if not p5_dir.is_file():
        section = 'P5_Reports'
        visibility_id = 'PUBLIC'
        file_id = 'P5MIN'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = f'{case_datetime}_[0-9]{{14}}.zip'
        download_file(section, file_pattern, date_pattern, p5_dir, t)
    return p5_dir


def download_predispatch(t: datetime.datetime) -> None:
    """Download predispatch summary of the given datetime from
    <#CURRENT_URL>/<#SECTION>/<#VISIBILITY_ID>_PREDISPATCHIS_<#CASE_DATETIME>_<#REPORT_DATETIME>.zip

    e.g. http://nemweb.com.au/Reports/Current/PredispatchIS_Reports/PUBLIC_PREDISPATCHIS_201905031130_20190503110120.zip

    Args:
        t: (datetime.datetime): Datetime of downloaded data

    Returns:
        Path to the downloaded file

    """
    case_datetime = get_case_datetime(t)
    predispatch_dir = new_dir(t) / f'PUBLIC_PREDISPATCHIS_{case_datetime}.csv'
    if not predispatch_dir.is_file():
        section = 'PredispatchIS_Reports'
        visibility_id = 'PUBLIC'
        file_id = 'PREDISPATCHIS'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = f'{case_datetime}_[0-9]{{14}}.zip'
        download_file(section, file_pattern, date_pattern, predispatch_dir, t)
    return predispatch_dir


def download_network_outage(t: datetime.datetime) -> None:
    """Download network outage of the given datetime from
    <#CURRENT_URL>/<#SECTION>/<#VISIBILITY_ID>_NETWORK_<#REPORT_DATETIME>_<#EVENT_QUEUE_ID>.ZIP
    e.g. http://nemweb.com.au/Reports/Current/Network/PUBLIC_NETWORK_20190422133005_0000000307021827.zip

    Args:
        report_datetime(str): Datetime of downloaded data

    Returns:
        None

    """
    case_datetime = get_case_datetime(t)
    outage_dir = new_dir(t) / f'PUBLIC_NETWORK_{case_datetime}.csv'
    if not outage_dir.is_file():
        section = 'Network'
        visibility_id = 'PUBLIC'
        file_id = 'NETWORK'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = '{}[0-9]{2}_[0-9]{{16}}.zip'.format(case_datetime)
        download_file(section, file_pattern, date_pattern, outage_dir, t)
    return outage_dir


def download_dispatch_summary(t: datetime.datetime) -> None:
    """Download dispatch summary of the given datetime from
    <#CURRENT_URL>/<#SECTION/<#VISIBILITY_ID>_DISPATCHIS_<#CASE_DATETIME>_<#EVENT_QUEUE_ID>.zip

    e.g. http://nemweb.com.au/Reports/Current/DispatchIS_Reports/PUBLIC_DISPATCHIS_201904301040_0000000307325261.zip

    Args:
        t(datetime): Datetime of downloaded data

    Returns:
        Path to the downloaded file

    """
    case_datetime = get_case_datetime(t)
    dispatch_dir = new_dir(t) / f'PUBLIC_DISPATCHIS_{case_datetime}.csv'
    if not dispatch_dir.is_file():
        section = 'DispatchIS_Reports'
        visibility_id = 'PUBLIC'
        file_id = 'DISPATCHIS'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = f'{case_datetime}_[0-9]{{16}}.zip'
        download_file(section, file_pattern, date_pattern, dispatch_dir, t)
    return dispatch_dir


def download_dispatch_scada(t: datetime.datetime) -> None:
    """Download real time scheduled, semi-scheduled and non-scheduled DUID SCADA data from
    <#CURRENT_URL>/<#SECTION>/<#VISIBILITY_ID>_DISPATCHSCADA_<#CASE_DATETIME>_<#EVENT_QUEUE_ID>.zip
    e.g. http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.zip

    Args:
        t(datetime): Datetime of downloaded data

    Returns:
        Path to the downloaded file

    """
    case_datetime = get_case_datetime(t)
    scada_dir = new_dir(t) / f'PUBLIC_DISPATCHSCADA_{case_datetime}.csv'
    if not scada_dir.is_file():
        section = 'Dispatch_SCADA'
        visibility_id = 'PUBLIC'
        file_id = 'DISPATCHSCADA'
        file_pattern = f'{visibility_id}_{file_id}'
        date_pattern = f'{case_datetime}_[0-9]{{16}}.zip'
        filename = f'{visibility_id}_{file_id}_{case_datetime}.csv'
        download_file(section, file_pattern, date_pattern, scada_dir, t)
    return scada_dir


def download_altlimits() -> None:
    """Download the complete list of ratings used in AEMO's EMS (energy management system)

    Returns:
        None

    """
    # logging.info('Downloading Ratings in EMS.')
    file = all_dir / 'altlimits.csv'
    download('http://nemweb.com.au/Reports/Current/Alt_Limits/altlimits.zip', file)


def download_transmission_equipment_ratings() -> None:
    """Download the daily transmission equipment ratings used in constraint equations and the ID used in the right-hand of the constraint equations

    Returns:
        str: Name of the downloaded file
    """
    # logging.info('Downloading Daily transmission equipment ratings.')
    file = all_dir / 'PUBLIC_TER_DAILY.CSV'
    download('http://nemweb.com.au/Reports/Current/Alt_Limits/PUBLIC_TER_DAILY.zip', file)


def download_registration() -> None:
    """Download NEM regeistration and exemption list.

    Returns:
        None

    """
    registration_file = all_dir / 'REGISTRATION.xls'
    if not registration_file.is_file():
        # logging.info('Download NEM Registration and Exemption List.')
        url = 'http://www.aemo.com.au/-/media/Files/Electricity/NEM/Participant_Information/NEM-Registration-and-Exemption-List.xls'
        download_from_url(url, registration_file)
    return registration_file


def download_mlf() -> None:
    """Download NEM marginal loss factors.

    Returns:
        None

    """
    mlf_file = all_dir / 'MLF.xls'
    if not mlf_file.is_file():
        # logging.info('Download NEM margional loss factors.')
        url = 'https://www.aemo.com.au/-/media/Files/Electricity/NEM/Security_and_Reliability/Loss_Factors_and_Regional_Boundaries/2019/2019-20-MLF-Applicable-from-01-July-2019-to-30-June-2020.xlsx'
        download_from_url(url, mlf_file)
    return mlf_file


def download_dvd_data(section, current=None):
    # current = datetime.datetime(2019, 9, 19, 4, 5, 0)
    if current:
        year = current.year
        month = current.month
    else:
        current = datetime.datetime.now()
        year = current.year if current.month != 1 else current.year - 1
        month = current.month - 1 if current.month != 1 else 12
    f = dvd_dir / f'DVD_{section}_{year}{month:02d}010000.csv'
    if not f.is_file():
        url = (DVD_URL + '/PUBLIC_DVD_{}_{}{:02d}010000.zip').format(year, year, month, section, year, month)
        download(url, f)
    if section == 'DISPATCHCONSTRAINT':
        wf_dir = dvd_dir / f'{section}_{get_case_datetime(current)}.csv'
        if not wf_dir.is_file():
            # rows = []
            with f.open() as rf:
                reader = csv.reader(rf)
                # for row in reader:
                #     if row[0] == 'I' or current == extract_datetime(row[4]):
                #         rows.append(row)
                rows = [row for row in reader if row[0] == 'D' and current == extract_datetime(row[4])]
            with wf_dir.open(mode='w') as result_file:
                writer = csv.writer(result_file, delimiter=',')
                for row in rows:
                    writer.writerow(row)
        return wf_dir
    return f


def download_interval(t: datetime.datetime) -> None:
    download_5min_predispatch(t)
    download_dispatch_summary(t)


def download_period(t: datetime.datetime) -> None:
    download_trading(t)
    download_predispatch(t)


def download_all_day(t: datetime.datetime) -> None:
    download_next_day_dispatch(t)
    download_bidmove_complete(t)
    download_mnsp_bids(t)
    download_intermittent(t)


def main():
    t = datetime.datetime(2020, 9, 1, 4, 0)
    # download_all_day(t + FIVE_MIN)
    # for i in range(TOTAL_INTERVAL):
    #     download_interval(t + FIVE_MIN)
    #     if i % 6 == 0:
    #         download_period(t + THIRTY_MIN)
    #     t += FIVE_MIN
    download_xml(t)


def test():
    t = datetime.datetime(2019, 9, 29, 4, 5)
    # download_dvd_data('INTERCONNECTORCONSTRAINT')
    constr_dir = download_dvd_data('SPDREGIONCONSTRAINT', t)
    print(constr_dir.is_file())


if __name__ == '__main__':
    main()
    # download_p5min_unit_solution(datetime.datetime(2019, 9, 1, 4, 5, 0))
