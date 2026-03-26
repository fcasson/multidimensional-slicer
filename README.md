# Ballooning Stability — Multidimensional Slicer

Interactive exploration tool for tokamak ideal-ballooning stability data. Built with **Panel** + **Plotly**.

![Screenshot](Screenshot.png)

## Quick Start

```bash
# Create virtual environment and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Launch the app (uses IdealBallooningSamples.csv by default)
panel serve app.py --show --autoreload

# Or point at a different CSV
SLICER_CSV=kappa_scan.csv panel serve app.py --show --autoreload
```

The browser will open at `http://localhost:5006/app`.

## Features

### Slicer Tab

- **2D / 3D scatter**: pick X, Y, and optional Z axes from all numeric columns
- **Colour & size mapping**: map any numeric column to point colour or size
- **Boolean filters**: toggle `isapar` / `isbpar` (Any / True / False)
- **Discrete selectors**: multi-select for low-cardinality columns like `psi_n`
- **Range sliders**: auto-generated for every continuous numeric column
- **Axis log scale**: per-axis toggle
- **CSV reload**: re-read data without restarting the server
- **Reset controls**: restore all widgets to defaults
- **Download**: export filtered data as CSV

### Analysis Tab

- **Pearson correlation ranking**: horizontal bar chart showing correlation of each variable with `IBMgr`, updated reactively as filters change
- **1D marginal histograms**: strip of histograms for all varying columns
- **2D pairplot**: NxN grid of `Histogram2d` (off-diagonal) and `Histogram` (diagonal) for selected columns, with selectable columns via checkbox (defaults to top 6 by correlation)

### IBMgr Generator (CLI)

- **`generate_ibmgr.py`**: command-line tool that wraps [pyrokinetics](https://github.com/pyro-kinetics/pyrokinetics) to sweep geometry parameters (elongation κ, triangularity δ) across kinetic samples
- **Parallel execution**: `--workers N` flag for multiprocessing (spawn context)
- **Incremental saves**: partial results written to CSV during long runs; safe to interrupt with Ctrl-C
- **Tested**: 2,100-point κ scan completed with 0 failures

## Running Tests

```bash
source .venv/bin/activate
python -m pytest -v
```

Tests also run automatically on push/PR via GitHub Actions.

## Files

| File | Purpose |
|---|---|
| `app.py` | Panel app — slicer + analysis tabs |
| `data_utils.py` | Data loading, cleaning, column classification |
| `ibm_generator.py` | Core library for IBMgr generation via pyrokinetics |
| `generate_ibmgr.py` | CLI wrapper for geometry-parameter scans |
| `test_app.py` | App tests (widgets, filtering, plots, analysis) |
| `test_data_utils.py` | Data layer tests |
| `test_ibm_generator.py` | Generator tests (pyrokinetics mocked) |
| `conftest.py` | Test fixture configuration |
| `requirements.txt` | Python dependencies |
