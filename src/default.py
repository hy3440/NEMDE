import datetime
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent  # Base directory
DATA_DIR = BASE_DIR / 'data'  # Data directory
OUT_DIR = BASE_DIR / 'out'  # Result directory
LOG_DIR = BASE_DIR / 'log'  # Log directory
MODEL_DIR = BASE_DIR / 'model'  # Model directory

ZERO = datetime.timedelta(seconds=0)
FIVE_MIN = datetime.timedelta(minutes=5)
THIRTY_MIN = datetime.timedelta(minutes=30)
FOUR_HOUR = datetime.timedelta(hours=4)
ONE_DAY = datetime.timedelta(days=1)

# TOTAL_INTERVAL = 288