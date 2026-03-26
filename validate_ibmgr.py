#!/usr/bin/env python3
"""Validate IBMgr generator against the original IdealBallooningSamples.csv.

Picks a few rows from the original CSV, reproduces them via pyrokinetics
(same workflow as the notebook), and compares IBMgr and beta_prime.
"""

import pandas as pd
from pyrokinetics import Pyro
from pyrokinetics.diagnostics import Diagnostics

TEMPLATE = "input2.cgyro"
ORIGINAL_CSV = "IdealBallooningSamples.csv"
N_TEST = 10  # number of rows to validate


def reproduce_row(pyro: Pyro, row: pd.Series) -> dict:
    """Apply one row's kinetic parameters and solve IBMgr.

    Mimics the original notebook workflow exactly.
    """
    # Set kinetic parameters (same as notebook)
    pyro.numerics.beta = row["beta"]
    pyro.local_geometry.q = row["q"]
    pyro.local_geometry.shat = row["shat"]

    pyro.local_species["electron"].inverse_lt = row["electron_temp_gradient"]
    pyro.local_species["electron"].inverse_ln = row["electron_dens_gradient"]
    pyro.local_species["ion1"].inverse_lt = row["deuterium_temp_gradient"]
    pyro.local_species["ion1"].inverse_ln = row["electron_dens_gradient"]
    pyro.local_species["ion1"].nu = row["electron_nu"]

    # Do NOT set kappa, delta, shift — keep template values (matches notebook)

    print(f"  QN check: {pyro.local_species.check_quasineutrality()}")

    pyro.enforce_consistent_beta_prime()
    bp = pyro.local_geometry.beta_prime.m

    diag = Diagnostics(pyro)
    ibmgr = diag.ideal_ballooning_solver()

    return {"beta_prime_computed": bp, "IBMgr_computed": ibmgr}


def main():
    df = pd.read_csv(ORIGINAL_CSV, index_col=0)
    test_rows = df.head(N_TEST)

    pyro = Pyro(gk_file=TEMPLATE, gk_type="CGYRO")

    # Show template geometry for reference
    print(f"Template kappa: {pyro.local_geometry.kappa}")
    print(f"Template delta: {pyro.local_geometry.delta}")
    print(f"Template shift: {pyro.local_geometry.shift}")
    print()

    results = []
    for idx, row in test_rows.iterrows():
        print(f"Row {idx}:")
        result = reproduce_row(pyro, row)

        bp_orig = row["betaprime_correct"]
        ibmgr_orig = row["IBMgr"]
        bp_err = abs(result["beta_prime_computed"] - bp_orig)
        ibmgr_err = abs(result["IBMgr_computed"] - ibmgr_orig)

        print(f"  beta_prime: original={bp_orig:.6f}  computed={result['beta_prime_computed']:.6f}  err={bp_err:.2e}")
        print(f"  IBMgr:      original={ibmgr_orig:.6f}  computed={result['IBMgr_computed']:.6f}  err={ibmgr_err:.2e}")
        print()

        results.append({
            "idx": idx,
            "bp_orig": bp_orig,
            "bp_computed": result["beta_prime_computed"],
            "bp_err": bp_err,
            "ibmgr_orig": ibmgr_orig,
            "ibmgr_computed": result["IBMgr_computed"],
            "ibmgr_err": ibmgr_err,
        })

    rdf = pd.DataFrame(results)
    print("=== Summary ===")
    print(f"Max beta_prime error: {rdf['bp_err'].max():.2e}")
    print(f"Max IBMgr error:      {rdf['ibmgr_err'].max():.2e}")
    print(f"Mean beta_prime error: {rdf['bp_err'].mean():.2e}")
    print(f"Mean IBMgr error:      {rdf['ibmgr_err'].mean():.2e}")


if __name__ == "__main__":
    main()
