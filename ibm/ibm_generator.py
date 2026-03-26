"""Core library for generating ideal ballooning mode growth rate data.

Wraps pyrokinetics to sweep geometry parameters (kappa, delta) across
kinetic parameter samples drawn from an existing dataset or the template.
"""

import itertools
import logging
import multiprocessing as mp
import signal
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
from pyrokinetics import Pyro
from pyrokinetics.diagnostics import Diagnostics

logger = logging.getLogger(__name__)


def _to_float(val) -> float:
    """Extract a plain float from a value that may be a pint Quantity."""
    return float(getattr(val, "m", val))


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
        "beta": _to_float(pyro.numerics.beta),
        "q": _to_float(pyro.local_geometry.q),
        "shat": _to_float(pyro.local_geometry.shat),
        "electron_temp_gradient": _to_float(
            pyro.local_species["electron"].inverse_lt
        ),
        "electron_dens_gradient": _to_float(
            pyro.local_species["electron"].inverse_ln
        ),
        "deuterium_temp_gradient": _to_float(
            pyro.local_species["ion1"].inverse_lt
        ),
        "electron_nu": _to_float(pyro.local_species["ion1"].nu),
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
    if "electron_nu" in row.index:
        pyro.local_species["ion1"].nu = row["electron_nu"]

    pyro.enforce_consistent_beta_prime()


def _flush_partial(results: list, failures: list, output_path: Path | None) -> None:
    """Write whatever results we have so far to a partial CSV."""
    if output_path is None or not results:
        return
    ts = datetime.now(timezone.utc).isoformat()
    df = pd.DataFrame(results)
    df["run_timestamp"] = ts
    df.to_csv(output_path, index=False)
    logger.info("Flushed %d results to %s", len(df), output_path)
    if failures:
        fail_path = output_path.with_name(output_path.stem + "_failures.csv")
        fdf = pd.DataFrame(failures)
        fdf["run_timestamp"] = ts
        fdf.to_csv(fail_path, index=False)


def run_ibm_scan(
    template_path: str | Path,
    scan_df: pd.DataFrame,
    progress: bool = True,
    output_path: Path | None = None,
    flush_every: int = 200,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the ideal ballooning solver for every row in scan_df.

    Returns (results_df, failures_df).
    results_df has all input columns plus IBMgr, isIBMunstable, beta_prime.
    failures_df has the same input columns plus an 'error' column.

    If output_path is set, partial results are flushed every flush_every rows
    and on SIGINT so that progress is never lost.
    """
    pyro = load_template(template_path)
    n = len(scan_df)

    results = []
    failures = []
    interrupted = False

    def _handle_sigint(sig, frame):
        nonlocal interrupted
        logger.warning("SIGINT received — writing partial results and stopping")
        interrupted = True

    prev_handler = signal.signal(signal.SIGINT, _handle_sigint)

    try:
        for i, (idx, row) in enumerate(scan_df.iterrows()):
            if interrupted:
                break

            if progress and (i % 50 == 0 or i == n - 1):
                logger.info("Processing row %d / %d", i + 1, n)

            try:
                _apply_row_to_pyro(pyro, row)
                beta_prime = _to_float(pyro.local_geometry.beta_prime)

                diag = Diagnostics(pyro)
                ibmgr = _to_float(diag.ideal_ballooning_solver())

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

            if output_path and (i + 1) % flush_every == 0:
                _flush_partial(results, failures, output_path)
    finally:
        signal.signal(signal.SIGINT, prev_handler)

    results_df = pd.DataFrame(results)
    failures_df = pd.DataFrame(failures)

    # Add run metadata
    ts = datetime.now(timezone.utc).isoformat()
    results_df["run_timestamp"] = ts
    if not failures_df.empty:
        failures_df["run_timestamp"] = ts

    return results_df, failures_df


def _solve_single_row(row_dict: dict, template_path: str) -> dict:
    """Worker function for multiprocessing — runs one solver call.

    Takes and returns plain dicts so they are picklable across processes.
    Each worker loads its own Pyro instance (not shared across processes).
    """
    # Lazy per-worker template cache via function attribute
    if not hasattr(_solve_single_row, "_pyro_cache"):
        _solve_single_row._pyro_cache = {}
    if template_path not in _solve_single_row._pyro_cache:
        _solve_single_row._pyro_cache[template_path] = load_template(template_path)
    pyro = _solve_single_row._pyro_cache[template_path]

    row = pd.Series(row_dict)
    try:
        _apply_row_to_pyro(pyro, row)
        beta_prime = _to_float(pyro.local_geometry.beta_prime)
        diag = Diagnostics(pyro)
        ibmgr = _to_float(diag.ideal_ballooning_solver())

        result = dict(row_dict)
        result["beta_prime"] = beta_prime
        result["IBMgr"] = ibmgr
        result["isIBMunstable"] = ibmgr > 0
        return {"ok": True, "data": result}
    except Exception as exc:
        failure = dict(row_dict)
        failure["error"] = str(exc)
        return {"ok": False, "data": failure}


def run_ibm_scan_parallel(
    template_path: str | Path,
    scan_df: pd.DataFrame,
    workers: int = 1,
    progress: bool = True,
    output_path: Path | None = None,
    flush_every: int = 200,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the ideal ballooning solver in parallel using multiprocessing.

    Falls back to serial run_ibm_scan when workers=1.
    If output_path is set, partial results are flushed periodically and on
    SIGINT so that progress is never lost.
    """
    if workers <= 1:
        return run_ibm_scan(
            template_path, scan_df, progress=progress,
            output_path=output_path, flush_every=flush_every,
        )

    template_str = str(template_path)
    row_dicts = [row.to_dict() for _, row in scan_df.iterrows()]
    n = len(row_dicts)
    logger.info("Starting parallel scan: %d points across %d workers", n, workers)

    results = []
    failures = []
    interrupted = False

    def _handle_sigint(sig, frame):
        nonlocal interrupted
        logger.warning("SIGINT received — writing partial results and stopping")
        interrupted = True

    prev_handler = signal.signal(signal.SIGINT, _handle_sigint)
    worker_fn = partial(_solve_single_row, template_path=template_str)

    try:
        # Use 'spawn' context to avoid fork-safety issues with pint/numpy
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=workers) as pool:
            for i, outcome in enumerate(pool.imap_unordered(worker_fn, row_dicts)):
                if interrupted:
                    pool.terminate()
                    break
                if progress and (i % 200 == 0 or i == n - 1):
                    logger.info("Completed %d / %d", i + 1, n)
                if outcome["ok"]:
                    results.append(outcome["data"])
                else:
                    failures.append(outcome["data"])
                    logger.warning("Row failed: %s", outcome["data"].get("error", "?"))
                if output_path and (i + 1) % flush_every == 0:
                    _flush_partial(results, failures, output_path)
    finally:
        signal.signal(signal.SIGINT, prev_handler)

    results_df = pd.DataFrame(results)
    failures_df = pd.DataFrame(failures)

    ts = datetime.now(timezone.utc).isoformat()
    results_df["run_timestamp"] = ts
    if not failures_df.empty:
        failures_df["run_timestamp"] = ts

    return results_df, failures_df


# ---------------------------------------------------------------------------
# Sampling helpers for independent-marginal + uniform-geometry scans
# ---------------------------------------------------------------------------

KINETIC_COLS_NO_COLLISIONS = [
    "beta",
    "q",
    "shat",
    "electron_temp_gradient",
    "electron_dens_gradient",
    "deuterium_temp_gradient",
]


def sample_independent_marginals(
    base_csv: str | Path,
    n_samples: int,
    columns: list[str] | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Sample from empirical marginal distributions independently.

    For each column, draws *n_samples* values with replacement from the
    original data.  Columns are sampled independently, which breaks
    inter-parameter correlations but gives better space-filling coverage.
    """
    rng = np.random.default_rng(seed)
    df = pd.read_csv(base_csv, index_col=0)
    if columns is None:
        columns = KINETIC_COLS_NO_COLLISIONS
    available = [c for c in columns if c in df.columns]
    result = {}
    for col in available:
        values = df[col].dropna().values
        result[col] = rng.choice(values, size=n_samples, replace=True)
    return pd.DataFrame(result)


def sample_uniform_geometry(
    n_samples: int,
    kappa_min: float = 1.0,
    kappa_max: float = 3.0,
    delta_min: float = -0.5,
    delta_max: float = 1.0,
    seed: int = 43,
) -> pd.DataFrame:
    """Sample kappa and delta from independent uniform distributions."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "kappa": rng.uniform(kappa_min, kappa_max, n_samples),
        "delta": rng.uniform(delta_min, delta_max, n_samples),
    })
