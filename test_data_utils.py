"""Tests for data_utils module."""

import pandas as pd
import pytest
from data_utils import load_and_clean, classify_columns, CSV_PATH


class TestLoadAndClean:
    def test_loads_csv(self):
        df = load_and_clean()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 10_000

    def test_no_unnamed_columns(self):
        df = load_and_clean()
        unnamed = [c for c in df.columns if c.startswith("Unnamed")]
        assert unnamed == []

    def test_electron_nu1_handled(self):
        df = load_and_clean()
        assert "electron_nu.1" not in df.columns
        # It was not a duplicate, so it gets renamed
        assert "electron_nu_ref" in df.columns
        assert "electron_nu" in df.columns

    def test_expected_columns_present(self):
        df = load_and_clean()
        expected = {"q", "shat", "beta", "gamma_exb", "betaprime_correct", "IBMgr",
                    "isapar", "isbpar", "psi_n", "shift", "delta", "kappa"}
        assert expected.issubset(set(df.columns))

    def test_bool_dtypes(self):
        df = load_and_clean()
        assert df["isapar"].dtype == "bool"
        assert df["isbpar"].dtype == "bool"


class TestClassifyColumns:
    @pytest.fixture
    def df(self):
        return load_and_clean()

    def test_numeric_list_nonempty(self, df):
        result = classify_columns(df)
        assert len(result["numeric"]) >= 15

    def test_bool_list(self, df):
        result = classify_columns(df)
        assert set(result["bool"]) == {"isapar", "isbpar"}

    def test_discrete_list_contains_psi_n(self, df):
        result = classify_columns(df)
        assert "psi_n" in result["discrete"]

    def test_discrete_is_subset_of_numeric(self, df):
        result = classify_columns(df)
        assert set(result["discrete"]).issubset(set(result["numeric"]))

    def test_booleans_not_in_numeric(self, df):
        result = classify_columns(df)
        for bc in result["bool"]:
            assert bc not in result["numeric"]
