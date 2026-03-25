"""Core library for generating ideal ballooning mode growth rate data.

Wraps pyrokinetics to sweep geometry parameters (kappa, delta) across
kinetic parameter samples drawn from an existing dataset or the template.
"""

import itertools
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pyrokinetics import Pyro
from pyrokinetics.diagnostics import Diagnostics

logger = logging.getLogger(__name__)

# Columns in the base CSV that map to Pyro attributes
KINETIC_COLS = [
    "beta",
    "q",
    "shat",
    "electron_temp_gradient",
    "electron_dens_gradient",
    "deuterium_temp_gradient",
    "electron_nu",
]


def load_template(template_path: str | Path) -> Pyro:
    """Load a CGYRO template file and return a Pyro object."""
    return Pyro(gk_file=str(template_path), gk_type="CGYRO")


def make_geometry_grid(
    kappa_min: float = 1.0,
    kappa_max: float = 3.0,
    n_kappa: int = 11,
    delta_min: float = -0.5,
    delta_max: float = 1.0,
    n_delta: int = 11,
) -> pd.DataFrame:
    """Create a regular grid over kappa and delta.

    Returns a DataFrame with columns ['kappa', 'delta'].
    """
    kappas = np.linspace(kappa_min, kappa_max, n_kappa)
    deltas = np.linspace(delta_min, delta_max, n_delta)
    grid = list(itertools.product(kappas, deltas))
    return pd.DataFrame(grid, columns=["kappa", "delta"])


def sample_base_rows(
    base_csv: str | Path,
    n_samples: int | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Sample kinetic parameter rows from an existing dataset.

    If n_samples is None, use all rows.  Returns only the KINETIC_COLS subset.
    """
    df = pd.read_csv(base_csv, index_col=0)
    # Keep only the kinetic columns that exist
    available = [c for c in KINETIC_COLS if c in df.columns]
    df = df[available].dropna()
    if n_samples is not None and n_samples < len(df):
        df = df.sample(n=n_samples, random_state=seed)
    return df.reset_index(drop=True)


def kinetic_rows_from_template(pyro: Pyro) -> pd.DataFrame:
    """Extract a single kinetic parameter row from the loaded template."""
    row = {
        "beta": float(pyro.numerics.beta),
        "q": float(pyro.local_geometry.q),
        "shat": float(pyro.local_geometry.shat),
        "electron_temp_gradient": float(
            pyro.local_species["electron"].inverse_lt
        ),
        "electron_dens_gradient": float(
            pyro.local_species["electron"].inverse_ln
        ),
        "deuterium_temp_gradient": float(
            pyro.local_species["ion1"].inverse_lt
        ),
        "electron_nu": float(pyro.local_species["ion1"].nu),
    }
    return pd.DataFrame([row])


def build_scan_dataframe(
    kinetic_rows: pd.DataFrame,
    geometry_grid: pd.DataFrame,
) -> pd.DataFrame:
    """Cross-product of kinetic rows with geometry grid points."""
    kinetic_rows = kinetic_rows.copy()
    geometry_grid = geometry_grid.copy()
    kinetic_rows["_merge"] = 1
    geometry_grid["_merge"] = 1
    combined = kinetic_rows.merge(geometry_grid, on="_merge").drop(columns="_merge")
    return combined.reset_index(drop=True)


def _apply_row_to_pyro(pyro: Pyro, row: pd.Series) -> None:
    """Write a scan row's parameters into the Pyro object."""
    pyro.numerics.beta = row["beta"]
    pyro.local_geometry.q = row["q"]
    pyro.local_geometry.shat = row["shat"]
    pyro.local_geometry.kappa = row["kappa"]
    pyro.local_geometry.delta = row["delta"]
    # kappaprime and deltaprime held at template values (not modified)

    pyro.local_species["electron"].inverse_lt = row["electron_temp_gradient"]
    pyro.local_species["electron"].inverse_ln = row["electron_dens_gradient"]
    pyro.local_species["ion1"].inverse_lt = row["deuterium_temp_gradient"]
    pyro.local_species["ion1"].inverse_ln = row["electron_dens_gradient"]
    pyro.local_species["ion1"].nu = row["electron_nu"]

    pyro.enforce_consistent_beta_prime()


def run_ibm_scan(
    template_path: str | Path,
    scan_df: pd.DataFrame,
    progress: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the ideal ballooning solver for every row in scan_df.

    Returns (results_df, failures_df).
    results_df has all input columns plus IBMgr, isIBMunstable, beta_prime.
    failures_df has the same input columns plus an 'error' column.
    """
    pyro = load_template(template_path)
    n = len(scan_df)

    results = []
    failures = []

    for i, (idx, row) in enumerate(scan_df.iterrows()):
        if progress and (i % 50 == 0 or i == n - 1):
            logger.info("Processing row %d / %d", i + 1, n)

        try:
            _apply_row_to_pyro(pyro, row)
            beta_prime = float(pyro.local_geometry.beta_prime)

            diag = Diagnostics(pyro)
            ibmgr = float(diag.ideal_ballooning_solver())

            result = row.to_dict()
            result["beta_prime"] = beta_prime
            result["IBMgr"] = ibmgr
            result["isIBMunstable"] = ibmgr > 0
            results.append(result)

        except Exception as exc:
            failure = row.to_dict()
            failure["error"] = str(exc)
            failures.append(failure)
            logger.warning("Row %d failed: %s", i, exc)

    results_df = pd.DataFrame(results)
    failures_df = pd.DataFrame(failures)

    # Add run metadata
    ts = datetime.now(timezone.utc).isoformat()
    results_df["run_timestamp"] = ts
    if not failures_df.empty:
        failures_df["run_timestamp"] = ts

    return results_df, failures_df
