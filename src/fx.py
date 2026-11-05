"""Conversión de precios entre monedas para comparar/optimizar activos
en distinta moneda dentro del mismo portafolio (GUIA_V2 §3.2, mandato
v2: "P_COP=P_USD*FX" — no implementada hasta ahora, portafolios con
monedas mixtas se bloqueaban en vez de convertirse).

Supuesto deliberado: la tasa de cambio es CONSTANTE durante toda la
ventana de datos (un solo número, no una serie histórica de FX). Esto
tiene una consecuencia matemática importante que hay que tener
presente al leer los resultados: multiplicar una serie de precios
completa por una constante NO cambia sus retornos porcentuales
((c·P_t)/(c·P_{t-1}) - 1 = P_t/P_{t-1} - 1), así que esta conversión
NO modifica mu, Sigma ni los pesos óptimos de Markowitz — solo permite
dejar de bloquear el portafolio y expresar montos (VaR, rebalanceo,
ficha técnica) en una sola moneda consistente. No modela el riesgo
cambiario en sí (la volatilidad de la tasa de cambio), que requeriría
una serie histórica de FX, no un solo número.
"""
import pandas as pd


class FxError(Exception):
    """Tasa de cambio inválida."""


def convert_price_series(prices: pd.Series, rate: float) -> pd.Series:
    """P_base = P_moneda_original * rate, con rate = cuántas unidades
    de la moneda BASE equivalen a 1 unidad de la moneda original del
    precio (ej. rate=4000 convierte una serie en USD a COP si en ese
    momento 1 USD = 4000 COP)."""
    if rate <= 0:
        raise FxError("rate debe ser positivo")
    return prices * rate
