"""Indicador técnico: momentum (v2, ruta de análisis técnico, GUIA_V2
§10.1/P129-136).

Momentum de N periodos: retorno acumulado desde t-N hasta t. El
mecanismo financiero que lo respalda es el efecto de continuación de
tendencia documentado en finanzas empíricas — es una hipótesis
falsable (P129), no una certeza ni una garantía de que se repita.
"""
from dataclasses import dataclass

import pandas as pd


class TechnicalIndicatorError(Exception):
    """Entrada inválida (ventana no positiva, historia insuficiente,
    precio base no positivo)."""


@dataclass(frozen=True)
class MomentumResult:
    ticker: str
    momentum: float  # retorno acumulado simple en la ventana
    window: int
    n_obs: int


def momentum(prices: pd.Series, window: int) -> float:
    """(P_t / P_(t-window)) - 1. Requiere al menos window+1 precios
    (P130: barras completas, no barras incompletas)."""
    if window <= 0:
        raise TechnicalIndicatorError("window debe ser positivo")
    if len(prices) < window + 1:
        raise TechnicalIndicatorError(
            f"se necesitan al menos {window + 1} precios, hay {len(prices)}"
        )
    p_now = float(prices.iloc[-1])
    p_past = float(prices.iloc[-(window + 1)])
    if p_past <= 0:
        raise TechnicalIndicatorError("precio base no positivo")
    return p_now / p_past - 1


def rank_by_momentum(price_series_map: dict[str, pd.Series], window: int) -> list[MomentumResult]:
    """Ordena los activos de mayor a menor momentum de `window`
    periodos. Un activo con historia insuficiente se omite (no se
    rellena ni detiene a los demás — mismo principio de aislamiento de
    fallos que RF-08)."""
    results = []
    for ticker, prices in price_series_map.items():
        try:
            m = momentum(prices, window)
        except TechnicalIndicatorError:
            continue
        results.append(MomentumResult(ticker=ticker, momentum=m, window=window, n_obs=len(prices)))
    return sorted(results, key=lambda r: r.momentum, reverse=True)
