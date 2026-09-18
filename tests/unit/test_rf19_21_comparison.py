"""Pruebas RF-19 a RF-21: mapa comparativo, dominancia, selección."""
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.comparison import (
    ComparisonRow,
    IncompatibleCurrencies,
    InsufficientAssetsForComparison,
    build_comparison_table,
    compute_non_dominated,
    dominates,
    select_max_mean_under_risk_limit,
    select_max_rvr,
    select_min_volatility_under_mean_floor,
    select_non_dominated_set,
)
from src.data import FetchResult, FixtureProvider, fetch_and_clean_many

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_CSV = FIXTURES_DIR / "Fixture_20_activos_sintetico_TBS_EIA.csv"
EXPECTED_CSV = FIXTURES_DIR / "Resultados_esperados_20_activos_TBS_EIA.csv"
FULL_RANGE = (date(2024, 7, 19), date(2026, 8, 13))

_TICKERS_20 = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "JPM", "JNJ", "XOM",
    "PG", "KO", "PEP", "WMT", "HD", "COST", "UNH", "V", "MA", "CAT", "MCD",
]


# --- dominancia (unitario, sin fixture) --------------------------------------

def test_dominates_strict_case():
    a = ComparisonRow("A", vol_annual=0.10, mean_annual=0.10, rvr=1.0, n_obs_common=100)
    b = ComparisonRow("B", vol_annual=0.15, mean_annual=0.08, rvr=0.53, n_obs_common=100)
    assert dominates(a, b) is True
    assert dominates(b, a) is False


def test_dominates_false_on_exact_tie():
    a = ComparisonRow("A", vol_annual=0.10, mean_annual=0.10, rvr=1.0, n_obs_common=100)
    b = ComparisonRow("B", vol_annual=0.10, mean_annual=0.10, rvr=1.0, n_obs_common=100)
    assert dominates(a, b) is False
    assert dominates(b, a) is False


def test_dominates_false_when_tradeoff_exists():
    # Más media pero también más volatilidad -> ninguno domina.
    a = ComparisonRow("A", vol_annual=0.20, mean_annual=0.15, rvr=0.75, n_obs_common=100)
    b = ComparisonRow("B", vol_annual=0.10, mean_annual=0.08, rvr=0.8, n_obs_common=100)
    assert dominates(a, b) is False
    assert dominates(b, a) is False


def test_dominates_within_tolerance_counts_as_tie():
    a = ComparisonRow("A", vol_annual=0.10, mean_annual=0.10 + 1e-13, rvr=1.0, n_obs_common=100)
    b = ComparisonRow("B", vol_annual=0.10, mean_annual=0.10, rvr=1.0, n_obs_common=100)
    # Diferencia dentro de atol=1e-12 -> se trata como empate, no dominancia.
    assert dominates(a, b) is False


def test_compute_non_dominated_simple_case():
    rows = [
        ComparisonRow("A", vol_annual=0.10, mean_annual=0.15, rvr=1.5, n_obs_common=100),
        ComparisonRow("B", vol_annual=0.15, mean_annual=0.10, rvr=0.67, n_obs_common=100),
        ComparisonRow("C", vol_annual=0.20, mean_annual=0.05, rvr=0.25, n_obs_common=100),
    ]
    # A domina a B y C (más media, menos o igual volatilidad) -> solo A no dominado.
    assert compute_non_dominated(rows) == {"A"}


# --- reglas de selección (unitario) ------------------------------------------

def test_select_max_mean_under_risk_limit():
    rows = [
        ComparisonRow("LOW_RISK", vol_annual=0.10, mean_annual=0.08, rvr=0.8, n_obs_common=100),
        ComparisonRow("HIGH_RISK", vol_annual=0.30, mean_annual=0.20, rvr=0.67, n_obs_common=100),
    ]
    result = select_max_mean_under_risk_limit(rows, risk_limit=0.15)
    assert result.selected_tickers == ["LOW_RISK"]


def test_select_max_mean_under_risk_limit_empty_when_none_eligible():
    rows = [ComparisonRow("X", vol_annual=0.50, mean_annual=0.10, rvr=0.2, n_obs_common=100)]
    result = select_max_mean_under_risk_limit(rows, risk_limit=0.05)
    assert result.selected_tickers == []


def test_select_min_volatility_under_mean_floor():
    rows = [
        ComparisonRow("A", vol_annual=0.10, mean_annual=0.05, rvr=0.5, n_obs_common=100),
        ComparisonRow("B", vol_annual=0.20, mean_annual=0.12, rvr=0.6, n_obs_common=100),
    ]
    result = select_min_volatility_under_mean_floor(rows, mean_floor=0.10)
    assert result.selected_tickers == ["B"]


def test_select_max_rvr_excludes_undefined():
    rows = [
        ComparisonRow("ZERO_VOL", vol_annual=0.0, mean_annual=0.05, rvr=None, n_obs_common=100),
        ComparisonRow("BEST", vol_annual=0.10, mean_annual=0.10, rvr=1.0, n_obs_common=100),
    ]
    result = select_max_rvr(rows)
    assert result.selected_tickers == ["BEST"]


def test_select_non_dominated_set_can_return_multiple():
    rows = [
        ComparisonRow("A", vol_annual=0.10, mean_annual=0.10, rvr=1.0, n_obs_common=100),
        ComparisonRow("B", vol_annual=0.05, mean_annual=0.05, rvr=1.0, n_obs_common=100),
        ComparisonRow("C", vol_annual=0.20, mean_annual=0.05, rvr=0.25, n_obs_common=100),  # dominado por B
    ]
    result = select_non_dominated_set(rows)
    assert set(result.selected_tickers) == {"A", "B"}


# --- build_comparison_table: validaciones ------------------------------------

def test_build_comparison_table_rejects_fewer_than_20():
    provider = FixtureProvider(FIXTURE_CSV)
    fetch_result = fetch_and_clean_many(
        _TICKERS_20[:5], provider, *FULL_RANGE, frequency="Diaria"
    )
    with pytest.raises(InsufficientAssetsForComparison):
        build_comparison_table(fetch_result.ok, "Diaria")


def test_build_comparison_table_blocks_incompatible_currencies():
    provider = FixtureProvider(FIXTURE_CSV)
    fetch_result = fetch_and_clean_many(
        _TICKERS_20, provider, *FULL_RANGE, frequency="Diaria"
    )
    # Forzar una moneda distinta en un ticker para simular incompatibilidad.
    tampered = dict(fetch_result.ok)
    ticker0 = _TICKERS_20[0]
    original = tampered[ticker0]
    tampered[ticker0] = original.__class__(
        ticker=original.ticker,
        prices=original.prices,
        currency="EUR",
        timezone=original.timezone,
        source=original.source,
        price_adjusted=original.price_adjusted,
        cleaning_report=original.cleaning_report,
    )
    with pytest.raises(IncompatibleCurrencies):
        build_comparison_table(tampered, "Diaria")


# --- Verificación exacta contra las 20 filas oficiales (MAP-20-01) ----------

@pytest.fixture(scope="module")
def official_comparison_rows():
    provider = FixtureProvider(FIXTURE_CSV)
    fetch_result = fetch_and_clean_many(
        _TICKERS_20, provider, *FULL_RANGE, frequency="Diaria"
    )
    assert len(fetch_result.ok) == 20
    return build_comparison_table(fetch_result.ok, "Diaria")


def test_map_20_01_common_dates_and_full_coverage(official_comparison_rows):
    # Con este fixture todos comparten el mismo calendario -> la
    # intersección común conserva las 539 observaciones para todos.
    assert all(row.n_obs_common == 539 for row in official_comparison_rows)


def test_map_20_01_non_dominated_matches_official_column(official_comparison_rows):
    expected = pd.read_csv(EXPECTED_CSV).set_index("ticker")["non_dominated"]
    non_dominated = compute_non_dominated(official_comparison_rows)

    for row in official_comparison_rows:
        expected_flag = bool(expected.loc[row.ticker])
        actual_flag = row.ticker in non_dominated
        assert actual_flag == expected_flag, f"{row.ticker}: esperado {expected_flag}"


def test_map_20_01_selected_max_rvr_matches_official_column(official_comparison_rows):
    expected = pd.read_csv(EXPECTED_CSV).set_index("ticker")["selected_max_rvr"]
    expected_selected = expected[expected].index.tolist()
    assert len(expected_selected) == 1  # solo un ganador en el fixture oficial

    result = select_max_rvr(official_comparison_rows)
    assert result.selected_tickers == expected_selected
