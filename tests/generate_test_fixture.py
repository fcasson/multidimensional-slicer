#!/usr/bin/env python3
"""Generate a small dummy CSV fixture for tests.

Produces tests/fixture.csv with 100 rows matching the structure of
IdealBallooningSamples.csv but with random values in realistic ranges.
"""

import numpy as np
import pandas as pd
from pathlib import Path

SEED = 42
N = 100

rng = np.random.default_rng(SEED)

data = {
    "q": rng.uniform(3.0, 5.0, N),
    "shat": rng.uniform(0.3, 1.2, N),
    "beta": rng.uniform(0.0005, 0.018, N),
    "gamma_exb": rng.uniform(0.0, 0.1, N),
    "electron_dens_gradient": rng.uniform(0.45, 1.22, N),
    "electron_nu": rng.uniform(0.000273, 0.000514, N),
    "betaprime": rng.uniform(-0.1, -0.003, N),
    "electron_temp_gradient": rng.uniform(0.2, 2.5, N),
    "deuterium_temp_gradient": rng.uniform(-0.77, 3.84, N),
    "isapar": rng.choice([True, False], N),
    "isbpar": rng.choice([True, False], N),
    # psi_n: 5 discrete values, 99% NaN
    "psi_n": [np.nan] * N,
    # Constant columns
    "shift": [-0.399188321] * N,
    "delta": [0.283118832] * N,
    "deltaprime": [0.292096551] * N,
    "kappa": [2.560049023] * N,
    "kappaprime": [0.015159987] * N,
    "electron_nu_ref": [0.000513856] * N,
    "betaprime_correct": rng.uniform(-0.134, -0.001, N),
    "IBMgr": rng.uniform(-0.05, -0.007, N),
}

# Sprinkle a few psi_n values
psi_n_vals = [0.3399, 0.5399, 0.6399, 0.7499, 0.8512]
for i in rng.choice(N, size=5, replace=False):
    data["psi_n"][i] = rng.choice(psi_n_vals)

df = pd.DataFrame(data)

out = Path(__file__).resolve().parent.parent / "data" / "fixture.csv"
out.parent.mkdir(exist_ok=True)
df.to_csv(out)
print(f"Wrote {len(df)} rows to {out}")
