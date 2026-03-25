# Ballooning Stability — Multidimensional Slicer

Interactive exploration tool for `IdealBallooningSamples.csv` (10,000 rows of tokamak ballooning stability parameters). Built with **Panel** + **Plotly**.

## Quick Start

```bash
# Create virtual environment and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Launch the app
panel serve app.py --show --autoreload
```

The browser will open at `http://localhost:5006/app`.

## Features

- **2D / 3D scatter**: pick X, Y, and optional Z axes from 17 numeric columns
- **Colour & size mapping**: map any numeric column to point colour or size
- **Boolean filters**: toggle `isapar` / `isbpar` (Any / True / False)
- **Discrete selectors**: multi-select for low-cardinality columns like `psi_n`
- **Range sliders**: auto-generated for every continuous numeric column
- **Axis log scale**: per-axis toggle
- **CSV reload**: re-read data without restarting the server
- **Reset controls**: restore all widgets to defaults
- **Download**: export filtered data as CSV

## Running Tests

```bash
source .venv/bin/activate
python -m pytest -v
```

## Files

| File | Purpose |
|---|---|
| `app.py` | Panel app — layout, widgets, plotting |
| `data_utils.py` | Data loading, cleaning, column classification |
| `test_app.py` | App tests (widgets, filtering, plots) |
| `test_data_utils.py` | Data layer tests |
| `requirements.txt` | Python dependencies |
| `IdealBallooningSamples.csv` | Dataset |
