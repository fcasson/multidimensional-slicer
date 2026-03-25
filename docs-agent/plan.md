## Plan: Interactive Multidimensional Slicer (Python)

TL;DR - Build a lightweight local Python app using Panel + Plotly/HoloViz. Use dropdowns to pick X/Y/(optional) Z, sliders to slice other dimensions, and Plotly for 2D/3D interactive scatter. Use Datashader if data grows large.

**Steps**
1. Data prep: load `IdealBallooningSamples.csv`, drop empty `Unnamed:*` cols, infer dtypes, and impute or mark missing `psi_n` values.  
2. App skeleton: create `app.py` with a Panel layout: header, controls (dropdowns, sliders, checkboxes), and plot pane.  
3. Controls: dynamic dropdowns for choosing X, Y, Z (optional); generate sliders for the remaining numeric dims; add a slider resolution and a "slice width" (tolerance) control.  
4. Plotting logic: filter dataframe by slider ranges, then render a 2D scatter (`plotly.express.scatter`) or 3D scatter (`px.scatter_3d`) depending on whether Z is selected. Color/size mapping options included.  
5. Performance: implement optional Datashader aggregation for >100k rows; otherwise use direct Plotly rendering for responsiveness.  
6. UX polish + run: add CSV reload, reset controls, axis scale toggles (linear/log) and tooltips. Provide `requirements.txt` and `README.md` with `panel serve app.py --autoreload` instructions.

**Relevant files**
- `app.py` — main Panel app, control widgets, plotting callbacks.
- `requirements.txt` — `panel`, `plotly`, `pandas`, `holoviews`, `datashader` (optional).
- `README.md` — run instructions and notes.
- `data/IdealBallooningSamples.csv` — existing dataset (move into `data/` or read from workspace root).

**Verification**
1. Run locally: `panel serve app.py --show` — confirm dropdowns populate with column names and scatter updates when sliders move.  
2. Test 3D: select a Z column and confirm `px.scatter_3d` rotates, zooms, and updates on slices.  
3. Performance test: with synthetic >200k rows, enable Datashader path and confirm responsiveness.

**Decisions & Assumptions**
- Local-only app (no auth/deployment) as requested.  
- Use Plotly for immediate 2D/3D interactivity; Panel provides simple standalone serving.  
- Dataset is currently ~1k rows — Datashader optional but included in plan if scale grows.

**Further Considerations**
1. Do you prefer `Panel` (simpler single-file local app) or `Dash` (more common for deployment)? Recommendation: `Panel` for quick local UX.  
2. Do you want preset slices or the ability to save/export current view as PNG/CSV?

