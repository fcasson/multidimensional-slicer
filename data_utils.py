"""Data loading and column classification for the ballooning slicer app."""

import os

import pandas as pd
from pathlib import Path

CSV_PATH = Path(os.environ.get(
    "SLICER_CSV",
    Path(__file__).resolve().parent / "IdealBallooningSamples.csv",
))
DISCRETE_THRESHOLD = 10  # columns with <= this many unique values are discrete


def load_and_clean(path: str | Path = CSV_PATH) -> pd.DataFrame:
    """Load CSV, drop junk columns, return a clean DataFrame."""
    df = pd.read_csv(path, index_col=0)

    # Drop Unnamed columns (artefacts of CSV export)
    unnamed = [c for c in df.columns if c.startswith("Unnamed")]
    df = df.drop(columns=unnamed)

    # Drop electron_nu.1 if it duplicates electron_nu; otherwise rename it
    if "electron_nu.1" in df.columns and "electron_nu" in df.columns:
        if df["electron_nu"].equals(df["electron_nu.1"]):
            df = df.drop(columns=["electron_nu.1"])
        else:
            df = df.rename(columns={"electron_nu.1": "electron_nu_ref"})

    return df


def classify_columns(df: pd.DataFrame) -> dict:
    """Split columns into numeric, boolean, and discrete lists.

    Returns dict with keys: 'numeric', 'bool', 'discrete'.
    Discrete columns are numeric columns with <= DISCRETE_THRESHOLD unique values.
    They appear in BOTH 'numeric' and 'discrete' lists so they can be used as
    axes or as discrete filters.
    """
    bool_cols = [c for c in df.columns if df[c].dtype == "bool"]
    numeric_cols = [c for c in df.select_dtypes(include="number").columns]
    discrete_cols = [c for c in numeric_cols if df[c].nunique() <= DISCRETE_THRESHOLD]

    return {
        "numeric": numeric_cols,
        "bool": bool_cols,
        "discrete": discrete_cols,
    }
