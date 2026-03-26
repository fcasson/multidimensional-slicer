"""Tests for app.py — widget setup, filtering, and plot building."""

import pandas as pd
import pytest

# Import the app module (does not start the server)
from gui import app


class TestWidgetSetup:
    def test_axis_dropdowns_populated(self):
        assert len(app.x_select.options) >= 10
        assert len(app.y_select.options) >= 10

    def test_z_has_none_option(self):
        assert app.z_select.options[0] == app.NONE_OPTION
        # Default is 3D mode with IBMgr
        assert app.z_select.value == "IBMgr"

    def test_color_default_is_q(self):
        assert app.color_select.value == "q"

    def test_bool_widgets_created(self):
        assert "isapar" in app.bool_widgets
        assert "isbpar" in app.bool_widgets
        for w in app.bool_widgets.values():
            assert w.value == "Any"

    def test_discrete_widgets_contain_psi_n(self):
        assert "psi_n" in app.discrete_widgets

    def test_range_sliders_created(self):
        # Should have sliders for continuous numeric cols (minus discrete/constant)
        assert len(app.range_sliders) > 0


class TestFiltering:
    def test_no_filters_returns_all(self):
        filtered = app._filter_df()
        assert len(filtered) == len(app.DF)

    def test_bool_filter_true(self):
        app.bool_widgets["isapar"].value = "True"
        filtered = app._filter_df()
        assert (filtered["isapar"] == True).all()
        app.bool_widgets["isapar"].value = "Any"  # reset

    def test_bool_filter_false(self):
        app.bool_widgets["isbpar"].value = "False"
        filtered = app._filter_df()
        assert (filtered["isbpar"] == False).all()
        app.bool_widgets["isbpar"].value = "Any"  # reset

    def test_discrete_filter_reduces_rows(self):
        w = app.discrete_widgets["psi_n"]
        all_vals = w.value[:]
        # Keep only the first value
        w.value = [all_vals[0]]
        filtered = app._filter_df()
        # Rows with psi_n == selected value OR psi_n == NaN pass through
        non_nan = filtered["psi_n"].dropna()
        expected = app._discrete_val_map["psi_n"][all_vals[0]]
        assert set(non_nan.unique()) == {expected}
        w.value = all_vals  # reset

    def test_empty_discrete_returns_nothing(self):
        w = app.discrete_widgets["psi_n"]
        saved = w.value[:]
        w.value = []
        filtered = app._filter_df()
        assert len(filtered) == 0
        w.value = saved  # reset

    def test_range_slider_filter(self):
        col = list(app.range_sliders.keys())[0]
        slider = app.range_sliders[col]
        mid = (slider.start + slider.end) / 2
        saved = slider.value
        slider.value = (mid, slider.end)
        # value_throttled is a constant param; temporarily unlock it
        p = slider.param.value_throttled
        p.constant = False
        slider.value_throttled = (mid, slider.end)
        p.constant = True
        filtered = app._filter_df()
        assert len(filtered) <= len(app.DF)
        assert (filtered[col] >= mid).all()
        # Reset
        p.constant = False
        slider.value_throttled = saved
        p.constant = True
        slider.value = saved


class TestPlotBuilder:
    def test_2d_plot(self):
        fig = app._build_plot(app.DF.head(100))
        assert fig is not None
        assert fig.data  # has at least one trace

    def test_3d_plot(self):
        app.z_select.value = app.NUMERIC_COLS[2]
        fig = app._build_plot(app.DF.head(100))
        assert fig is not None
        assert fig.data
        app.z_select.value = app.NONE_OPTION  # reset


class TestResetControls:
    def test_reset_restores_defaults(self):
        # Change some values
        app.x_select.value = app.NUMERIC_COLS[3]
        app.bool_widgets["isapar"].value = "True"
        # Reset
        app._reset_controls()
        assert app.x_select.value == "shat"
        assert app.y_select.value == "betaprime_correct"
        assert app.z_select.value == "IBMgr"
        assert app.bool_widgets["isapar"].value == "Any"


class TestVaryingCols:
    def test_excludes_constant_columns(self):
        # Constant columns like shift, delta, kappa should be excluded
        for col in ["shift", "delta", "deltaprime", "kappa", "kappaprime"]:
            if col in app.DF.columns:
                assert col not in app.VARYING_COLS

    def test_includes_varying_columns(self):
        for col in ["q", "shat", "beta", "IBMgr"]:
            assert col in app.VARYING_COLS


class TestCorrelationBar:
    def test_returns_figure(self):
        fig = app._build_correlation_bar(app.DF)
        assert fig is not None
        assert len(fig.data) == 1
        assert fig.data[0].orientation == "h"

    def test_bar_count_matches_varying_cols(self):
        fig = app._build_correlation_bar(app.DF)
        varying_minus_ibmgr = [c for c in app.VARYING_COLS if c != "IBMgr"]
        assert len(fig.data[0].y) == len(varying_minus_ibmgr)

    def test_empty_df_returns_empty_figure(self):
        fig = app._build_correlation_bar(app.DF.head(0))
        assert len(fig.data) == 0


class TestMarginals:
    def test_returns_figure_with_traces(self):
        cols = ["q", "shat", "beta"]
        fig = app._build_marginals(app.DF, cols)
        assert len(fig.data) == 3

    def test_empty_cols_returns_empty_figure(self):
        fig = app._build_marginals(app.DF, [])
        assert len(fig.data) == 0


class TestPairplot:
    def test_returns_n_squared_traces(self):
        cols = ["q", "shat", "beta"]
        fig = app._build_pairplot(app.DF.head(500), cols)
        assert len(fig.data) == 9  # 3x3

    def test_single_col_returns_empty(self):
        fig = app._build_pairplot(app.DF, ["q"])
        assert len(fig.data) == 0

    def test_diagonal_is_histogram(self):
        import plotly.graph_objects as go
        cols = ["q", "shat"]
        fig = app._build_pairplot(app.DF.head(500), cols)
        # Diagonal traces: index 0 (0,0) and 3 (1,1)
        assert isinstance(fig.data[0], go.Histogram)
        assert isinstance(fig.data[3], go.Histogram)

    def test_offdiag_is_histogram2d(self):
        import plotly.graph_objects as go
        cols = ["q", "shat"]
        fig = app._build_pairplot(app.DF.head(500), cols)
        # Off-diagonal: index 1 (0,1) and 2 (1,0)
        assert isinstance(fig.data[1], go.Histogram2d)
        assert isinstance(fig.data[2], go.Histogram2d)


class TestPairColSelect:
    def test_default_is_top_6(self):
        assert len(app.pair_col_select.value) == 6

    def test_options_exclude_ibmgr(self):
        assert "IBMgr" not in app.pair_col_select.options

    def test_options_exclude_constants(self):
        for col in ["shift", "delta", "deltaprime", "kappa", "kappaprime"]:
            if col in app.DF.columns:
                assert col not in app.pair_col_select.options
