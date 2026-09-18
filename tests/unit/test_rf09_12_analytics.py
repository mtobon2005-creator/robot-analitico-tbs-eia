"""Pruebas RF-09 a RF-12.

Incluye verificación numérica exacta contra
tests/fixtures/Resultados_esperados_20_activos_TBS_EIA.csv para los
20 tickers oficiales del fixture (MAP-20-01).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analytics import (
    build_present_context,
    compare_full_vs_recent_window,
    compute_drawdown_series,
    compute_log_returns,
    descriptive_stats,
    last_return_percentile_midrank,
    max_drawdown,
    quantile_type7,
)
from src.data import FixtureProvider, clean_prices

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_CSV = FIXTURES_DIR / "Fixture_20_activos_sintetico_TBS_EIA.csv"
EXPECTED_CSV = FIXTURES_DIR / "Resultados_esperados_20_activos_TBS_EIA.csv"

ATOL = 1e-8


# --- RF-10: exclusividad logarítmica (LOG-01) --------------------------------

def test_compute_log_returns_matches_official_log01_case():
    # LOG-01: precios 100, 110, 99 -> g=[0.095310179804325, -0.105360515657826]
    prices = pd.Series(
        [100.0, 110.0, 99.0],
        index=pd.date_range("2026-01-01", periods=3, freq="D"),
    )
    g = compute_log_returns(prices)
    np.testing.assert_allclose(
        g.values, [0.095310179804325, -0.105360515657826], atol=ATOL
    )


def test_compute_log_returns_never_produces_simple_return_values():
    # 0.10 y -0.10 serían los rendimientos SIMPLES — LOG-01 exige que
    # NUNCA aparezcan como salida de esta función.
    prices = pd.Series(
        [100.0, 110.0, 99.0],
        index=pd.date_range("2026-01-01", periods=3, freq="D"),
    )
    g = compute_log_returns(prices)
    assert not np.isclose(g.iloc[0], 0.10, atol=1e-6)
    assert not np.isclose(g.iloc[1], -0.10, atol=1e-6)


def test_compute_log_returns_rejects_nonpositive_prices():
    prices = pd.Series(
        [100.0, -5.0], index=pd.date_range("2026-01-01", periods=2, freq="D")
    )
    with pytest.raises(ValueError):
        compute_log_returns(prices)


def test_compute_log_returns_drops_first_nan():
    prices = pd.Series(
        [100.0, 101.0, 102.0], index=pd.date_range("2026-01-01", periods=3, freq="D")
    )
    g = compute_log_returns(prices)
    assert len(g) == 2  # 3 precios -> 2 rendimientos, sin NaN


# --- RF-11: estadísticos (STAT-01, FREQ-01) ----------------------------------

def _synthetic_returns():
    return pd.Series(
        [-0.02, -0.01, 0.0, 0.01, 0.02],
        index=pd.date_range("2026-01-01", periods=5, freq="D"),
    )


def test_descriptive_stats_matches_official_stat01_daily():
    stats_ = descriptive_stats(_synthetic_returns(), "Diaria")
    assert stats_.mean_period == pytest.approx(0.0, abs=ATOL)
    assert stats_.variance_period == pytest.approx(0.000250000000000, abs=ATOL)
    assert stats_.sd_period == pytest.approx(0.015811388300842, abs=ATOL)
    assert stats_.sd_annual == pytest.approx(0.250998007960223, abs=ATOL)


def test_descriptive_stats_matches_official_freq01_weekly():
    stats_ = descriptive_stats(_synthetic_returns(), "Semanal")
    assert stats_.mean_annual == pytest.approx(0.0, abs=ATOL)
    assert stats_.sd_annual == pytest.approx(0.114017542509914, abs=ATOL)


def test_descriptive_stats_matches_official_freq01_monthly():
    stats_ = descriptive_stats(_synthetic_returns(), "Mensual")
    assert stats_.mean_annual == pytest.approx(0.0, abs=ATOL)
    assert stats_.sd_annual == pytest.approx(0.054772255750517, abs=ATOL)


def test_descriptive_stats_rvr_is_none_when_volatility_zero():
    constant_returns = pd.Series(
        [0.0, 0.0, 0.0], index=pd.date_range("2026-01-01", periods=3, freq="D")
    )
    stats_ = descriptive_stats(constant_returns, "Diaria")
    assert stats_.sd_annual == 0.0
    assert stats_.rvr is None  # RVR indefinida, no división por cero


def test_descriptive_stats_rejects_unknown_frequency():
    with pytest.raises(ValueError):
        descriptive_stats(_synthetic_returns(), "Quincenal")


def test_quantile_type7_matches_numpy_linear():
    returns = pd.Series(np.arange(1, 101, dtype=float))
    assert quantile_type7(returns, 50) == pytest.approx(
        np.percentile(returns, 50, method="linear")
    )


# --- RF-12: drawdown y percentil midrank -------------------------------------

def test_drawdown_series_is_zero_at_running_peak():
    prices = pd.Series(
        [100.0, 110.0, 90.0, 120.0],
        index=pd.date_range("2026-01-01", periods=4, freq="D"),
    )
    dd = compute_drawdown_series(prices)
    assert dd.iloc[0] == pytest.approx(0.0)
    assert dd.iloc[1] == pytest.approx(0.0)  # nuevo máximo -> drawdown 0
    assert dd.iloc[2] == pytest.approx(90 / 110 - 1)
    assert dd.iloc[3] == pytest.approx(0.0)  # nuevo máximo otra vez


def test_max_drawdown_is_the_minimum_of_the_series():
    prices = pd.Series(
        [100.0, 110.0, 88.0, 120.0],
        index=pd.date_range("2026-01-01", periods=4, freq="D"),
    )
    assert max_drawdown(prices) == pytest.approx(88 / 110 - 1)


def test_last_return_percentile_midrank_handles_ties():
    # Cinco valores iguales -> el último debe caer en el percentil 50
    # (midrank promedia los rangos de los empates).
    returns = pd.Series([0.01, 0.01, 0.01, 0.01, 0.01])
    pct = last_return_percentile_midrank(returns)
    assert pct == pytest.approx(50.0)


def test_last_return_percentile_midrank_is_90_for_max_of_five_no_tie():
    # Máximo único de 5 valores: rango estricto-menor=4/5=80%,
    # menor-o-igual=5/5=100% -> midrank promedia a 90%.
    returns = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
    pct = last_return_percentile_midrank(returns)
    assert pct == pytest.approx(90.0)


def test_compare_full_vs_recent_window_labels_partial_when_short():
    returns = _synthetic_returns()  # 5 observaciones
    comparison = compare_full_vs_recent_window(returns, "Diaria")  # m=252
    assert comparison.is_partial is True
    assert comparison.recent_window_size == 5  # min(252, 5)


def test_compare_full_vs_recent_window_not_partial_when_long_enough():
    long_returns = pd.Series(np.random.normal(0, 0.01, 300))
    comparison = compare_full_vs_recent_window(long_returns, "Diaria")  # m=252
    assert comparison.is_partial is False
    assert comparison.recent_window_size == 252


def test_build_present_context_reports_last_price_and_return():
    prices = pd.Series(
        [100.0, 105.0, 95.0],
        index=pd.date_range("2026-01-01", periods=3, freq="D"),
    )
    returns = compute_log_returns(prices)
    ctx = build_present_context(prices, returns)
    assert ctx.last_price == pytest.approx(95.0)
    assert ctx.last_date == prices.index[-1]
    assert ctx.last_log_return == pytest.approx(returns.iloc[-1])
    assert ctx.max_drawdown_value == pytest.approx(95 / 105 - 1)


# --- Verificación exacta contra los 20 tickers oficiales (MAP-20-01) --------

_TICKERS_TO_VERIFY = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "JPM", "JNJ", "XOM",
    "PG", "KO", "PEP", "WMT", "HD", "COST", "UNH", "V", "MA", "CAT", "MCD",
]


@pytest.fixture(scope="module")
def expected_results():
    return pd.read_csv(EXPECTED_CSV).set_index("ticker")


@pytest.fixture(scope="module")
def fixture_provider():
    return FixtureProvider(FIXTURE_CSV)


@pytest.mark.parametrize("ticker", _TICKERS_TO_VERIFY)
def test_full_pipeline_matches_official_expected_results(
    ticker, fixture_provider, expected_results
):
    from datetime import date

    raw = fixture_provider.fetch(ticker, date(2024, 7, 19), date(2026, 8, 13))
    prices, _ = clean_prices(raw)
    returns = compute_log_returns(prices)
    stats_ = descriptive_stats(returns, "Diaria")
    q05 = quantile_type7(returns, 5)
    q95 = quantile_type7(returns, 95)
    mdd = max_drawdown(prices)

    expected = expected_results.loc[ticker]

    assert stats_.n_obs == expected["return_observations"]
    assert prices.iloc[-1] == pytest.approx(expected["last_adjusted_close"], abs=ATOL)
    assert stats_.mean_period == pytest.approx(expected["mean_log_period"], abs=ATOL)
    assert stats_.sd_period == pytest.approx(expected["sample_sd_period"], abs=ATOL)
    assert stats_.mean_annual == pytest.approx(expected["mean_log_annual_252"], abs=ATOL)
    assert stats_.sd_annual == pytest.approx(expected["volatility_annual_252"], abs=ATOL)
    if stats_.rvr is not None:
        assert stats_.rvr == pytest.approx(expected["individual_rvr"], abs=ATOL)
    assert q05 == pytest.approx(expected["q05_log_type7"], abs=ATOL)
    assert q95 == pytest.approx(expected["q95_log_type7"], abs=ATOL)
    assert mdd == pytest.approx(expected["max_drawdown"], abs=ATOL)
