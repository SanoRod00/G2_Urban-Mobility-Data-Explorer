"""cleaning/validate.py
"""



import argparse
import csv
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "processed" / "trips_normalized_parquet"
DEFAULT_ZONES = ROOT / "data" / "processed"