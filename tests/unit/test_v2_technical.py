"""Pruebas del indicador técnico de momentum (GUIA_V2 §10.1, P129-136)."""
import pandas as pd
import pytest

from src.technical import TechnicalIndicatorError, momentum, rank_by_momentum


def _prices(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx)


def test_momentum_matches_manual_ratio():
    prices = _prices([100, 101, 102, 103, 104, 105, 110])
    # (110/100) - 1, ventana de 6 periodos (7 precios -> índice -7 es el primero)
    result = momentum(prices, window=6)
    assert result == pytest.approx(0.10, abs=1e-12)


def test_momentum_zero_when_price_unchanged():
    prices = _prices([100, 105, 95, 100])
    assert momentum(prices, window=3) == pytest.approx(0.0, abs=1e-12)


def test_momentum_negative_on_decline():
    prices = _prices([100, 90, 80])
    assert momentum(prices, window=2) == pytest.approx(-0.20, abs=1e-12)


def test_momentum_rejects_non_positive_window():
    with pytest.raises(TechnicalIndicatorError, match="positiv"):
        momentum(_prices([100, 101, 102]), window=0)


def test_momentum_rejects_insufficient_history():
    with pytest.raises(TechnicalIndicatorError, match="al menos"):
        momentum(_prices([100, 101, 102]), window=5)


def test_momentum_rejects_nonpositive_base_price():
    prices = _prices([-5, 10, 20])
    with pytest.raises(TechnicalIndicatorError, match="no positivo"):
        momentum(prices, window=2)


def test_rank_by_momentum_orders_descending():
    price_map = {
        "A": _prices([100, 110]),  # +10%
        "B": _prices([100, 90]),  # -10%
        "C": _prices([100, 105]),  # +5%
    }
    ranking = rank_by_momentum(price_map, window=1)
    assert [r.ticker for r in ranking] == ["A", "C", "B"]
    assert ranking[0].momentum == pytest.approx(0.10, abs=1e-12)


def test_rank_by_momentum_skips_insufficient_history_without_failing_others():
    price_map = {
        "SHORT": _prices([100, 101]),  # solo 2 precios, insuficiente para window=5
        "LONG": _prices([100, 101, 102, 103, 104, 120]),
    }
    ranking = rank_by_momentum(price_map, window=5)
    assert [r.ticker for r in ranking] == ["LONG"]
