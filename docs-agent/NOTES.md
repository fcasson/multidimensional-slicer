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
