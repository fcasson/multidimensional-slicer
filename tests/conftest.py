"""Shared test configuration — point data_utils at the test fixture."""

import os
from pathlib import Path

# Set CSV_PATH before any test imports data_utils or app
_fixture = Path(__file__).resolve().parent.parent / "data" / "fixture.csv"
os.environ["SLICER_CSV"] = str(_fixture)
