"""Pruebas de conversión de monedas (GUIA_V2 §3.2, "P_COP=P_USD*FX")."""
import pandas as pd
import pytest

from src.fx import FxError, convert_price_series


def test_convert_price_series_matches_manual_calculation():
    prices = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2024-01-01", periods=3))
    result = convert_price_series(prices, rate=4000.0)
    pd.testing.assert_series_equal(result, pd.Series([4000.0, 8000.0, 12000.0], index=prices.index))


def test_convert_price_series_rate_one_is_identity():
    prices = pd.Series([10.5, 11.0, 9.75])
    result = convert_price_series(prices, rate=1.0)
    pd.testing.assert_series_equal(result, prices)


def test_convert_price_series_preserves_simple_returns():
    # Multiplicar por una constante no cambia los retornos porcentuales
    # — ver docstring del módulo. Verificación directa de esa propiedad.
    prices = pd.Series([100.0, 105.0, 98.0, 110.0])
    converted = convert_price_series(prices, rate=4000.0)
    original_returns = prices.pct_change().dropna()
    converted_returns = converted.pct_change().dropna()
    pd.testing.assert_series_equal(original_returns, converted_returns, check_exact=False, atol=1e-10)


def test_convert_price_series_rejects_non_positive_rate():
    prices = pd.Series([1.0, 2.0])
    with pytest.raises(FxError, match="rate"):
        convert_price_series(prices, rate=0.0)
    with pytest.raises(FxError, match="rate"):
        convert_price_series(prices, rate=-4000.0)
