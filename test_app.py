"""Tests for app.py — widget setup, filtering, and plot building."""

import pandas as pd
import pytest

# Import the app module (does not start the server)
import app


class TestWidgetSetup:
    def test_axis_dropdowns_populated(self):
        assert len(app.x_select.options) >= 15
        assert len(app.y_select.options) >= 15

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
        # Should have sliders for continuous numeric cols (minus discrete ones)
        assert len(app.range_sliders) > 5


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
        filtered = app._filter_df()
        assert len(filtered) <= len(app.DF)
        assert (filtered[col] >= mid).all()
        slider.value = saved  # reset


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
