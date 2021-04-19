import datetime
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent  # Base directory
DATA_DIR = BASE_DIR / 'data'  # Data directory
OUT_DIR = BASE_DIR / 'out'  # Result directory
LOG_DIR = BASE_DIR / 'log'  # Log directory
MODEL_DIR = BASE_DIR / 'model'  # Model directory

ZERO = datetime.timedelta(seconds=0)
FIVE_MIN = datetime.timedelta(minutes=5)
TWENTYFIVE_MIN = datetime.timedelta(minutes=25)
THIRTY_MIN = datetime.timedelta(minutes=30)
FOUR_HOUR = datetime.timedelta(hours=4)
ONE_DAY = datetime.timedelta(days=1)


def early_morning(t):
    """ Check if t is early morning (before 4am).

    Args:
        t (datetime.datetime):

    Returns:
        True if it is before 4am; False otherwise.
    """
    start = datetime.datetime(t.year, t.month, t.day, 0, 0, 0)
    return t - start <= FOUR_HOUR


def extract_datetime(s):
    """ Extract datetime.datetime from string.

    Args:
        s (str): string to extract

    Returns:
        Extracted datetime.datetime
    """
    return datetime.datetime.strptime(s, '%Y/%m/%d %H:%M:%S')


def get_case_date(t) :
    """ Get the case time. Note before 4am is condered as yesterday.

    Args:
        t (datetime.datetime): datetime

    Returns:
        A string in format YYmmdd.
    """
    if early_morning(t):
        return (t - ONE_DAY).strftime('%Y%m%d')  # YYmmdd
    else:
        return t.strftime('%Y%m%d')  # YYmmdd


def get_current_date(t):
    """ Get current date.

    Args:
        t (datetime.datetime): datetime

    Returns:
        A string in format YYmmdd
    """
    if t.hour == 0 and t.minute == 0 and t.second == 0:
        return (t - ONE_DAY).strftime('%Y%m%d')  # YYmmdd
    else:
        return t.strftime('%Y%m%d')  # YYmmdd


def get_report_date(t):
    """ Get report date. Note before 4am is considered as next day.

    Args:
         t (datetime.datetime): datetime

    Returns:
        A string in format YYmmdd.
    """
    if early_morning(t):
        return t.strftime('%Y%m%d')  # YYmmdd
    else:
        return (t + ONE_DAY).strftime('%Y%m%d')  # YYmmdd


def get_case_datetime(t):
    """ Get case datetime.

    Args:
        t (datetime.datetime): datetime

    Returns:
        A string in format YYmmddHHMM
    """
    return t.strftime('%Y%m%d%H%M')  # YYmmddHHMM


def get_interval_datetime(t):
    """ Get interval datetime.

    Args:
        t (datetime.datetime): datetime

    Returns:
        A string in format YY/mm/dd HH:MM:SS
    """
    return t.strftime('%Y/%m/%d %H:%M:%S')  # YY/mm/dd HH:MM:SS


def get_result_datetime(t):
    """ Get result datetime.

    Args:
         t (datetime.datetime): datetime

    Returns:
        A string in format YY-mm-dd HH:MM:SS
    """
    return t.strftime('%Y-%m-%d %H-%M-%S')  # YY-mm-dd HH:MM:SS


def datetime_to_interval(t):
    """ Calculate interval number by datetime.

    Args:
         t (datetime.datetime): datetime

    Returns:
        (Start datetime, Interval number)
    """
    last = t - ONE_DAY if early_morning(t) else t
    start = datetime.datetime(last.year, last.month, last.day, 4, 0)
    no = int((t - start) / FIVE_MIN)
    return last, no


def get_first_datetime(t):
    """ Get the first interval datetime.

    Args:
         t (datetime.datetime): datetime

    Returns:
        The first interval datetime.datetime
    """
    if early_morning(t):
        yesterday = t - ONE_DAY
        return datetime.datetime(yesterday.year, yesterday.month, yesterday.day, 4, 5, 0)
    else:
        return datetime.datetime(t.year, t.month, t.day, 4, 5, 0)