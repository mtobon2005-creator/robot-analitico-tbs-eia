"""Pruebas RF-05 a RF-08.

Usa el fixture oficial y el mock configurable — NINGUNA prueba depende
de internet (PROVIDER-01, T-03).
"""
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.data import (
    EmptyResponse,
    FetchResult,
    FixtureProvider,
    InsufficientSample,
    MockProvider,
    ProviderTimeout,
    TickerNotFound,
    clean_prices,
    fetch_and_clean_many,
    resample_prices,
    validate_sufficient_sample,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_CSV = FIXTURES_DIR / "Fixture_20_activos_sintetico_TBS_EIA.csv"

FULL_RANGE = (date(2024, 7, 19), date(2026, 8, 13))  # rango completo del fixture


@pytest.fixture
def fixture_provider():
    return FixtureProvider(FIXTURE_CSV)


# --- RF-05: FixtureProvider --------------------------------------------------

def test_fixture_provider_fetches_known_ticker(fixture_provider):
    raw = fixture_provider.fetch("AAPL", *FULL_RANGE)
    assert raw.ticker == "AAPL"
    assert len(raw.dates) == 540
    assert raw.currency == "USD"
    assert raw.timezone == "America/New_York"
    assert raw.price_adjusted is True


def test_fixture_provider_raises_ticker_not_found_for_unknown(fixture_provider):
    with pytest.raises(TickerNotFound):
        fixture_provider.fetch("EIA_INVALID_2026", *FULL_RANGE)


def test_fixture_provider_raises_empty_response_outside_range(fixture_provider):
    with pytest.raises(EmptyResponse):
        fixture_provider.fetch("AAPL", date(2030, 1, 1), date(2030, 2, 1))


@pytest.mark.parametrize(
    "ticker",
    ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "JPM", "JNJ", "XOM", "PG",
     "KO", "PEP", "WMT", "HD", "COST", "UNH", "V", "MA", "CAT", "MCD"],
)
def test_fixture_provider_covers_all_20_official_tickers(fixture_provider, ticker):
    raw = fixture_provider.fetch(ticker, *FULL_RANGE)
    assert len(raw.dates) == 540


# --- MockProvider (PROVIDER-01) ----------------------------------------------

def test_mock_provider_valid_case():
    provider = MockProvider({"OK1": "valid"})
    raw = provider.fetch("OK1", date(2026, 1, 1), date(2026, 2, 1))
    assert len(raw.prices) == 35
    assert all(p > 0 for p in raw.prices)


def test_mock_provider_empty_case():
    provider = MockProvider({"E1": "empty"})
    with pytest.raises(EmptyResponse):
        provider.fetch("E1", date(2026, 1, 1), date(2026, 2, 1))


def test_mock_provider_timeout_case():
    provider = MockProvider({"T1": "timeout"})
    with pytest.raises(ProviderTimeout):
        provider.fetch("T1", date(2026, 1, 1), date(2026, 2, 1))


def test_mock_provider_ticker_missing_case():
    provider = MockProvider({})  # nada configurado -> ticker_missing por defecto
    with pytest.raises(TickerNotFound):
        provider.fetch("NOPE", date(2026, 1, 1), date(2026, 2, 1))


def test_mock_provider_nonpositive_case_is_cleaned_out():
    provider = MockProvider({"NP1": "nonpositive"})
    raw = provider.fetch("NP1", date(2026, 1, 1), date(2026, 2, 1))
    series, report = clean_prices(raw)
    assert report["dropped_nonpositive"] == 1
    assert (series > 0).all()


# --- RF-06: limpieza ---------------------------------------------------------

def test_clean_prices_sorts_dates():
    from src.data import RawPriceResponse

    raw = RawPriceResponse(
        ticker="X",
        dates=[date(2026, 1, 3), date(2026, 1, 1), date(2026, 1, 2)],
        prices=[3.0, 1.0, 2.0],
        currency="USD",
        timezone="UTC",
        source="test",
    )
    series, _ = clean_prices(raw)
    assert list(series.values) == [1.0, 2.0, 3.0]


def test_clean_prices_drops_duplicate_dates_keeps_last():
    from src.data import RawPriceResponse

    raw = RawPriceResponse(
        ticker="X",
        dates=[date(2026, 1, 1), date(2026, 1, 1)],
        prices=[10.0, 20.0],
        currency="USD",
        timezone="UTC",
        source="test",
    )
    series, report = clean_prices(raw)
    assert len(series) == 1
    assert series.iloc[0] == 20.0  # keep='last'
    assert report["dropped_duplicates"] == 1


def test_clean_prices_reports_dropped_nonpositive_explicitly():
    from src.data import RawPriceResponse

    raw = RawPriceResponse(
        ticker="X",
        dates=[date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)],
        prices=[10.0, -1.0, 0.0],
        currency="USD",
        timezone="UTC",
        source="test",
    )
    series, report = clean_prices(raw)
    assert len(series) == 1
    assert report["dropped_nonpositive"] == 2


def test_fixture_aapl_survives_cleaning_with_no_drops(fixture_provider):
    raw = fixture_provider.fetch("AAPL", *FULL_RANGE)
    series, report = clean_prices(raw)
    assert report["dropped_duplicates"] == 0
    assert report["dropped_missing"] == 0
    assert report["dropped_nonpositive"] == 0
    assert len(series) == 540


# --- RF-07: remuestreo (verificado contra RESAMPLE-01) ----------------------

def test_resample_daily_is_noop(fixture_provider):
    raw = fixture_provider.fetch("AAPL", *FULL_RANGE)
    series, _ = clean_prices(raw)
    resampled = resample_prices(series, "Diaria")
    assert len(resampled) == len(series)


def test_resample_weekly_matches_official_matrix_count(fixture_provider):
    # RESAMPLE-01: weekly_prices=109 para AAPL en el fixture oficial.
    raw = fixture_provider.fetch("AAPL", *FULL_RANGE)
    series, _ = clean_prices(raw)
    weekly = resample_prices(series, "Semanal")
    assert len(weekly) == 109


def test_resample_monthly_matches_official_matrix_count(fixture_provider):
    # RESAMPLE-01: monthly_prices=26 para AAPL en el fixture oficial.
    raw = fixture_provider.fetch("AAPL", *FULL_RANGE)
    series, _ = clean_prices(raw)
    monthly = resample_prices(series, "Mensual")
    assert len(monthly) == 26


def test_resample_uses_last_price_of_period_not_first():
    idx = pd.date_range("2026-01-01", periods=10, freq="D")  # incluye 2 fines de semana
    series = pd.Series(range(1, 11), index=idx, dtype=float)
    weekly = resample_prices(series, "Semanal")
    # El último valor de la primera semana (hasta el viernes 2026-01-02)
    # debe ser el precio del viernes, no el del jueves ni el domingo.
    first_period_last_value = weekly.iloc[0]
    assert first_period_last_value == series.loc["2026-01-02"]


# --- RF-08: muestra insuficiente y orquestación multi-ticker -----------------

def test_validate_sufficient_sample_rejects_short_series():
    short = pd.Series([1.0, 2.0, 3.0])
    with pytest.raises(InsufficientSample):
        validate_sufficient_sample(short, minimum=30)


def test_validate_sufficient_sample_accepts_long_enough_series():
    long_series = pd.Series(range(50), dtype=float)
    validate_sufficient_sample(long_series, minimum=30)  # no debe lanzar


def test_fetch_and_clean_many_partial_failure_keeps_valid_results(fixture_provider):
    # FAIL-20P1-01 / T-06: 20 tickers válidos + EIA_INVALID_2026 ->
    # conserva los 20 válidos y reporta el error aislado.
    valid_tickers = [
        "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "JPM", "JNJ", "XOM",
        "PG", "KO", "PEP", "WMT", "HD", "COST", "UNH", "V", "MA", "CAT", "MCD",
    ]
    tickers = valid_tickers + ["EIA_INVALID_2026"]

    result = fetch_and_clean_many(
        tickers, fixture_provider, *FULL_RANGE, frequency="Diaria"
    )

    assert len(result.ok) == 20
    assert set(result.ok.keys()) == set(valid_tickers)
    assert "EIA_INVALID_2026" in result.errors
    assert "TickerNotFound" in result.errors["EIA_INVALID_2026"]


def test_fetch_and_clean_many_mixed_mock_behaviors_isolated():
    provider = MockProvider(
        {"OK1": "valid", "OK2": "valid", "E1": "empty", "T1": "timeout"}
    )
    result = fetch_and_clean_many(
        ["OK1", "OK2", "E1", "T1"],
        provider,
        date(2026, 1, 1),
        date(2026, 2, 1),
        frequency="Diaria",
        min_observations=10,
    )
    assert set(result.ok.keys()) == {"OK1", "OK2"}
    assert set(result.errors.keys()) == {"E1", "T1"}


def test_fetch_and_clean_many_returns_dataclass():
    result = fetch_and_clean_many(
        [], MockProvider({}), date(2026, 1, 1), date(2026, 2, 1), frequency="Diaria"
    )
    assert isinstance(result, FetchResult)
    assert result.ok == {}
    assert result.errors == {}
