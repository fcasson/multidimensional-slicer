# Implementation Notes & Gotchas

Discovered during the initial build. Read this before modifying the app.

## Dataset Surprises

- **`electron_nu.1` is NOT a duplicate of `electron_nu`** — it's a single constant value (0.000514) across all 10k rows, likely a reference/nominal value. It was renamed to `electron_nu_ref` in `data_utils.py`, not dropped.
- **`psi_n` is 99.35% NaN** — only 65 of 10,000 rows have a non-NaN value. The 5 discrete values are: ~0.34, ~0.54, ~0.64, ~0.75, ~0.85.
- **`isapar` is `True` for all rows** in the current dataset. The filter exists but currently has no practical effect.
- **Six columns are constant** across the dataset: `shift`, `delta`, `deltaprime`, `kappa`, `kappaprime`, `electron_nu_ref`. These all fall into the discrete classifier (≤10 unique values) and appear as `CheckButtonGroup` filters.

## NaN Handling — Critical

Filters must pass through NaN rows, otherwise most data vanishes (because `psi_n` NaN causes `isin()` to exclude 9,935 rows). Both discrete and range filters use `| DF[col].isna()` to preserve NaN rows. **Do not remove this without understanding the psi_n distribution.**

## Panel + FastListTemplate

- **Theme toggle was disabled** (`theme_toggle=False`) — toggling dark/light mode causes a full page re-render that resets all widget state. The Plotly template is hardcoded to `plotly_white` anyway.
- **`panel serve --autoreload`** requires `watchfiles` package (optional, not in requirements.txt). Without it, a deprecation warning appears but autoreload still works via the legacy watcher.

## Column Classification

`classify_columns()` uses a threshold of ≤10 unique values to classify numeric columns as "discrete". These columns appear in both `numeric` (usable as axes) and `discrete` (get `CheckButtonGroup` widgets). Current discrete columns: `psi_n`, `shift`, `delta`, `deltaprime`, `kappa`, `kappaprime`, `electron_nu_ref`.

## Defaults

| Setting | Value | Rationale |
|---|---|---|
| X axis | `shat` | Magnetic shear — key ballooning parameter |
| Y axis | `betaprime_correct` | Corrected pressure gradient |
| Z axis | `IBMgr` | Ideal ballooning mode growth rate (the target quantity) |
| Colour | `q` | Safety factor — gives good visual separation |

## CSV Not in Git

The CSV file (`IdealBallooningSamples.csv`) is in `.gitignore`. It must be placed at the workspace root manually. `data_utils.py` resolves the path relative to its own location via `Path(__file__).resolve().parent`.

## Test Suite

25 tests across two files:
- `test_data_utils.py` (10 tests) — loading, cleaning, column classification
- `test_app.py` (15 tests) — widgets, filtering, plot building, reset

Run with: `.venv/bin/python -m pytest -v`

## Not Yet Implemented (from plan)

- Prevent same column on multiple axes (planned but not enforced)
- Global "slice width %" control
- Axis scale toggles work but aren't prominent in the UI
- Datashader path (not needed at 10k rows)
- Save/load slice presets

---

## IBMgr Generator

### pyrokinetics Version

The released pyrokinetics 0.8.0 **does not** have `Pyro.enforce_consistent_beta_prime()`. This method was added in PR #499 and is only available on the `unstable` branch:

```bash
pip install git+https://github.com/pyro-kinetics/pyrokinetics@unstable
```

Current installed version: `0.8.1.dev421`. **Do not downgrade to 0.8.0** — the generator will break.

### Pint Quantities — Critical

Pyrokinetics attributes (e.g. `pyro.numerics.beta`, `pyro.local_geometry.kappa`) are **pint Quantities**, not plain floats. Calling `float()` on them raises `pint.errors.DimensionalityError`. The `_to_float()` helper in `ibm_generator.py` extracts the magnitude via `.m`:

```python
def _to_float(val) -> float:
    return float(getattr(val, "m", val))
```

**Always use `_to_float()`** when extracting numeric values from Pyro objects for CSV output.

### Multiprocessing — Must Use `spawn`

The default `fork` context deadlocks when pyrokinetics/pint/numpy are in use. The generator explicitly uses `mp.get_context("spawn")`. **Do not switch back to fork.**

The `spawn` context requires all worker arguments to be picklable. The Pyro template is **not** passed to workers — instead, each worker loads it from disk via a lazy-init cache (`_TEMPLATE_CACHE` dict keyed by path).

### electron_nu Mapping

In the original notebook (`createInputFiles.ipynb`), `pyro.local_species['ion1'].nu = row.electron_nu`. This maps the `electron_nu` column to the ion1 collision frequency. The generator reproduces this mapping — do not change it without understanding the physics context.

### Incremental Saves & SIGINT

- `_flush_partial()` writes completed rows to the output CSV even mid-scan.
- `flush_every=200` by default — writes every 200 completed rows.
- SIGINT handler catches Ctrl+C, flushes remaining results, and exits cleanly.
- Works in both serial (`run_ibm_scan`) and parallel (`run_ibm_scan_parallel`) paths.

### Performance Baseline

| Scan | Points | Workers | Time | Failures |
|---|---|---|---|---|
| Kappa-only (21 × 100 kinetic) | 2100 | 8 | ~38 min | 0 |

Rate: ~55 points/min with 8 workers on 8-core machine. Startup overhead is ~40s per scan (template loading in each spawn worker).

### Test Suite

14 tests in `test_ibm_generator.py`:
- All pyrokinetics calls are mocked (`Diagnostics`, `load_template`)
- Tests cover: geometry grid, kinetic sampling, scan dataframe construction, serial scan (success/failure/mixed), CLI argument handling
- Run with: `.venv/bin/python -m pytest test_ibm_generator.py -v`

### Output CSV Format

The output CSV has the same columns as `IdealBallooningSamples.csv` (all kinetic + geometry parameters + `IBMgr`), making it directly loadable in the slicer app. Failed rows (if any) are written to a separate failures CSV with an additional `error` column.
