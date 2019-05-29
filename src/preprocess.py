import csv
import logging
import io
import pathlib
import re
import requests
import zipfile

log = logging.getLogger(__name__)

# Base directory
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

# Data directory
DATA_DIR = BASE_DIR.joinpath('data')

# Base URL to download files data from
BASE_URL = 'http://nemweb.com.au/Reports/Current'


def download(url: str, file: pathlib.Path) -> None:
    """Unzip and download file from URL.

    Args:
        url (str): URL to download file from
        file (pathlib.Path): File path to save

    Returns:
        None

    """
    result = requests.get(url)
    if result.ok:
        with zipfile.ZipFile(io.BytesIO(result.content)) as zf:
            csv_name = zf.namelist()[0]
            logging.info('Download {}'.format(csv_name))
            with file.open('wb') as f:
                f.write(zf.read(csv_name))


def download_file(section: str, filename_pattern: str, file: pathlib.Path) -> None:
    """Download a matched file from the section.

    Args:
        section (str): Section to download from
        filename_pattern (str): Pattern of file name
        file (pathlib.Path): File path to save

    Returns:
        None

    """
    page = requests.get('{}/{}'.format(BASE_URL, section))
    regex = re.compile('{}<'.format(filename_pattern))
    match = regex.findall(page.text)[0]
    download('{}/{}/{}'.format(BASE_URL, section, match[:-1]), file)


def download_files(section: str, filename_pattern: str) -> list:
    """Download all the matched files from the section.

    e.g. Download the files from http://nemweb.com.au/Reports/Current/Bidmove_Summary/ whose name matches the pattern
         PUBLIC_BIDMOVE_SUMMARY_<#CASE_DATE>_[0-9]{16}.zip

    Args:
        section (str): Section to download files from
        filename_pattern(str): Pattern of file name

    Returns:
        list: A list of downloaded csv filenames

    """
    page = requests.get('{}/{}'.format(BASE_URL, section))
    regex = re.compile('{}<'.format(filename_pattern))
    filenames = []
    for match in regex.findall(page.text):
        csv_name = download('{}/{}/{}'.format(BASE_URL, section, match[:-1]))
        filenames.append(csv_name)
    logging.info('Downloaded {} {} file(s)'.format(section, len(filenames)))
    return filenames


def download_intermittent(report_date: str) -> None:
    """Download intermittent generation forecast of the given report date from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_NEXT_DAY_INTERMITTENT_DS_<#REPORT_DATETIME>.zip

    e.g. http://nemweb.com.au/Reports/Current/Next_Day_Intermittent_DS/PUBLIC_NEXT_DAY_INTERMITTENT_DS_20190410041023.zip

    Args:
        report_date (str): Report date of downloaded data

    Returns:
        None

    """
    section = 'Next_Day_Intermittent_DS'
    visibility_id = 'PUBLIC'
    file_id = 'NEXT_DAY_INTERMITTENT_DS'
    filename_pattern = '{}_{}_{}[0-9]{{6}}.zip'.format(visibility_id, file_id, report_date)
    filename = '{}_{}_{}.csv'.format(visibility_id, file_id, report_date)
    download_file(section, filename_pattern, DATA_DIR.joinpath(filename))


def download_next_day_dispatch(case_date: str) -> None:
    """Download next day dispatch of the given date from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_NEXT_DAY_DISPATCH_<#CASE_DATE>_<#EVENT_QUEUE_ID>.zip

    e.g. http://nemweb.com.au/Reports/Current/Next_Day_Dispatch/PUBLIC_NEXT_DAY_DISPATCH_20190527_0000000308408731.zip

    Args:
        case_date (str): Date of downloaded data

    Returns:
        None

    """
    section = 'Next_Day_Dispatch'
    visibility_id = 'PUBLIC'
    file_id = 'NEXT_DAY_DISPATCH'
    filename_pattern = '{}_{}_{}_[0-9]{{16}}.zip'.format(visibility_id, file_id, case_date)
    filename = '{}_{}_{}.csv'.format(visibility_id, file_id, case_date)
    download_file(section, filename_pattern, DATA_DIR.joinpath(filename))


def download_bidmove_summary(case_date: str) -> None:
    """Download bidmove summary of the given date from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_BIDMOVE_SUMMARY_<#CASE_DATE>_<#EVENT_QUEUE_ID>.zip

    e.g. http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_SUMMARY_20170201_0000000280589268.zip

    Args:
        case_date (str): Date of downloaded data

    Returns:
        None

    """
    section = 'Bidmove_Summary'
    visibility_id = 'PUBLIC'
    file_id = 'BIDMOVE_SUMMARY'
    filename_pattern = '{}_{}_{}_[0-9]{{16}}.zip'.format(visibility_id, file_id, case_date)
    filename = '{}_{}_{}.csv'.format(visibility_id, file_id, case_date)
    download_file(section, filename_pattern, DATA_DIR.joinpath(filename))


def download_bidmove_complete(case_date: str) -> None:
    """Download bidmove complete of the given date from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_BIDMOVE_COMPLETE_<#CASE_DATE>_<#EVENT_QUEUE_ID>.zip

    e.g. http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_COMPLETE_20170201_0000000280589266.zip

    Args:
        case_date (str): Date of downloaded data

    Returns:
        None

    """
    section = 'Bidmove_Complete'
    visibility_id = 'PUBLIC'
    file_id = 'BIDMOVE_COMPLETE'
    filename_pattern = '{}_{}_{}_[0-9]{{16}}.zip'.format(visibility_id, file_id, case_date)
    filename = '{}_{}_{}.csv'.format(visibility_id, file_id, case_date)
    download_file(section, filename_pattern, DATA_DIR.joinpath(filename))


def download_5min_predispatch(case_datetime: str) -> None:
    """Download 5-minute predispatch summary of the given datetime from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_P5MIN_<#CASE_DATETIME>_<#REPORT_DATETIME>.zip
    e.g. http://nemweb.com.au/Reports/Current/P5_Reports/PUBLIC_P5MIN_201904301445_20190430144045.zip

    Args:
        case_datetime(str): Datetime of downloaded data

    Returns:
        None

    """
    section = 'P5_Reports'
    visibility_id = 'PUBLIC'
    file_id = 'P5MIN'
    filename_pattern = '{}_{}_{}_[0-9]{{14}}.zip'.format(visibility_id, file_id, case_datetime)
    filename = '{}_{}_{}.csv'.format(visibility_id, file_id, case_datetime)
    download_file(section, filename_pattern, DATA_DIR.joinpath(filename))


def download_predispatch(case_datetime: str) -> None:
    """Download predispatch summary of the given datetime from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_PREDISPATCHIS_<#CASE_DATETIME>_<#REPORT_DATETIME>.zip

    e.g. http://nemweb.com.au/Reports/Current/PredispatchIS_Reports/PUBLIC_PREDISPATCHIS_201905031130_20190503110120.zip

    Args:
        case_datetime(str): Datetime of downloaded data

    Returns:
        None

    """
    section = 'PredispatchIS_Reports'
    visibility_id = 'PUBLIC'
    file_id = 'PREDISPATCHIS'
    filename_pattern = '{}_{}_{}_[0-9]{{14}}.zip'.format(visibility_id, file_id, case_datetime)
    filename = '{}_{}_{}.csv'.format(visibility_id, file_id, case_date)
    download_file(section, filename_pattern, DATA_DIR.joinpath(filename))


def download_network_outage(report_datetime: str) -> None:
    """Download network outage of the given datetime from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_NETWORK_<#REPORT_DATETIME>_<#EVENT_QUEUE_ID>.ZIP
    e.g. http://nemweb.com.au/Reports/Current/Network/PUBLIC_NETWORK_20190422133005_0000000307021827.zip

    Args:
        report_datetime(str): Datetime of downloaded data

    Returns:
        None

    """
    section = 'Network'
    visibility_id = 'PUBLIC'
    file_id = 'NETWORK'
    filename_pattern = '{}_{}_{}_[0-9]{{16}}.zip'.format(visibility_id, file_id, report_datetime)
    filename = '{}_{}_{}.csv'.format(visibility_id, file_id, report_datetime)
    download_file(section, filename_pattern, DATA_DIR.joinpath(filename))


def download_dispatch_summary(case_datetime: str) -> None:
    """Download dispatch summary of the given datetime from
    <#BASE_URL>/<#SECTION/<#VISIBILITY_ID>_DISPATCHIS_<#CASE_DATETIME>_<#EVENT_QUEUE_ID>.zip

    e.g. http://nemweb.com.au/Reports/Current/DispatchIS_Reports/PUBLIC_DISPATCHIS_201904301040_0000000307325261.zip

    Args:
        case_datetime(str): Datetime of downloaded data

    Returns:
        None

    """
    section = 'DispatchIS_Reports'
    visibility_id = 'PUBLIC'
    file_id = 'DISPATCHIS'
    filename_pattern = '{}_{}_{}_[0-9]{{16}}.zip'.format(visibility_id, file_id, case_datetime)
    filename = '{}_{}_{}.csv'.format(visibility_id, file_id, case_datetime)
    download_file(section, filename_pattern, DATA_DIR.joinpath(filename))


def download_dispatch_scada(case_datetime: str) -> None:
    """Download real time scheduled, semi-scheduled and non-scheduled DUID SCADA data from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_DISPATCHSCADA_<#CASE_DATETIME>_<#EVENT_QUEUE_ID>.zip
    e.g. http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.zip

    Args:
        case_datetime(str): Datetime of downloaded data

    Returns:
        None

    """
    section = 'Dispatch_SCADA'
    visibility_id = 'PUBLIC'
    file_id = 'DISPATCHSCADA'
    filename_pattern = '{}_{}_{}_[0-9]{{16}}.zip'.format(visibility_id, file_id, case_datetime)
    filename = '{}_{}_{}.csv'.format(visibility_id, file_id, case_datetime)
    download_file(section, filename_pattern, DATA_DIR.joinpath(filename))


def download_altlimits() -> None:
    """Download the complete list of ratings used in AEMO's EMS (energy management system)

    Returns:
        None

    """
    logging.info('Downloading Ratings in EMS.')
    file = DATA_DIR.joinpath('altlimits.csv')
    return download('http://nemweb.com.au/Reports/Current/Alt_Limits/altlimits.zip', file)


def download_transmission_equipment_ratings() -> None:
    """Download the daily transmission equipment ratings used in constraint equations and the ID used in the right-hand of the constraint equations

    Returns:
        str: Name of the downloaded file
    """
    logging.info('Downloading Daily transmission equipment ratings.')
    file = DATA_DIR.joinpath('PUBLIC_TER_DAILY.CSV')
    download('http://nemweb.com.au/Reports/Current/Alt_Limits/PUBLIC_TER_DAILY.zip', file)


def download_all(case_date):
    """Download files of the given date from all sections.

    Args:
        case_date (str): the date of downloaded data

    Returns:
        None
    """
    download_bidmove_complete(case_date)
    download_bidmove_summary(case_date)
    download_5min_predispatch(case_date)
    download_predispatch(case_date)
    download_network_outage(case_date)
    download_dispatch_summary(case_date)
    download_dispatch_scada(case_date)
    download_altlimits()
    download_transmission_equipment_ratings()


def main():
    logging.basicConfig(format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)
    case_date = '20190528'
    logging.info('Downloading data of {}'.format(case_date))
    # download_intermittent(case_date)
    # download_all(case_date)
    # download_bidmove_complete(case_date)
    # download_bidmove_summary(case_date)
    # download_dispatch_summary(case_date)
    # download_5min_predispatch(case_date)
    download_next_day_dispatch(case_date)


if __name__ == '__main__':
    main()
