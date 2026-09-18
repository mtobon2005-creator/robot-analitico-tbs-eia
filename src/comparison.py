"""RF-19 a RF-21: comparación de N activos, dominancia media-volatilidad
y reglas de preselección.

Verificado exactamente contra las columnas `non_dominated` y
`selected_max_rvr` de los 20 tickers oficiales
(Resultados_esperados_20_activos_TBS_EIA.csv) — ver
tests/unit/test_rf19_21_comparison.py.
"""
from dataclasses import dataclass
from functools import reduce

import numpy as np
import pandas as pd

from src.analytics import compute_log_returns, descriptive_stats
from src.config import N_MIN_ACTIVOS
from src.data import PriceSeries

ATOL_DOMINANCE = 1e-12
RTOL_DOMINANCE = 1e-10


class IncompatibleCurrencies(ValueError):
    pass


class InsufficientAssetsForComparison(ValueError):
    pass


# --- RF-19/RF-20: tabla comparable con coordenadas históricas ----------------

@dataclass(frozen=True)
class ComparisonRow:
    ticker: str
    vol_annual: float  # eje X del mapa (sección 5.8)
    mean_annual: float  # eje Y del mapa — estimador histórico, no promesa futura
    rvr: float | None  # razón individual media-volatilidad (None si vol=0)
    n_obs_common: int  # observaciones dentro de la ventana de fechas común


def _check_currency_compatibility(price_series_map: dict[str, PriceSeries]) -> str:
    """RF-20: 'sin conversión se bloquearán monedas incompatibles'."""
    currencies = {ps.currency for ps in price_series_map.values()}
    if len(currencies) > 1:
        raise IncompatibleCurrencies(
            f"Monedas incompatibles sin conversión declarada: {sorted(currencies)}. "
            "Todos los activos comparados deben compartir moneda base."
        )
    return currencies.pop()


def _common_date_index(price_series_map: dict[str, PriceSeries]) -> pd.DatetimeIndex:
    """RF-20: 'usar la intersección común de fechas después del
    remuestreo'. Las coordenadas del mapa NO dependen de H (MAP-H-01)."""
    indices = [ps.prices.index for ps in price_series_map.values()]
    return reduce(lambda a, b: a.intersection(b), indices)


def build_comparison_table(
    price_series_map: dict[str, PriceSeries], frequency: str
) -> list[ComparisonRow]:
    """RF-19: acumula los activos válidos en una tabla comparable. RF-20:
    intersección común de fechas, misma frecuencia/precio/log-rendimiento/
    anualización/moneda base — bloquea monedas incompatibles."""
    if len(price_series_map) < N_MIN_ACTIVOS:
        raise InsufficientAssetsForComparison(
            f"Se requieren al menos {N_MIN_ACTIVOS} activos válidos para "
            f"la vista comparativa; hay {len(price_series_map)}."
        )

    _check_currency_compatibility(price_series_map)
    common_index = _common_date_index(price_series_map)

    rows = []
    for ticker, ps in price_series_map.items():
        prices_common = ps.prices.loc[ps.prices.index.intersection(common_index)]
        returns_common = compute_log_returns(prices_common)
        stats_ = descriptive_stats(returns_common, frequency)
        rows.append(
            ComparisonRow(
                ticker=ticker,
                vol_annual=stats_.sd_annual,
                mean_annual=stats_.mean_annual,
                rvr=stats_.rvr,
                n_obs_common=stats_.n_obs,
            )
        )
    return rows


# --- RF-20: dominancia media-volatilidad -------------------------------------

def _ge(a: float, b: float) -> bool:
    return a > b or np.isclose(a, b, atol=ATOL_DOMINANCE, rtol=RTOL_DOMINANCE)


def _le(a: float, b: float) -> bool:
    return a < b or np.isclose(a, b, atol=ATOL_DOMINANCE, rtol=RTOL_DOMINANCE)


def dominates(a: ComparisonRow, b: ComparisonRow) -> bool:
    """A domina a B si A ofrece media histórica igual o mayor Y
    volatilidad igual o menor, con al menos una desigualdad ESTRICTA
    (fuera de tolerancia). No es dominancia estocástica (sección 5.8)."""
    same_mean = np.isclose(a.mean_annual, b.mean_annual, atol=ATOL_DOMINANCE, rtol=RTOL_DOMINANCE)
    same_vol = np.isclose(a.vol_annual, b.vol_annual, atol=ATOL_DOMINANCE, rtol=RTOL_DOMINANCE)
    if same_mean and same_vol:
        return False  # empate total -> ninguno domina al otro
    return bool(_ge(a.mean_annual, b.mean_annual) and _le(a.vol_annual, b.vol_annual))


def compute_non_dominated(rows: list[ComparisonRow]) -> set[str]:
    """Conjunto de activos que NINGÚN otro activo domina."""
    non_dominated = set()
    for row in rows:
        if not any(dominates(other, row) for other in rows if other.ticker != row.ticker):
            non_dominated.add(row.ticker)
    return non_dominated


# --- RF-21: reglas de preselección --------------------------------------------

@dataclass(frozen=True)
class SelectionResult:
    rule: str
    parameters: dict
    selected_tickers: list[str]  # puede tener 1 (reglas de máximo/mínimo) o más (no dominados)


def select_max_mean_under_risk_limit(
    rows: list[ComparisonRow], risk_limit: float
) -> SelectionResult:
    """'Máxima media histórica bajo límite de riesgo'."""
    eligible = [r for r in rows if _le(r.vol_annual, risk_limit)]
    if not eligible:
        return SelectionResult("max_media_bajo_limite_riesgo", {"risk_limit": risk_limit}, [])
    best = max(eligible, key=lambda r: r.mean_annual)
    return SelectionResult(
        "max_media_bajo_limite_riesgo", {"risk_limit": risk_limit}, [best.ticker]
    )


def select_min_volatility_under_mean_floor(
    rows: list[ComparisonRow], mean_floor: float
) -> SelectionResult:
    """'Mínima volatilidad bajo media mínima'."""
    eligible = [r for r in rows if _ge(r.mean_annual, mean_floor)]
    if not eligible:
        return SelectionResult("min_vol_bajo_media_minima", {"mean_floor": mean_floor}, [])
    best = min(eligible, key=lambda r: r.vol_annual)
    return SelectionResult(
        "min_vol_bajo_media_minima", {"mean_floor": mean_floor}, [best.ticker]
    )


def select_max_rvr(rows: list[ComparisonRow]) -> SelectionResult:
    """'Máxima razón individual media-volatilidad' (RVR). Excluye
    activos con volatilidad cero (RVR indefinida — sección 5.3)."""
    eligible = [r for r in rows if r.rvr is not None]
    if not eligible:
        return SelectionResult("max_rvr", {}, [])
    best = max(eligible, key=lambda r: r.rvr)
    return SelectionResult("max_rvr", {}, [best.ticker])


def select_non_dominated_set(rows: list[ComparisonRow]) -> SelectionResult:
    """'Conjunto no dominado' — sección 5.8: 'los activos no dominados
    pueden resaltarse, pero no forman una frontera eficiente de
    portafolios'."""
    non_dominated = compute_non_dominated(rows)
    return SelectionResult(
        "conjunto_no_dominado", {}, sorted(non_dominated)
    )
