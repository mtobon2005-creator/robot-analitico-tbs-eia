"""Pruebas RF-22: exportación de precios, tabla comparativa y bundle JSON."""
import json
from datetime import date

import pandas as pd
import pytest

from src.comparison import ComparisonRow
from src.data import PriceSeries
from src.export import (
    export_comparison_table_csv,
    export_full_bundle_json,
    export_prices_csv,
)


def _make_price_series(ticker: str, prices: list[float]) -> PriceSeries:
    index = pd.date_range("2026-01-01", periods=len(prices), freq="D")
    return PriceSeries(
        ticker=ticker,
        prices=pd.Series(prices, index=index),
        currency="USD",
        timezone="America/New_York",
        source="test-fixture",
        price_adjusted=True,
        cleaning_report={"dropped_duplicates": 0, "dropped_missing": 0, "dropped_nonpositive": 0},
    )


def test_export_prices_csv_has_expected_columns():
    data = {"AAPL": _make_price_series("AAPL", [100.0, 101.0, 102.0])}
    csv_text = export_prices_csv(data)
    df = pd.read_csv(pd.io.common.StringIO(csv_text))
    assert list(df.columns) == ["date", "ticker", "adjusted_close", "currency", "source"]
    assert len(df) == 3
    assert (df["ticker"] == "AAPL").all()


def test_export_prices_csv_combines_multiple_tickers():
    data = {
        "AAPL": _make_price_series("AAPL", [100.0, 101.0]),
        "MSFT": _make_price_series("MSFT", [200.0, 202.0]),
    }
    csv_text = export_prices_csv(data)
    df = pd.read_csv(pd.io.common.StringIO(csv_text))
    assert set(df["ticker"]) == {"AAPL", "MSFT"}
    assert len(df) == 4


def test_export_comparison_table_csv():
    rows = [
        ComparisonRow("AAPL", vol_annual=0.20, mean_annual=0.10, rvr=0.5, n_obs_common=500),
        ComparisonRow("MSFT", vol_annual=0.15, mean_annual=0.12, rvr=0.8, n_obs_common=500),
    ]
    csv_text = export_comparison_table_csv(rows)
    df = pd.read_csv(pd.io.common.StringIO(csv_text))
    assert list(df["ticker"]) == ["AAPL", "MSFT"]
    assert df.loc[0, "rvr"] == pytest.approx(0.5)


def test_export_full_bundle_json_is_valid_json_with_required_keys():
    data = {"AAPL": _make_price_series("AAPL", [100.0, 101.0, 102.0])}
    rows = [ComparisonRow("AAPL", vol_annual=0.2, mean_annual=0.1, rvr=0.5, n_obs_common=2)]
    params = {"fecha_inicial": date(2026, 1, 1), "fecha_final": date(2026, 1, 3), "frecuencia": "Diaria"}

    text = export_full_bundle_json(data, rows, params)
    payload = json.loads(text)  # no debe lanzar -> JSON válido

    assert "exported_at" in payload
    assert payload["parameters"]["fecha_inicial"] == "2026-01-01"  # date -> isoformat
    assert payload["sources"]["AAPL"] == "test-fixture"
    assert payload["comparison_table"][0]["ticker"] == "AAPL"
    assert payload["prices"]["AAPL"]["adjusted_close"] == [100.0, 101.0, 102.0]


def test_export_full_bundle_json_includes_errors_when_present():
    data = {"AAPL": _make_price_series("AAPL", [100.0])}
    rows = [ComparisonRow("AAPL", vol_annual=0.0, mean_annual=0.0, rvr=None, n_obs_common=0)]
    text = export_full_bundle_json(
        data, rows, {}, fetch_errors={"EIA_INVALID_2026": "TickerNotFound: no existe"}
    )
    payload = json.loads(text)
    assert "EIA_INVALID_2026" in payload["errors"]
