import io
import os
import pandas as pd
import re
import requests
import zipfile


# Core data directory
data_dir = os.path.abspath(os.path.join(os.path.curdir, os.pardir, 'data'))

# Base URL to download data from
BASE_URL = "http://nemweb.com.au/Reports/Current"


def download(section, filename_pattern):
    """
    Download all the matched files from the section.

    e.g. Download the files from http://nemweb.com.au/Reports/Current/Bidmove_Summary/ whose name matches the pattern
         PUBLIC_BIDMOVE_SUMMARY_<#CASE_DATE>_[0-9]{16}.zip

    :param section: the section to download from
    :param filename_pattern:
    :return: a list of downloaded csv filenames
    """
    page = requests.get("{0}/{1}".format(BASE_URL, section))
    regex = re.compile("{0}<".format(filename_pattern))
    # match = regex.finditer(page.text)[0]:
    filenames = []
    for match in regex.findall(page.text):
        result = requests.get("{0}/{1}/{2}".format(BASE_URL, section, match[:-1]))
        if result.ok:
            with zipfile.ZipFile(io.BytesIO(result.content)) as zf:
                csv_name = zf.namelist()[0]
                filenames.append(csv_name)
                zf.extractall(data_dir)
    print("{0}: {1} file(s).".format(section, len(filenames)))
    return filenames


def download_bidmove_summary(case_date):
    """
    Download bidmove summary of the given date from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_BIDMOVE_SUMMARY_<#CASE_DATE>_<#EVENT_QUEUE_ID>.zip
    e.g. http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_SUMMARY_20170201_0000000280589268.zip

    :param case_date: the date of downloaded data
    :return: a list of downloaded csv filenames
    """
    section = "Bidmove_Summary"
    visibility_id = "PUBLIC"
    file_id = "BIDMOVE_SUMMARY"
    filename_pattern = "{0}_{1}_{2}_[0-9]{{16}}.zip".format(visibility_id, file_id, case_date)
    return download(section, filename_pattern)


def download_5min_predispatch(case_date):
    """
    Download 5-minute predispatch summary of the given date from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_P5MIN_<#CASE_DATETIME>_<#REPORT_DATETIME>.zip
    e.g. http://nemweb.com.au/Reports/Current/P5_Reports/PUBLIC_P5MIN_201904301445_20190430144045.zip

    :param case_date: the date of downloaded data
    :return: a list of downloaded csv filenames
    """
    section = "P5_Reports"
    visibility_id = "PUBLIC"
    file_id = "P5MIN"
    filename_pattern = "{0}_{1}_{2}[0-9]{{4}}_[0-9]{{14}}.zip".format(visibility_id, file_id, case_date)
    return download(section, filename_pattern)


def download_predispatch(case_date):
    """
    Download predispatch summary of the given date from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_PREDISPATCHIS_<#CASE_DATETIME>_<#REPORT_DATETIME>.zip
    e.g. http://nemweb.com.au/Reports/Current/PredispatchIS_Reports/PUBLIC_PREDISPATCHIS_201905031130_20190503110120.zip

    :param case_date: the date of downloaded data
    :return: a list of downloaded csv filenames
    """
    section = "PredispatchIS_Reports"
    visibility_id = "PUBLIC"
    file_id = "PREDISPATCHIS"
    filename_pattern = "{0}_{1}_{2}[0-9]{{4}}_[0-9]{{14}}.zip".format(visibility_id, file_id, case_date)
    return download(section, filename_pattern)


def download_network_outage(case_date):
    """
    Download network outage of the given date from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_NETWORK_<#REPORT_DATETIME>_<#EVENT_QUEUE_ID>.ZIP
    e.g. http://nemweb.com.au/Reports/Current/Network/PUBLIC_NETWORK_20190422133005_0000000307021827.zip

    :param case_date: the date of downloaded data
    :return: a list of downloaded csv filenames
    """
    section = "Network"
    visibility_id = "PUBLIC"
    file_id = "NETWORK"
    filename_pattern = "{0}_{1}_{2}[0-9]{{6}}_[0-9]{{16}}.zip".format(visibility_id, file_id, case_date)
    return download(section, filename_pattern)


def download_dispatch_summary(case_date):
    """
    Download dispatch summary of the given date from
    <#BASE_URL>/<#SECTION/<#VISIBILITY_ID>_DISPATCHIS_<#CASE_DATETIME>_<#EVENT_QUEUE_ID>.zip
    http://nemweb.com.au/Reports/Current/DispatchIS_Reports/PUBLIC_DISPATCHIS_201904301040_0000000307325261.zip

    :param case_date: the date of downloaded data
    :return: a list of downloaded csv filenames
    """
    section = "DispatchIS_Reports"
    visibility_id = "PUBLIC"
    file_id = "DISPATCHIS"
    filename_pattern = "{0}_{1}_{2}[0-9]{{4}}_[0-9]{{16}}.zip".format(visibility_id, file_id, case_date)
    return download(section, filename_pattern)


def download_dispatch_scada(case_date):
    """
    Download real time scheduled, semi-scheduled and non-scheduled DUID SCADA data from
    <#BASE_URL>/<#SECTION>/<#VISIBILITY_ID>_DISPATCHSCADA_<#CASE_DATETIME>_<#EVENT_QUEUE_ID>.zip
    e.g. http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.zip

    :param case_date: the date of downloaded data
    :return: a list of downloaded csv filenames
    """
    section = "Dispatch_SCADA"
    visibility_id = "PUBLIC"
    file_id = "DISPATCHSCADA"
    filename_pattern = "{0}_{1}_{2}[0-9]{{4}}_[0-9]{{16}}.zip".format(visibility_id, file_id, case_date)
    return download(section, filename_pattern)


def download_all(case_date):
    """
    Download files of the given date from all sections.

    :param case_date: the date of downloaded data
    :return: a list of downloaded csv filenames
    """
    download_bidmove_summary(case_date)
    download_5min_predispatch(case_date)
    download_predispatch(case_date)
    download_network_outage(case_date)
    download_dispatch_summary(case_date)
    download_dispatch_scada(case_date)


def main():
    case_date = "20190502"
    print("Download data of {0}".format(case_date))
    download_all(case_date)


if __name__ == '__main__':
    main()
