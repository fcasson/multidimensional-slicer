#!/usr/bin/env python3
"""Generate a kappa-delta scan with kinetic params from original data.

Samples kinetic parameters (q, shat, beta, electron_dens_gradient,
electron_temp_gradient, deuterium_temp_gradient) from the empirical
marginal distributions of the original dataset.  Kappa and delta are
sampled from uniform distributions.  Collisionality and gamma_exb are
dropped — they have no effect on IBMgr.

Examples
--------
    python generate_kappa_delta_scan.py \
        --template input2.cgyro \
        --base-csv IdealBallooningSamples.csv \
        --n-samples 500 \
        --output kappa_delta_scan.csv

    # Custom geometry ranges:
    python generate_kappa_delta_scan.py \
        --template input2.cgyro \
        --base-csv IdealBallooningSamples.csv \
        --n-samples 500 \
        --kappa-min 1.0 --kappa-max 3.0 \
        --delta-min -0.5 --delta-max 1.0 \
        --output kappa_delta_scan.csv
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

from ibm_generator import (
    run_ibm_scan_parallel,
    sample_independent_marginals,
    sample_uniform_geometry,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate kappa-delta scan with kinetic params from original data."
    )

    p.add_argument(
        "--template", type=Path, required=True,
        help="Path to CGYRO template input file.",
    )
    p.add_argument(
        "--base-csv", type=Path, required=True,
        help="CSV of kinetic parameters to sample from.",
    )
    p.add_argument(
        "--n-samples", type=int, default=500,
        help="Number of scan points to generate (default: 500).",
    )
    p.add_argument("--seed", type=int, default=42, help="Random seed.")

    # Geometry ranges
    p.add_argument("--kappa-min", type=float, default=1.0)
    p.add_argument("--kappa-max", type=float, default=3.0)
    p.add_argument("--delta-min", type=float, default=-0.5)
    p.add_argument("--delta-max", type=float, default=1.0)

    # Output / execution
    p.add_argument(
        "--output", type=Path, required=True,
        help="Path for output CSV.",
    )
    p.add_argument(
        "--workers", type=int, default=1,
        help="Number of parallel workers (default: 1 = serial).",
    )
    p.add_argument(
        "--nice", type=int, default=0,
        help="Increase process niceness (0-19, higher = lower priority).",
    )

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.nice > 0:
        os.nice(args.nice)
        logger.info("Process niceness increased by %d", args.nice)

    if not args.template.exists():
        logger.error("Template file not found: %s", args.template)
        return 1
    if not args.base_csv.exists():
        logger.error("Base CSV not found: %s", args.base_csv)
        return 1

    # Sample kinetic parameters from empirical marginals
    kinetic = sample_independent_marginals(
        args.base_csv, args.n_samples, seed=args.seed,
    )
    logger.info("Sampled %d kinetic parameter rows (6 dims)", len(kinetic))

    # Sample kappa and delta uniformly
    geometry = sample_uniform_geometry(
        args.n_samples,
        kappa_min=args.kappa_min, kappa_max=args.kappa_max,
        delta_min=args.delta_min, delta_max=args.delta_max,
        seed=args.seed + 1,
    )
    logger.info(
        "Sampled geometry: kappa [%.1f, %.1f], delta [%.1f, %.1f]",
        args.kappa_min, args.kappa_max, args.delta_min, args.delta_max,
    )

    # Combine row-wise (no cross product — each sample is independent)
    scan_df = pd.concat([kinetic, geometry], axis=1)
    logger.info("Total scan points: %d  (8 dimensions)", len(scan_df))

    # Run solver
    results, failures = run_ibm_scan_parallel(
        args.template, scan_df, workers=args.workers,
        output_path=args.output,
    )

    # Save
    results.to_csv(args.output, index=False)
    logger.info("Results written to %s (%d rows)", args.output, len(results))

    if not failures.empty:
        fail_path = args.output.with_name(args.output.stem + "_failures.csv")
        failures.to_csv(fail_path, index=False)
        logger.warning("Failures written to %s (%d rows)", fail_path, len(failures))

    return 0


if __name__ == "__main__":
    sys.exit(main())
