"""Interactive Multidimensional Slicer — Panel + Plotly app."""

import panel as pn
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd

from data_utils import CSV_PATH, load_and_clean, classify_columns

pn.extension("plotly", sizing_mode="stretch_width")

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
DF = load_and_clean()
COL_INFO = classify_columns(DF)
NUMERIC_COLS = COL_INFO["numeric"]
BOOL_COLS = COL_INFO["bool"]
DISCRETE_COLS = COL_INFO["discrete"]
NONE_OPTION = "—"  # sentinel for "no selection"

# Columns that actually vary (more than 1 unique value)
VARYING_COLS = [c for c in NUMERIC_COLS if DF[c].nunique() > 1]

# ---------------------------------------------------------------------------
# Widgets — axis selectors
# ---------------------------------------------------------------------------
def _default(preferred, cols, fallback_idx=0):
    """Return *preferred* if it exists in *cols*, else cols[fallback_idx]."""
    return preferred if preferred in cols else cols[fallback_idx]

x_select = pn.widgets.Select(name="X axis", options=NUMERIC_COLS, value=_default("shat", NUMERIC_COLS))
y_select = pn.widgets.Select(name="Y axis", options=NUMERIC_COLS, value=_default("betaprime_correct", NUMERIC_COLS, 1))
z_select = pn.widgets.Select(
    name="Z axis (optional)", options=[NONE_OPTION] + NUMERIC_COLS,
    value=_default("IBMgr", [NONE_OPTION] + NUMERIC_COLS),
)
color_select = pn.widgets.Select(
    name="Colour",
    options=[NONE_OPTION] + NUMERIC_COLS,
    value=_default("q", [NONE_OPTION] + NUMERIC_COLS),
)
size_select = pn.widgets.Select(
    name="Size", options=[NONE_OPTION] + NUMERIC_COLS, value=NONE_OPTION
)

# Axis scale toggles
x_log = pn.widgets.Checkbox(name="X log scale", value=False)
y_log = pn.widgets.Checkbox(name="Y log scale", value=False)
z_log = pn.widgets.Checkbox(name="Z log scale", value=False)

# ---------------------------------------------------------------------------
# Widgets — boolean filters (tri-state: Any / True / False)
# ---------------------------------------------------------------------------
bool_widgets = {}
for col in BOOL_COLS:
    bool_widgets[col] = pn.widgets.Select(
        name=col, options=["Any", "True", "False"], value="Any"
    )

# ---------------------------------------------------------------------------
# Widgets — discrete selectors
# ---------------------------------------------------------------------------
discrete_widgets = {}
for col in DISCRETE_COLS:
    unique_vals = sorted(DF[col].dropna().unique().tolist())
    str_vals = [str(v) for v in unique_vals]
    discrete_widgets[col] = pn.widgets.CheckButtonGroup(
        name=col, options=str_vals, value=str_vals,
    )
# Map string labels back to original values for filtering
_discrete_val_map = {}
for col in DISCRETE_COLS:
    unique_vals = sorted(DF[col].dropna().unique().tolist())
    _discrete_val_map[col] = {str(v): v for v in unique_vals}

# ---------------------------------------------------------------------------
# Widgets — range sliders for continuous numeric columns
# ---------------------------------------------------------------------------
range_sliders = {}
for col in NUMERIC_COLS:
    if col in DISCRETE_COLS:
        continue
    lo, hi = float(DF[col].min()), float(DF[col].max())
    if lo == hi:
        continue
    range_sliders[col] = pn.widgets.RangeSlider(
        name=col, start=lo, end=hi, value=(lo, hi), step=(hi - lo) / 200
    )

# ---------------------------------------------------------------------------
# Header / status
# ---------------------------------------------------------------------------
status_pane = pn.pane.Markdown("", styles={"font-size": "14px"})

# ---------------------------------------------------------------------------
# Filtering logic
# ---------------------------------------------------------------------------

def _filter_df():
    """Apply all active filters and return filtered DataFrame."""
    mask = pd.Series(True, index=DF.index)

    # Boolean filters
    for col, widget in bool_widgets.items():
        if widget.value == "True":
            mask &= DF[col] == True
        elif widget.value == "False":
            mask &= DF[col] == False

    # Discrete filters
    for col, widget in discrete_widgets.items():
        if widget.value:
            selected = [_discrete_val_map[col][s] for s in widget.value]
            mask &= DF[col].isin(selected) | DF[col].isna()
        else:
            # No values selected → show nothing
            mask &= False

    # Range sliders (use value_throttled when available)
    for col, widget in range_sliders.items():
        val = widget.value_throttled if widget.value_throttled is not None else widget.value
        lo, hi = val
        mask &= (DF[col] >= lo) & (DF[col] <= hi) | DF[col].isna()

    return DF.loc[mask]


# ---------------------------------------------------------------------------
# Plot builder
# ---------------------------------------------------------------------------

def _build_plot(filtered):
    """Build a Plotly figure from the filtered DataFrame."""
    x, y = x_select.value, y_select.value
    z = z_select.value if z_select.value != NONE_OPTION else None
    color = color_select.value if color_select.value != NONE_OPTION else None
    size = size_select.value if size_select.value != NONE_OPTION else None

    # Ensure size values are positive for Plotly
    plot_df = filtered.copy()
    if size and (plot_df[size] <= 0).any():
        plot_df[size] = plot_df[size] - plot_df[size].min() + 1e-6

    common = dict(color=color, size=size, hover_data=list(filtered.columns[:8]))

    if z is None:
        fig = px.scatter(plot_df, x=x, y=y, **common)
        if x_log.value:
            fig.update_xaxes(type="log")
        if y_log.value:
            fig.update_yaxes(type="log")
    else:
        fig = px.scatter_3d(plot_df, x=x, y=y, z=z, **common)
        scene = {}
        if x_log.value:
            scene["xaxis"] = dict(type="log")
        if y_log.value:
            scene["yaxis"] = dict(type="log")
        if z_log.value:
            scene["zaxis"] = dict(type="log")
        if scene:
            fig.update_layout(scene=scene)

    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        template="plotly_white",
        height=650,
        uirevision="keep",
    )
    return fig


# ---------------------------------------------------------------------------
# Reactive update
# ---------------------------------------------------------------------------

# Collect all widget references for dependency tracking.
# Range sliders use value_throttled (fires on mouse-up) to avoid
# rapid re-renders that reset the 3-D camera / zoom level.
_all_widgets = (
    [x_select, y_select, z_select, color_select, size_select, x_log, y_log, z_log]
    + list(bool_widgets.values())
    + list(discrete_widgets.values())
    + [rs.param.value_throttled for rs in range_sliders.values()]
)


_plot_pane = pn.pane.Plotly(sizing_mode="stretch_both")


@pn.depends(*_all_widgets, watch=True)
def _update_plot(*_events):
    filtered = _filter_df()
    status_pane.object = f"**Showing {len(filtered):,} / {len(DF):,} rows**"
    if filtered.empty:
        _plot_pane.object = go.Figure()
        return
    _plot_pane.object = _build_plot(filtered)


# Trigger initial render
_update_plot()


# ---------------------------------------------------------------------------
# Reload & Reset
# ---------------------------------------------------------------------------

def _reload_csv(_event=None):
    global DF, COL_INFO
    DF = load_and_clean()
    COL_INFO = classify_columns(DF)
    pn.state.notifications.info("CSV reloaded.")


def _reset_controls(_event=None):
    x_select.value = _default("shat", NUMERIC_COLS)
    y_select.value = _default("betaprime_correct", NUMERIC_COLS, 1)
    z_select.value = _default("IBMgr", [NONE_OPTION] + NUMERIC_COLS)
    color_select.value = _default("q", [NONE_OPTION] + NUMERIC_COLS)
    size_select.value = NONE_OPTION
    x_log.value = False
    y_log.value = False
    z_log.value = False
    for w in bool_widgets.values():
        w.value = "Any"
    for col, w in discrete_widgets.items():
        all_str = list(_discrete_val_map[col].keys())
        w.value = all_str
    for w in range_sliders.values():
        w.value = (w.start, w.end)


reload_btn = pn.widgets.Button(name="Reload CSV", button_type="light")
reload_btn.on_click(_reload_csv)
reset_btn = pn.widgets.Button(name="Reset Controls", button_type="warning")
reset_btn.on_click(_reset_controls)

# ---------------------------------------------------------------------------
# Download filtered CSV
# ---------------------------------------------------------------------------

def _download_callback():
    return _filter_df().to_csv()


download_btn = pn.widgets.FileDownload(
    callback=_download_callback, filename="filtered_data.csv", button_type="success",
    label="Download Filtered CSV",
)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

axis_section = pn.Column(
    "### Axes",
    x_select, y_select, z_select,
    x_log, y_log, z_log,
)

mapping_section = pn.Column("### Mapping", color_select, size_select)

bool_section = pn.Column("### Boolean Filters", *bool_widgets.values()) if bool_widgets else pn.Column()

discrete_section_items = []
for col, w in discrete_widgets.items():
    discrete_section_items.append(pn.pane.Markdown(f"**{col}**"))
    discrete_section_items.append(w)
discrete_section = pn.Column("### Discrete Filters", *discrete_section_items) if discrete_widgets else pn.Column()

slider_section = pn.Column("### Range Filters", *range_sliders.values()) if range_sliders else pn.Column()

sidebar = pn.Column(
    reload_btn,
    reset_btn,
    download_btn,
    axis_section,
    mapping_section,
    slider_section,
    bool_section,
    discrete_section,
    scroll=True,
    width=320,
)

slicer_tab = pn.Column(status_pane, _plot_pane, sizing_mode="stretch_both")

# ---------------------------------------------------------------------------
# Analysis tab — correlation ranking & pairplot
# ---------------------------------------------------------------------------

# Columns to include in the pairplot (user-selectable, minus constants)
_pair_cols_all = [c for c in VARYING_COLS if c != "IBMgr"]
# Default to top 6 by absolute correlation with IBMgr
_corrs = DF[_pair_cols_all + ["IBMgr"]].corr(numeric_only=True)["IBMgr"].drop("IBMgr").abs()
_pair_cols_default = _corrs.sort_values(ascending=False).head(6).index.tolist()
pair_col_select = pn.widgets.CheckBoxGroup(
    name="Pairplot columns",
    options=_pair_cols_all,
    value=_pair_cols_default,
    inline=False,
)


def _build_correlation_bar(filtered):
    """Horizontal bar chart of Pearson correlations with IBMgr."""
    if "IBMgr" not in filtered.columns or len(filtered) < 3:
        return go.Figure()
    varying = [c for c in VARYING_COLS if c != "IBMgr"]
    corrs = filtered[varying + ["IBMgr"]].corr(numeric_only=True)["IBMgr"].drop("IBMgr")
    corrs = corrs.dropna().sort_values()
    fig = go.Figure(go.Bar(
        x=corrs.values,
        y=corrs.index,
        orientation="h",
        marker_color=["#d62728" if v < 0 else "#1f77b4" for v in corrs.values],
    ))
    fig.update_layout(
        title="Pearson correlation with IBMgr",
        xaxis_title="Correlation",
        xaxis_range=[-1, 1],
        margin=dict(l=180, r=20, t=50, b=40),
        template="plotly_white",
        height=400,
    )
    return fig


def _build_marginals(filtered, cols):
    """Row of 1D histograms for each selected column."""
    if not cols or len(filtered) < 3:
        return go.Figure()
    n = len(cols)
    fig = make_subplots(rows=1, cols=n, subplot_titles=cols,
                        horizontal_spacing=0.04)
    for j, col in enumerate(cols):
        vals = filtered[col].dropna()
        fig.add_trace(
            go.Histogram(x=vals, nbinsx=80, marker_color="#1f77b4",
                         showlegend=False),
            row=1, col=j + 1,
        )
        fig.update_xaxes(tickfont_size=8, row=1, col=j + 1)
        fig.update_yaxes(showticklabels=False, row=1, col=j + 1)
    fig.update_layout(
        height=200,
        margin=dict(l=40, r=20, t=40, b=30),
        template="plotly_white",
        title="Marginal distributions",
    )
    return fig


def _build_pairplot(filtered, cols):
    """NxN grid: 1D histograms on diagonal, 2D histograms off-diagonal."""
    if len(cols) < 2 or len(filtered) < 3:
        return go.Figure()
    n = len(cols)
    fig = make_subplots(
        rows=n, cols=n,
        shared_xaxes=False, shared_yaxes=False,
        horizontal_spacing=0.02, vertical_spacing=0.02,
    )
    for i, row_col in enumerate(cols):
        for j, col_col in enumerate(cols):
            r, c = i + 1, j + 1
            if i == j:
                # Diagonal — 1D histogram
                vals = filtered[row_col].dropna()
                fig.add_trace(
                    go.Histogram(x=vals, nbinsx=80, marker_color="#1f77b4",
                                 showlegend=False),
                    row=r, col=c,
                )
            else:
                # Off-diagonal — 2D histogram
                pair = filtered[[col_col, row_col]].dropna()
                fig.add_trace(
                    go.Histogram2d(
                        x=pair[col_col], y=pair[row_col],
                        nbinsx=80, nbinsy=80,
                        colorscale="Blues", showscale=False,
                        showlegend=False,
                    ),
                    row=r, col=c,
                )
            # Axis labels on edges only
            if i == n - 1:
                fig.update_xaxes(title_text=col_col, title_font_size=13,
                                 tickfont_size=10, row=r, col=c)
            else:
                fig.update_xaxes(showticklabels=False, row=r, col=c)
            if j == 0:
                fig.update_yaxes(title_text=row_col, title_font_size=13,
                                 tickfont_size=10, row=r, col=c)
            else:
                fig.update_yaxes(showticklabels=False, row=r, col=c)
    cell_size = max(120, 900 // n)
    fig.update_layout(
        height=cell_size * n + 60,
        width=cell_size * n + 180,
        margin=dict(l=60, r=20, t=40, b=40),
        template="plotly_white",
        title="Pairwise 2D histograms",
    )
    return fig


# Reactive analysis pane — correlation bar + marginals always reactive,
# pairplot only on explicit button click.
_corr_pane = pn.pane.Plotly(sizing_mode="stretch_width")
_marginal_pane = pn.pane.Plotly(sizing_mode="stretch_width")
_pairplot_container = pn.Column(sizing_mode="stretch_both")


@pn.depends(*_all_widgets, watch=True)
def _update_top_analysis(*_events):
    """Recompute correlation bar and marginals on any filter change."""
    filtered = _filter_df()
    cols = [c for c in VARYING_COLS if c != "IBMgr"]
    if filtered.empty or len(filtered) < 3:
        _corr_pane.object = go.Figure()
        _marginal_pane.object = go.Figure()
        return
    _corr_pane.object = _build_correlation_bar(filtered)
    _marginal_pane.object = _build_marginals(filtered, cols)


def _plot_2d_correlations(_event=None):
    """Build the pairplot on button click only."""
    _pairplot_container[:] = [pn.indicators.LoadingSpinner(value=True, size=40)]
    filtered = _filter_df()
    cols = pair_col_select.value
    if filtered.empty or len(cols) < 2:
        _pairplot_container[:] = [
            pn.pane.Markdown("*Select at least 2 columns and ensure data matches filters.*")
        ]
        return
    pair_fig = _build_pairplot(filtered, cols)
    _pairplot_container[:] = [pn.pane.Plotly(pair_fig)]


plot_2d_btn = pn.widgets.Button(
    name="Plot selected 2D correlations", button_type="primary"
)
plot_2d_btn.on_click(_plot_2d_correlations)

# Trigger initial render
_update_top_analysis()

analysis_tab = pn.Column(
    _corr_pane,
    _marginal_pane,
    pn.pane.Markdown("**Select columns for 2D pairplot:**"),
    pair_col_select,
    plot_2d_btn,
    _pairplot_container,
    sizing_mode="stretch_both",
)

tabs = pn.Tabs(
    ("Slicer", slicer_tab),
    ("Analysis", analysis_tab),
    sizing_mode="stretch_both",
)

template = pn.template.FastListTemplate(
    title=f"Ballooning Stability — {CSV_PATH.name}",
    sidebar=[sidebar],
    main=[tabs],
    accent_base_color="#1f77b4",
    header_background="#1f77b4",
    theme_toggle=False,
)

template.servable()
