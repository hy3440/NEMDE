import datetime
import json
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent  # Base directory
DATA_DIR = BASE_DIR / 'data'  # Data directory

path = DATA_DIR / 'predispatch_intervals.json'

start = datetime.datetime(2019, 10, 25, 4, 30, 0)
THIRTY = datetime.timedelta(minutes=30)
res = {}
for i in range(48, 31, -1):
    res[start.strftime('%H:%M')] = i
    start += THIRTY
for i in range(79, 48, -1):
    res[start.strftime('%H:%M')] = i
    start += THIRTY
json.dump(res, path.open('w'), indent=2)