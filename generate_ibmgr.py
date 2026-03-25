#!/usr/bin/env python3
"""CLI for generating ideal ballooning mode growth rate scans.

Examples
--------
Scan kappa/delta using template kinetic parameters only:

    python generate_ibmgr.py --template input.cgyro --output scan_results.csv

Scan using kinetic samples from an existing dataset:

    python generate_ibmgr.py --template input.cgyro \
        --base-csv IdealBallooningSamples.csv --n-samples 50 \
        --kappa-min 1.0 --kappa-max 3.0 --n-kappa 11 \
        --delta-min -0.5 --delta-max 1.0 --n-delta 11 \
        --output scan_results.csv
"""

import argparse
import logging
import sys
from pathlib import Path

from ibm_generator import (
    build_scan_dataframe,
    kinetic_rows_from_template,
    load_template,
    make_geometry_grid,
    run_ibm_scan_parallel,
    sample_base_rows,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate ideal ballooning mode growth rate data."
    )

    p.add_argument(
        "--template",
        type=Path,
        required=True,
        help="Path to CGYRO template input file.",
    )
    p.add_argument(
        "--base-csv",
        type=Path,
        default=None,
        help="Optional CSV of kinetic parameters to sample from. "
        "If omitted, template values are used as the single reference point.",
    )
    p.add_argument(
        "--n-samples",
        type=int,
        default=None,
        help="Number of rows to sample from base CSV (default: all).",
    )
    p.add_argument("--seed", type=int, default=42, help="Random seed for sampling.")

    # Geometry grid
    p.add_argument("--kappa-min", type=float, default=1.0)
    p.add_argument("--kappa-max", type=float, default=3.0)
    p.add_argument("--n-kappa", type=int, default=11)
    p.add_argument("--delta-min", type=float, default=-0.5)
    p.add_argument("--delta-max", type=float, default=1.0)
    p.add_argument("--n-delta", type=int, default=11)

    # Output
    p.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for output CSV.",
    )
    p.add_argument(
        "--failures-output",
        type=Path,
        default=None,
        help="Path for failures CSV (default: <output>_failures.csv).",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1 = serial).",
    )

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Validate inputs
    if not args.template.exists():
        logger.error("Template file not found: %s", args.template)
        return 1
    if args.base_csv and not args.base_csv.exists():
        logger.error("Base CSV not found: %s", args.base_csv)
        return 1

    # Build kinetic rows
    if args.base_csv:
        logger.info("Sampling kinetic parameters from %s", args.base_csv)
        kinetic_rows = sample_base_rows(args.base_csv, args.n_samples, args.seed)
        logger.info("Using %d kinetic parameter rows", len(kinetic_rows))
    else:
        logger.info("Using template kinetic parameters (single reference point)")
        pyro = load_template(args.template)
        kinetic_rows = kinetic_rows_from_template(pyro)

    # Build geometry grid
    grid = make_geometry_grid(
        kappa_min=args.kappa_min,
        kappa_max=args.kappa_max,
        n_kappa=args.n_kappa,
        delta_min=args.delta_min,
        delta_max=args.delta_max,
        n_delta=args.n_delta,
    )
    logger.info(
        "Geometry grid: %d kappa x %d delta = %d points",
        args.n_kappa,
        args.n_delta,
        len(grid),
    )

    # Cross product
    scan_df = build_scan_dataframe(kinetic_rows, grid)
    logger.info("Total scan points: %d", len(scan_df))

    # Run
    results, failures = run_ibm_scan_parallel(
        args.template, scan_df, workers=args.workers,
        output_path=args.output,
    )

    # Save
    results.to_csv(args.output, index=False)
    logger.info("Results written to %s (%d rows)", args.output, len(results))

    if not failures.empty:
        fail_path = args.failures_output or args.output.with_name(
            args.output.stem + "_failures.csv"
        )
        failures.to_csv(fail_path, index=False)
        logger.warning("Failures written to %s (%d rows)", fail_path, len(failures))

    return 0


if __name__ == "__main__":
    sys.exit(main())
