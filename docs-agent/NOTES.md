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

Axis defaults are now **dynamic** — the app prefers `shat`, `betaprime_correct`, `IBMgr`, `q` but falls back to whatever columns exist in the loaded CSV. This is handled by the `_default()` helper. The same helper is used by `_reset_controls()`.

| Setting | Preferred | Fallback |
|---|---|---|
| X axis | `shat` | First numeric column |
| Y axis | `betaprime_correct` | Second numeric column |
| Z axis | `IBMgr` | `—` (none) |
| Colour | `q` | `—` (none) |

## CSV Not in Git — OUTDATED

> **Update (779166f):** CSV data files are now committed in `data/`. The original `IdealBallooningSamples.csv`, `kappa_delta_5k_narrow.csv`, and `input2.cgyro` are all tracked. `.gitignore` uses `!data/*.csv` and `!data/*.cgyro` exceptions. Scratch CSVs in the root directory are still gitignored.

The `SLICER_CSV` environment variable overrides the default CSV path:

```bash
SLICER_CSV=data/kappa_delta_5k_narrow.csv panel serve gui/app.py --show
```

The CSV filename is displayed in the browser title bar.

## Repo Structure

As of commit 779166f, the repo is organized into subdirectories:
- `gui/` — app.py, data_utils.py
- `ibm/` — ibm_generator.py, generate_ibmgr.py, generate_kappa_delta_scan.py, validate_ibmgr.py
- `data/` — committed datasets and templates
- `tests/` — test suite (53 tests)

All imports use package-qualified paths (e.g. `from gui.data_utils import ...`, `from ibm.ibm_generator import ...`). Mock patch targets in tests also use qualified paths (e.g. `@patch("ibm.ibm_generator.Diagnostics")`).

`data_utils.py` resolves the default CSV path relative to two parents up: `Path(__file__).resolve().parent.parent / "data" / "IdealBallooningSamples.csv"`.

## Test Suite

53 tests across three files:
- `tests/test_data_utils.py` (10 tests) — loading, cleaning, column classification
- `tests/test_app.py` (29 tests) — widgets, filtering, plot building, reset, analysis tab
- `tests/test_ibm_generator.py` (14 tests) — generator tests with all pyrokinetics mocked

Tests use a 100-row fixture CSV (`data/fixture.csv`) so they run without the real dataset. The fixture is committed to git. `conftest.py` sets `SLICER_CSV` to `data/fixture.csv` before imports.

GitHub Actions CI runs all tests on push/PR to master: `python -m pytest tests/ -v`.

Run locally with: `.venv/bin/python -m pytest tests/ -v`

## 3D Plot Camera Persistence

The slicer uses a **persistent `pn.pane.Plotly`** object (`_plot_pane`) whose `.object` is updated in place, combined with `uirevision="keep"` in the Plotly layout. This preserves the 3D camera rotation when filters change.

**Do not** return a new `pn.pane.Plotly(...)` from the update function — that creates a fresh DOM element and resets the camera.

## Analysis Tab — Pairplot Performance

The pairplot builds server-side in <0.5s for 2100 rows × 6 columns (36 traces). However, browser rendering of large Plotly subplot grids can feel slow. The pairplot is on-demand (button click) to avoid blocking the UI. A `LoadingSpinner` is shown while it builds.

Default to top 6 columns by correlation to keep the grid manageable.

## Not Yet Implemented (from plan)

- Prevent same column on multiple axes (planned but not enforced)
- Global "slice width %" control
- Datashader path (not needed at 10k rows)
- Save/load slice presets
- GUI integration for IBMgr generation (run from slicer sidebar)

---

## 3D Plot Zoom Flicker — Critical (Fixed 26dcaa9)

Range sliders fire `value` events continuously during drag, rebuilding the plot and resetting the 3D camera. Fixed by using `value_throttled` (fires only on mouse-up):

```python
val = widget.value_throttled if widget.value_throttled is not None else widget.value
```

**Testing gotcha**: `value_throttled` is a `param.Constant` on Panel RangeSlider widgets. To set it in tests:
```python
p = slider.param.value_throttled
p.constant = False
slider.value_throttled = (lo, hi)
p.constant = True
```

Do not simply assign `slider.value_throttled = ...` without unlocking — it will raise an error.

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
| Kappa-only grid (21 × 100 kinetic) | 2100 | 8 | ~38 min | 0 |
| Kappa-delta random 500 | 500 | 8 | ~1.5 hr | 0 |
| Kappa-delta narrow 5k (delta 0.3–0.8) | 5000 | 8 (nice 10) | ~15 hr | 0 |

Rate: ~55 points/min with 8 workers on 8-core machine. Startup overhead is ~40s per scan (template loading in each spawn worker).

### CPU Throttling (--nice)

`generate_kappa_delta_scan.py` accepts `--nice N` (0–19) to call `os.nice(N)` before starting workers. Useful on shared machines. The 5k narrow scan was run with `--nice 10`.

### Test Suite

14 tests in `tests/test_ibm_generator.py`:
- All pyrokinetics calls are mocked (`Diagnostics`, `load_template`)
- Mock patch targets use qualified paths: `@patch("ibm.ibm_generator.Diagnostics")`, `@patch("ibm.generate_ibmgr.run_ibm_scan_parallel")`
- Tests cover: geometry grid, kinetic sampling, scan dataframe construction, serial scan (success/failure/mixed), CLI argument handling
- Run with: `.venv/bin/python -m pytest tests/test_ibm_generator.py -v`

### Output CSV Format

The output CSV has the same columns as `IdealBallooningSamples.csv` (all kinetic + geometry parameters + `IBMgr`), making it directly loadable in the slicer app. Failed rows (if any) are written to a separate failures CSV with an additional `error` column.
