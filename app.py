"""Interactive Multidimensional Slicer — Panel + Plotly app."""

import panel as pn
import plotly.express as px
import pandas as pd

from data_utils import load_and_clean, classify_columns

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

# ---------------------------------------------------------------------------
# Widgets — axis selectors
# ---------------------------------------------------------------------------
x_select = pn.widgets.Select(name="X axis", options=NUMERIC_COLS, value="shat")
y_select = pn.widgets.Select(name="Y axis", options=NUMERIC_COLS, value="betaprime_correct")
z_select = pn.widgets.Select(
    name="Z axis (optional)", options=[NONE_OPTION] + NUMERIC_COLS, value="IBMgr"
)
color_select = pn.widgets.Select(
    name="Colour",
    options=[NONE_OPTION] + NUMERIC_COLS,
    value="betaprime_correct" if "betaprime_correct" in NUMERIC_COLS else NONE_OPTION,
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

    # Range sliders
    axes_in_use = {x_select.value, y_select.value}
    if z_select.value != NONE_OPTION:
        axes_in_use.add(z_select.value)
    for col, widget in range_sliders.items():
        lo, hi = widget.value
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
    )
    return fig


# ---------------------------------------------------------------------------
# Reactive update
# ---------------------------------------------------------------------------

# Collect all widget references for dependency tracking
_all_widgets = (
    [x_select, y_select, z_select, color_select, size_select, x_log, y_log, z_log]
    + list(bool_widgets.values())
    + list(discrete_widgets.values())
    + list(range_sliders.values())
)


@pn.depends(*_all_widgets, watch=False)
def update_plot(*_events):
    filtered = _filter_df()
    status_pane.object = f"**Showing {len(filtered):,} / {len(DF):,} rows**"
    if filtered.empty:
        return pn.pane.Markdown("*No data matches current filters.*")
    return pn.pane.Plotly(_build_plot(filtered), sizing_mode="stretch_both")


# ---------------------------------------------------------------------------
# Reload & Reset
# ---------------------------------------------------------------------------

def _reload_csv(_event=None):
    global DF, COL_INFO
    DF = load_and_clean()
    COL_INFO = classify_columns(DF)
    pn.state.notifications.info("CSV reloaded.")


def _reset_controls(_event=None):
    x_select.value = "shat"
    y_select.value = "betaprime_correct"
    z_select.value = "IBMgr"
    color_select.value = (
        "betaprime_correct" if "betaprime_correct" in NUMERIC_COLS else NONE_OPTION
    )
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
    bool_section,
    discrete_section,
    slider_section,
    scroll=True,
    width=320,
)

main = pn.Column(status_pane, update_plot, sizing_mode="stretch_both")

template = pn.template.FastListTemplate(
    title="Ballooning Stability — Multidimensional Slicer",
    sidebar=[sidebar],
    main=[main],
    accent_base_color="#1f77b4",
    header_background="#1f77b4",
    theme_toggle=False,
)

template.servable()
