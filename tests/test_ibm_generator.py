"""Tests for ibm_generator and generate_ibmgr CLI.

All pyrokinetics calls are mocked so tests run without the solver.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from ibm import ibm_generator
from ibm.generate_ibmgr import main as cli_main


# ---------------------------------------------------------------------------
# ibm_generator unit tests
# ---------------------------------------------------------------------------


class TestMakeGeometryGrid:
    def test_default_shape(self):
        grid = ibm_generator.make_geometry_grid()
        assert list(grid.columns) == ["kappa", "delta"]
        assert len(grid) == 11 * 11

    def test_custom_shape(self):
        grid = ibm_generator.make_geometry_grid(
            kappa_min=1.0, kappa_max=2.0, n_kappa=3,
            delta_min=0.0, delta_max=1.0, n_delta=5,
        )
        assert len(grid) == 3 * 5
        assert grid["kappa"].min() == pytest.approx(1.0)
        assert grid["kappa"].max() == pytest.approx(2.0)
        assert grid["delta"].min() == pytest.approx(0.0)
        assert grid["delta"].max() == pytest.approx(1.0)

    def test_single_point(self):
        grid = ibm_generator.make_geometry_grid(
            kappa_min=2.0, kappa_max=2.0, n_kappa=1,
            delta_min=0.5, delta_max=0.5, n_delta=1,
        )
        assert len(grid) == 1
        assert grid.iloc[0]["kappa"] == pytest.approx(2.0)
        assert grid.iloc[0]["delta"] == pytest.approx(0.5)


class TestSampleBaseRows:
    def test_samples_correct_columns(self, tmp_path):
        df = pd.DataFrame({
            "beta": [0.01, 0.02, 0.03, 0.04, 0.05],
            "q": [1.5, 2.0, 2.5, 3.0, 3.5],
            "shat": [0.5, 1.0, 1.5, 2.0, 2.5],
            "electron_temp_gradient": [1.0] * 5,
            "electron_dens_gradient": [0.5] * 5,
            "deuterium_temp_gradient": [0.8] * 5,
            "electron_nu": [0.001] * 5,
            "extra_col": [99] * 5,
        })
        csv_path = tmp_path / "test.csv"
        df.to_csv(csv_path)

        sampled = ibm_generator.sample_base_rows(csv_path, n_samples=3, seed=0)
        assert len(sampled) == 3
        assert "extra_col" not in sampled.columns
        for col in ibm_generator.KINETIC_COLS:
            assert col in sampled.columns

    def test_no_sample_limit(self, tmp_path):
        df = pd.DataFrame({
            "beta": [0.01, 0.02],
            "q": [1.5, 2.0],
            "shat": [0.5, 1.0],
            "electron_temp_gradient": [1.0, 1.0],
            "electron_dens_gradient": [0.5, 0.5],
            "deuterium_temp_gradient": [0.8, 0.8],
            "electron_nu": [0.001, 0.001],
        })
        csv_path = tmp_path / "test.csv"
        df.to_csv(csv_path)

        sampled = ibm_generator.sample_base_rows(csv_path)
        assert len(sampled) == 2


class TestBuildScanDataframe:
    def test_cross_product_size(self):
        kinetic = pd.DataFrame({
            "beta": [0.01, 0.02],
            "q": [1.5, 2.0],
        })
        grid = pd.DataFrame({
            "kappa": [1.0, 2.0, 3.0],
            "delta": [0.0, 0.5, 1.0],
        })
        combined = ibm_generator.build_scan_dataframe(kinetic, grid)
        assert len(combined) == 2 * 3
        assert "beta" in combined.columns
        assert "kappa" in combined.columns

    def test_no_merge_column_left(self):
        kinetic = pd.DataFrame({"beta": [0.01]})
        grid = pd.DataFrame({"kappa": [1.0]})
        combined = ibm_generator.build_scan_dataframe(kinetic, grid)
        assert "_merge" not in combined.columns


def _make_mock_pyro():
    """Create a mock Pyro with the attributes the generator accesses."""
    pyro = MagicMock()
    pyro.numerics.beta = 0.01
    pyro.local_geometry.q = 3.49
    pyro.local_geometry.shat = 1.2
    pyro.local_geometry.kappa = 2.56
    pyro.local_geometry.delta = 0.28
    pyro.local_geometry.beta_prime = -0.05
    pyro.local_species.__getitem__ = MagicMock(return_value=MagicMock(
        inverse_lt=1.5, inverse_ln=1.0, nu=0.03,
    ))
    return pyro


class TestKineticRowsFromTemplate:
    def test_returns_single_row(self):
        pyro = _make_mock_pyro()
        df = ibm_generator.kinetic_rows_from_template(pyro)
        assert len(df) == 1
        assert "beta" in df.columns
        assert "electron_nu" in df.columns


class TestRunIbmScan:
    @patch("ibm.ibm_generator.Diagnostics")
    @patch("ibm.ibm_generator.load_template")
    def test_successful_scan(self, mock_load, mock_diag_cls):
        mock_pyro = _make_mock_pyro()
        mock_load.return_value = mock_pyro

        mock_diag = MagicMock()
        mock_diag.ideal_ballooning_solver.return_value = 0.123
        mock_diag_cls.return_value = mock_diag

        scan_df = pd.DataFrame({
            "beta": [0.01, 0.02],
            "q": [3.0, 3.5],
            "shat": [1.0, 1.5],
            "electron_temp_gradient": [1.5, 1.6],
            "electron_dens_gradient": [1.0, 1.1],
            "deuterium_temp_gradient": [1.5, 1.6],
            "electron_nu": [0.03, 0.04],
            "kappa": [2.0, 2.5],
            "delta": [0.3, 0.4],
        })

        results, failures = ibm_generator.run_ibm_scan("fake.cgyro", scan_df)

        assert len(results) == 2
        assert len(failures) == 0
        assert "IBMgr" in results.columns
        assert "isIBMunstable" in results.columns
        assert "beta_prime" in results.columns
        assert "run_timestamp" in results.columns
        assert results["IBMgr"].iloc[0] == pytest.approx(0.123)
        assert results["isIBMunstable"].iloc[0] == True  # noqa: E712 (numpy bool)

    @patch("ibm.ibm_generator.Diagnostics")
    @patch("ibm.ibm_generator.load_template")
    def test_failure_handling(self, mock_load, mock_diag_cls):
        mock_pyro = _make_mock_pyro()
        mock_load.return_value = mock_pyro

        mock_diag = MagicMock()
        mock_diag.ideal_ballooning_solver.side_effect = RuntimeError("solver boom")
        mock_diag_cls.return_value = mock_diag

        scan_df = pd.DataFrame({
            "beta": [0.01],
            "q": [3.0],
            "shat": [1.0],
            "electron_temp_gradient": [1.5],
            "electron_dens_gradient": [1.0],
            "deuterium_temp_gradient": [1.5],
            "electron_nu": [0.03],
            "kappa": [2.0],
            "delta": [0.3],
        })

        results, failures = ibm_generator.run_ibm_scan("fake.cgyro", scan_df)

        assert len(results) == 0
        assert len(failures) == 1
        assert "error" in failures.columns
        assert "solver boom" in failures["error"].iloc[0]

    @patch("ibm.ibm_generator.Diagnostics")
    @patch("ibm.ibm_generator.load_template")
    def test_mixed_success_and_failure(self, mock_load, mock_diag_cls):
        mock_pyro = _make_mock_pyro()
        mock_load.return_value = mock_pyro

        mock_diag = MagicMock()
        # First call succeeds, second raises
        mock_diag.ideal_ballooning_solver.side_effect = [0.05, RuntimeError("bad")]
        mock_diag_cls.return_value = mock_diag

        scan_df = pd.DataFrame({
            "beta": [0.01, 0.02],
            "q": [3.0, 3.5],
            "shat": [1.0, 1.5],
            "electron_temp_gradient": [1.5, 1.6],
            "electron_dens_gradient": [1.0, 1.1],
            "deuterium_temp_gradient": [1.5, 1.6],
            "electron_nu": [0.03, 0.04],
            "kappa": [2.0, 2.5],
            "delta": [0.3, 0.4],
        })

        results, failures = ibm_generator.run_ibm_scan("fake.cgyro", scan_df)

        assert len(results) == 1
        assert len(failures) == 1


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_missing_template_exits_1(self, tmp_path):
        ret = cli_main([
            "--template", str(tmp_path / "nonexistent.cgyro"),
            "--output", str(tmp_path / "out.csv"),
        ])
        assert ret == 1

    def test_missing_base_csv_exits_1(self, tmp_path):
        template = tmp_path / "t.cgyro"
        template.write_text("dummy")
        ret = cli_main([
            "--template", str(template),
            "--base-csv", str(tmp_path / "nonexistent.csv"),
            "--output", str(tmp_path / "out.csv"),
        ])
        assert ret == 1

    @patch("ibm.generate_ibmgr.run_ibm_scan_parallel")
    @patch("ibm.generate_ibmgr.load_template")
    def test_template_only_run(self, mock_load, mock_run, tmp_path):
        mock_pyro = _make_mock_pyro()
        mock_load.return_value = mock_pyro

        results = pd.DataFrame({
            "kappa": [2.0],
            "delta": [0.3],
            "IBMgr": [0.1],
            "isIBMunstable": [True],
            "beta_prime": [-0.05],
            "run_timestamp": ["2026-01-01T00:00:00"],
        })
        mock_run.return_value = (results, pd.DataFrame())

        template = tmp_path / "input.cgyro"
        template.write_text("dummy")
        output = tmp_path / "out.csv"

        ret = cli_main([
            "--template", str(template),
            "--output", str(output),
            "--n-kappa", "2",
            "--n-delta", "2",
        ])

        assert ret == 0
        assert output.exists()
