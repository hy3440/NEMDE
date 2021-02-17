import pandas as pd
import pathlib
import zipfile


BASE_DIR = pathlib.Path(__file__).resolve().parent.parent  # Base directory
DATA_DIR = BASE_DIR / 'data'  # Data directory
OUT_DIR = BASE_DIR / 'out'  # Result directory
all_dir = DATA_DIR / 'all'  # all directory in data directory
all_dir.mkdir(parents=True, exist_ok=True)
dvd_dir = DATA_DIR / 'dvd'
dvd_dir.mkdir(parents=True, exist_ok=True)

