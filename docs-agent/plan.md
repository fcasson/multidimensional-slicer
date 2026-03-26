## Plan: Interactive Multidimensional Slicer (Python)

TL;DR — Build a lightweight local Python app using Panel + Plotly. Use dropdowns to pick X/Y/(optional) Z axes, sliders to slice remaining numeric dimensions, boolean checkboxes for `isapar`/`isbpar` filtering, and Plotly for 2D/3D interactive scatter. 10k rows renders comfortably in Plotly without Datashader.

---

### Dataset Profile

| Property | Value |
|---|---|
| File | `IdealBallooningSamples.csv` (workspace root) |
| Rows | 10,000 |
| Total columns | 26 (including index) |
| Numeric axes (selectable) | `q`, `shat`, `beta`, `gamma_exb`, `electron_dens_gradient`, `electron_nu`, `betaprime`, `electron_temp_gradient`, `deuterium_temp_gradient`, `psi_n`, `shift`, `delta`, `deltaprime`, `kappa`, `kappaprime`, `betaprime_correct`, `IBMgr` (17 cols) |
| Boolean filters | `isapar`, `isbpar` |
| Columns to drop | unnamed index col 0, `Unnamed: 18`–`22` |
| Columns renamed | `electron_nu.1` → `electron_nu_ref` (constant reference value, not a duplicate) |

**Notes on columns:**
- `betaprime_correct` appears to be a corrected version of `betaprime` — both are kept as selectable axes.
- `electron_nu.1` is a single constant (0.000514) across all rows — renamed to `electron_nu_ref`.
- `psi_n` has only 5 unique values and is 99.35% NaN (65/10,000 rows populated) — treated as a discrete filter with NaN passthrough.

---

### Steps

#### 1. Data prep (`data_utils.py`)
- Load CSV with `pandas.read_csv`, set col 0 as index.
- Drop `Unnamed:*` columns and `electron_nu.1` (after confirming duplication).
- Separate columns into three lists: `numeric_cols`, `bool_cols`, `discrete_cols` (for any column with ≤10 unique values, e.g. `psi_n`).
- No imputation — leave NaNs and let user see gaps (Plotly silently drops NaN points).

#### 2. App skeleton (`app.py`)
- Panel layout with three regions:
  - **Header**: title + dataset summary (row count, active filters).
  - **Sidebar**: axis selectors, colour/size mapping, boolean filters, dimension sliders.
  - **Main**: Plotly figure pane (responsive sizing).
- Wire `pn.serve()` entry point.

#### 3. Controls
- **Axis dropdowns** (`pn.widgets.Select`): X, Y, Z (Z default = `None` → 2D mode). Populate from `numeric_cols`. Prevent selecting the same column for multiple axes.
- **Colour / size dropdowns**: optional mapping to any numeric column (colour default = `q`).
- **Boolean filter checkboxes**: one per bool col (`isapar`, `isbpar`) — tri-state: True / False / Any.
- **Dimension sliders**: auto-generated `RangeSlider` for each numeric col *not* currently assigned to an axis. Include a global "slice width %" control that sets default range breadth.
- **Discrete selectors**: for columns with few unique values, use `CheckButtonGroup` widget (togglable buttons showing active state clearly).

#### 4. Plotting logic
- Filter dataframe by all active slider ranges, boolean filters, and discrete selectors.
- Display filtered-row count in header.
- If Z is `None`: `plotly.express.scatter(df, x=X, y=Y, color=C, size=S)`.
- If Z is set: `plotly.express.scatter_3d(df, x=X, y=Y, z=Z, color=C, size=S)`.
- Use `@pn.depends(...)` or `pn.bind()` to reactively update plot on any widget change.

#### 5. Performance
- At 10k rows Plotly renders in <1 s — no Datashader needed for current data.
- If dataset grows beyond ~50k rows, add a `Datashader` toggle that rasterises the scatter via `holoviews` + `datashader` pipeline and displays as an image instead of individual points.
- Use `pn.state.notifications` to warn the user if filtered data exceeds 50k rows without Datashader enabled.

#### 6. UX polish
- **CSV reload button**: re-read file on click (for updated data without restarting server).
- **Reset controls**: restore all sliders/dropdowns to defaults.
- **Axis scale toggles**: linear / log per axis.
- **Hover tooltips**: show all column values for a point on hover.
- **Export**: Plotly's built-in PNG/SVG toolbar + a "Download filtered CSV" button.

---

### Relevant Files

| File | Purpose |
|---|---|
| `gui/app.py` | Main Panel app — layout, widgets, plotting callbacks |
| `gui/data_utils.py` | Data loading, cleaning, column classification |
| `requirements.txt` | `panel`, `plotly`, `pandas`, `holoviews`, `datashader` |
| `README.md` | Run instructions (`panel serve gui/app.py --show --autoreload`) |

CSV data lives in `data/` (see Repo Structure below).

---

### Verification

1. **Startup**: `panel serve app.py --show` — dropdowns populate with 17 numeric column names; sliders appear for non-axis columns.
2. **2D mode**: Select X=`q`, Y=`shat` — scatter renders with ~10k points in <2 s.
3. **3D mode**: Set Z=`beta` — `scatter_3d` renders; rotation/zoom works.
4. **Slicing**: Move `electron_temp_gradient` slider — point count decreases, plot updates reactively.
5. **Boolean filter**: Toggle `isapar` to False — only rows with `isapar=False` shown.
6. **Discrete selector**: Deselect a `psi_n` value — corresponding rows disappear.
7. **Edge cases**: Same column selected for X and Y (should be prevented); all sliders at minimum range (empty plot, no crash); rapid widget changes (no stale callbacks).

---

### Decisions & Assumptions

- **Local-only** — no auth or deployment infra.
- **Panel over Dash** — simpler single-file serving, sufficient for local exploration. Panel's `--autoreload` flag supports live development.
- **10k rows** — well within Plotly's WebGL scatter limit (~100k). Datashader is a future optimisation, not a launch requirement.
- **No imputation** — physicist users will prefer seeing data gaps over silently filled values.
- **`q` as default colour** — safety factor gives good visual separation across the parameter space.

---

### Open Questions (Resolved)

1. ~~Should `psi_n` be treated as discrete?~~ **Yes** — auto-classified by ≤10 unique values threshold. All low-cardinality columns get `CheckButtonGroup`.
2. ~~Save/load slice presets?~~ **Not yet implemented** — deferred to future work.
3. ~~Colour scales?~~ **Default Plotly continuous scale** — no custom diverging/sequential maps yet.

---

## Phase 2: IBMgr Generator

TL;DR — CLI-driven tool that wraps pyrokinetics to sweep geometry parameters (kappa, delta) across kinetic parameter samples drawn from an existing dataset, computing ideal ballooning mode growth rates (IBMgr) for each combination. Outputs a CSV compatible with the slicer app.

### Motivation

The original `IdealBallooningSamples.csv` holds `kappa`, `delta`, `kappaprime`, `deltaprime`, `shift` constant across all 10k rows. The generator expands the parameter space by scanning kappa and delta while holding derivatives (`kappaprime`, `deltaprime`) fixed, producing new IBMgr data that can be loaded into the slicer.

### Architecture

| File | Purpose |
|---|---|
| `ibm/ibm_generator.py` | Core library — grid construction, kinetic sampling, Pyro interaction, serial & parallel solvers |
| `ibm/generate_ibmgr.py` | CLI wrapper — argument parsing, orchestration (grid-based scans) |
| `ibm/generate_kappa_delta_scan.py` | CLI for random kappa-delta scans — uniform geometry sampling, marginal kinetic sampling, `--nice` CPU throttle |
| `ibm/validate_ibmgr.py` | Cross-validation script — compares generated IBMgr values against original dataset |
| `tests/test_ibm_generator.py` | 14 tests — all pyrokinetics calls mocked |
| `data/input2.cgyro` | CGYRO template file (committed) |

### Key Design Decisions

- **CLI-first** — no GUI integration yet; output CSV can be loaded in the slicer directly.
- **Grid scan** — Cartesian product of `kappa` × `delta` values, crossed with kinetic samples.
- **Derivatives held fixed** — `kappaprime` and `deltaprime` come from the template and are not varied.
- **`enforce_consistent_beta_prime()`** — called after setting geometry parameters to keep beta_prime self-consistent. Requires pyrokinetics unstable branch (≥0.8.1.dev).
- **`_to_float()` helper** — pint Quantities must be unwrapped via `.m` (magnitude) before writing to CSV.
- **`spawn` multiprocessing context** — `fork` deadlocks with pint/numpy; all parallel work uses `mp.get_context("spawn")`.
- **Incremental saves** — partial CSV written every 200 rows + on SIGINT, so long scans are not lost on interruption.

### CLI Usage

```bash
# Template-only scan (1 kinetic sample from the template itself)
python generate_ibmgr.py --template input.cgyro --output scan.csv

# Full scan: 100 kinetic samples × 21 kappa × 1 delta = 2100 points, 8 workers
python generate_ibmgr.py --template input.cgyro \
    --base-csv IdealBallooningSamples.csv --n-samples 100 \
    --kappa-min 1.0 --kappa-max 3.0 --n-kappa 21 \
    --n-delta 1 --workers 8 --output kappa_scan.csv
```

### Key CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--template` | (required) | Path to CGYRO input file |
| `--base-csv` | None | CSV to sample kinetic parameters from |
| `--n-samples` | 100 | Number of kinetic rows to sample |
| `--seed` | 42 | Random seed for reproducibility |
| `--kappa-min/max` | 1.0 / 3.0 | Elongation range |
| `--n-kappa` | 21 | Number of kappa grid points |
| `--delta-min/max` | -0.5 / 1.0 | Triangularity range |
| `--n-delta` | 11 | Number of delta grid points |
| `--workers` | 1 | Number of parallel workers (spawn context) |
| `--output` | `ibm_scan.csv` | Output CSV path |
| `--failures-output` | `ibm_failures.csv` | Failed rows CSV path |

### First Scan Results

- **2100 points** (100 kinetic samples × 21 kappa × 1 delta)
- **0 failures** — all rows solved successfully
- **~38 minutes** with 8 workers on 8-core machine
- Output: `kappa_scan.csv` (gitignored)

### Dependencies

- `pyrokinetics ≥0.8.1.dev` from unstable branch (`pip install git+https://github.com/pyro-kinetics/pyrokinetics@unstable`)
- `pandas`, `numpy` (already in requirements.txt)

### Not Yet Implemented

- GUI integration (run from slicer sidebar)
- Automatic derivatives (kappaprime, deltaprime) — pyrokinetics does not recompute these from kappa/delta
- Appending to existing CSV (currently overwrites)

---

## Kappa-Delta Scan Generator

TL;DR — A separate scan script (`ibm/generate_kappa_delta_scan.py`) that uses uniform random sampling over the kappa-delta plane (rather than a Cartesian grid) and draws kinetic parameters from marginal distributions of the original dataset. Supports CPU throttling via `--nice` for running on shared machines.

### Sampling Strategy

- **Geometry (kappa, delta)**: uniform random within user-specified ranges.
- **Kinetic parameters**: independent marginal sampling from `IdealBallooningSamples.csv` — each kinetic column is sampled independently from its own empirical distribution.
- Both strategies are implemented in `ibm_generator.py` (`sample_uniform_geometry()`, `sample_independent_marginals()`).

### Key CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--template` | (required) | Path to CGYRO input file |
| `--base-csv` | None | CSV to sample kinetic parameters from |
| `--n-samples` | 500 | Number of random samples |
| `--seed` | 42 | Random seed |
| `--kappa-min/max` | 1.0 / 3.0 | Elongation range |
| `--delta-min/max` | -0.5 / 1.0 | Triangularity range |
| `--workers` | 1 | Parallel workers |
| `--nice` | 0 | CPU niceness (0–19) |
| `--output` | `kappa_delta_scan.csv` | Output CSV path |

### Scans Completed

| Scan | Samples | Delta range | Time | Output |
|---|---|---|---|---|
| Initial 500-sample | 500 | [-0.5, 1.0] | ~1.5 hr (8 workers) | `kappa_delta_scan.csv` (root, gitignored) |
| 5000-sample narrow | 5000 | [0.3, 0.8] | ~15 hr (8 workers, nice 10) | `data/kappa_delta_5k_narrow.csv` (committed) |

### Cross-Validation

`ibm/validate_ibmgr.py` confirmed the pipeline is correct: for the `input2.cgyro` template's geometry parameters, the generated IBMgr matches the original dataset values.

---

## Repo Structure (as of 779166f)

```
gui/                    # Slicer application
  __init__.py
  app.py                # Main Panel app
  data_utils.py         # Data loading/cleaning

ibm/                    # IBMgr generation tools
  __init__.py
  ibm_generator.py      # Core library
  generate_ibmgr.py     # Grid-based scan CLI
  generate_kappa_delta_scan.py  # Random scan CLI
  validate_ibmgr.py     # Cross-validation

data/                   # Datasets (committed, open)
  IdealBallooningSamples.csv    # Original 10k dataset
  kappa_delta_5k_narrow.csv     # 5000 samples, delta [0.3, 0.8]
  input2.cgyro                  # CGYRO template
  fixture.csv                   # 100-row test fixture

tests/                  # Test suite (53 tests)
  __init__.py
  conftest.py
  test_app.py
  test_data_utils.py
  test_ibm_generator.py
  generate_test_fixture.py

.github/workflows/tests.yml    # CI
```

### Data Files Policy

- CSV data files in `data/` are **open and committed** to git.
- `.gitignore` uses `*.csv` with `!data/*.csv` exception, and `*.cgyro` with `!data/*.cgyro` exception.
- Intermediate/scratch CSVs in the root directory remain gitignored.

---

## 3D Plot Zoom Flicker Fix (26dcaa9)

Range sliders fire `value` events continuously during drag, causing repeated plot rebuilds and resetting the 3D camera. Fixed by reading `widget.value_throttled` (fires only on mouse-up) instead of `widget.value` for range sliders. The `_filter_df()` function now uses:

```python
val = widget.value_throttled if widget.value_throttled is not None else widget.value
```

**Testing note**: `value_throttled` is a `param.Constant` on Panel widgets. Tests must temporarily unlock it:
```python
p = slider.param.value_throttled
p.constant = False
slider.value_throttled = (lo, hi)
p.constant = True
```

---

## Phase 3: Analysis Tab, Dynamic Defaults & CI

### Analysis Tab

Added a second tab ("Analysis") to the slicer with three reactive/on-demand components:

1. **Pearson correlation bar chart** — horizontal bar chart of absolute Pearson correlations of each varying column with `IBMgr`. Updates reactively on any filter change.
2. **1D marginal histograms** — strip of histograms for all varying columns (80 bins). Updates reactively.
3. **2D pairplot** — NxN grid of `Histogram2d` (off-diagonal) and `Histogram` (diagonal). On-demand via "Plot selected 2D correlations" button. Columns selectable via `CheckBoxGroup` (defaults to top 6 by correlation). Loading spinner shown while building.

Constant columns (only 1 unique value) are excluded from the analysis via `VARYING_COLS`.

### Dynamic Axis Defaults

Axis defaults now adapt to whatever CSV is loaded. The `_default()` helper tries the preferred column name and falls back to positional indexing:

```python
def _default(preferred, cols, fallback_idx=0):
    return preferred if preferred in cols else cols[fallback_idx]
```

This fixes the `ValueError` when loading `kappa_scan.csv` (which has no `betaprime_correct` column).

### 3D Camera Persistence

The slicer now uses a persistent `pn.pane.Plotly` object (`_plot_pane`) with `uirevision="keep"`. The `_update_plot` callback updates `.object` in place rather than returning a new pane, so Plotly preserves the 3D camera rotation across filter changes.

### CSV Filename in Title Bar

The `FastListTemplate` title now shows the loaded CSV filename: `f"Ballooning Stability — {CSV_PATH.name}"`.

### SLICER_CSV Environment Variable

`data_utils.py` reads `SLICER_CSV` from the environment to override the default CSV path:

```bash
SLICER_CSV=kappa_scan.csv panel serve app.py --show
```

### Test Fixture & GitHub Actions CI

- `generate_test_fixture.py` creates a 100-row dummy CSV with realistic random values.
- `tests/fixture.csv` is committed to git (`.gitignore` has `!tests/fixture.csv`).
- `conftest.py` sets `SLICER_CSV` to `tests/fixture.csv` before imports.
- `.github/workflows/tests.yml` runs all 53 tests on push/PR to master (Python 3.12, ubuntu-latest).

### Updated Files Table

| File | Purpose |
|---|---|
| `app.py` | Panel app — slicer + analysis tabs, dynamic defaults, persistent plot pane |
| `data_utils.py` | Data loading, cleaning, column classification, `SLICER_CSV` support |
| `ibm_generator.py` | Core library for IBMgr generation via pyrokinetics |
| `generate_ibmgr.py` | CLI wrapper for geometry-parameter scans |
| `test_app.py` | 29 tests — widgets, filtering, plots, analysis tab |
| `test_data_utils.py` | 10 tests — data layer |
| `test_ibm_generator.py` | 14 tests — generator (pyrokinetics mocked) |
| `conftest.py` | Test fixture configuration |
| `generate_test_fixture.py` | Creates 100-row dummy CSV |
| `tests/fixture.csv` | Test fixture dataset |
| `.github/workflows/tests.yml` | GitHub Actions CI workflow |
| `README.md` | Updated with all features, screenshot, generator docs |

