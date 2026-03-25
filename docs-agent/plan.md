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
| Columns to drop | unnamed index col 0, `Unnamed: 18`–`22`, `electron_nu.1` (duplicate of `electron_nu`) |

**Notes on columns:**
- `betaprime_correct` appears to be a corrected version of `betaprime` — keep both and let the user choose, but default colour-mapping to `betaprime_correct`.
- `electron_nu.1` has identical values to `electron_nu` in sampled rows — verify at load time and drop if duplicate.
- `psi_n` takes a small set of discrete values (e.g. 0.536, 0.637, 0.851) — may be better as a discrete selector than a continuous slider.

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
- **Colour / size dropdowns**: optional mapping to any numeric column (colour default = `betaprime_correct`).
- **Boolean filter checkboxes**: one per bool col (`isapar`, `isbpar`) — tri-state: True / False / Any.
- **Dimension sliders**: auto-generated `RangeSlider` for each numeric col *not* currently assigned to an axis. Include a global "slice width %" control that sets default range breadth.
- **Discrete selectors**: for columns like `psi_n` with few unique values, use `MultiChoice` widget instead of a slider.

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
| `app.py` | Main Panel app — layout, widgets, plotting callbacks |
| `data_utils.py` | Data loading, cleaning, column classification |
| `requirements.txt` | `panel`, `plotly`, `pandas`, `holoviews`, `datashader` |
| `README.md` | Run instructions (`panel serve app.py --show --autoreload`) |

The CSV stays at the workspace root (`IdealBallooningSamples.csv`) — no need to move it.

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
- **`betaprime_correct` as default colour** — it's the corrected physics quantity and varies across the full range.

---

### Open Questions

1. Should `psi_n` (and any other low-cardinality column) be treated as a discrete filter by default, or should the user choose?
2. Do you want the ability to **save/load slice presets** (JSON file with widget states) for reproducible views?
3. Any preferred **colour scales** for the physics quantities (e.g. diverging for `betaprime_correct`, sequential for `IBMgr`)?

