"""RF-09 a RF-12: análisis histórico del activo.

RF-10: exclusivamente rendimientos logarítmicos — este módulo no
ofrece ninguna ruta de cálculo con rendimientos simples (verificado
contra LOG-01: precios 100,110,99 -> g=[0.0953..., -0.1054...], nunca
0.10/-0.10).

Todos los cálculos verificados numéricamente contra
`tests/fixtures/Resultados_esperados_20_activos_TBS_EIA.csv` (columna
por columna, ver tests/unit/test_rf09_12_analytics.py).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from src.config import FRECUENCIAS

_ECUACION_RENDIMIENTO_LOGARITMICO = "g_t = ln(P_t / P_(t-1))"


# --- RF-10: rendimiento exclusivamente logarítmico --------------------------

def compute_log_returns(prices: pd.Series) -> pd.Series:
    """g_t = ln(P_t / P_(t-1)). Única definición de rendimiento admitida
    (RF-10) — nunca (P_t - P_(t-1)) / P_(t-1)."""
    if (prices <= 0).any():
        raise ValueError(
            "Los precios deben ser estrictamente positivos para calcular "
            "log-rendimientos (deberían haberse filtrado en RF-06)."
        )
    return np.log(prices / prices.shift(1)).dropna()


# --- RF-11: estadísticas descriptivas y anualización ------------------------

@dataclass(frozen=True)
class DescriptiveStats:
    n_obs: int
    mean_period: float
    median_period: float
    variance_period: float  # muestral, ddof=1
    sd_period: float
    min_: float
    p25: float
    p75: float
    max_: float
    skewness: float  # Fisher-Pearson, corregida por sesgo
    excess_kurtosis: float  # Fisher, corregida por sesgo
    mean_annual: float
    sd_annual: float
    rvr: float | None  # media_anual / vol_anual; None si vol_anual == 0


def annualization_factor(frequency: str) -> int:
    if frequency not in FRECUENCIAS:
        raise ValueError(f"Frecuencia desconocida: '{frequency}'.")
    return FRECUENCIAS[frequency]


def descriptive_stats(returns: pd.Series, frequency: str) -> DescriptiveStats:
    """Sección 5.3 de la guía: media, mediana, varianza muestral,
    desviación estándar, mín/p25/p75/máx, asimetría y exceso de
    curtosis (Fisher, corregidos por sesgo — scipy bias=False),
    anualizados con μ_anual = m·ḡ y σ_anual = √m·s_g."""
    m = annualization_factor(frequency)
    n = len(returns)
    mean_period = float(returns.mean())
    sd_period = float(returns.std(ddof=1))  # muestral
    mean_annual = mean_period * m
    sd_annual = sd_period * np.sqrt(m)
    rvr = (mean_annual / sd_annual) if sd_annual != 0 else None

    return DescriptiveStats(
        n_obs=n,
        mean_period=mean_period,
        median_period=float(returns.median()),
        variance_period=float(returns.var(ddof=1)),
        sd_period=sd_period,
        min_=float(returns.min()),
        p25=float(np.percentile(returns, 25, method="linear")),
        p75=float(np.percentile(returns, 75, method="linear")),
        max_=float(returns.max()),
        skewness=float(stats.skew(returns, bias=False)),
        excess_kurtosis=float(stats.kurtosis(returns, fisher=True, bias=False)),
        mean_annual=mean_annual,
        sd_annual=sd_annual,
        rvr=rvr,
    )


def quantile_type7(returns: pd.Series, q: float) -> float:
    """Cuantil lineal tipo 7 (sección 5.3, 'CONVENCIONES REPRODUCIBLES').
    `q` en [0, 100] (ej. 5 para el percentil 5, 95 para el percentil 95)."""
    return float(np.percentile(returns, q, method="linear"))


# --- RF-12: contexto del presente (drawdown, percentil, ventana reciente) ---

def compute_drawdown_series(prices: pd.Series) -> pd.Series:
    """D_t = P_t / max_{s<=t}(P_s) - 1 (sección 4, tabla de símbolos).
    Se calcula sobre PRECIOS, nunca sobre rendimientos."""
    running_max = prices.cummax()
    return prices / running_max - 1


def max_drawdown(prices: pd.Series) -> float:
    return float(compute_drawdown_series(prices).min())


def last_return_percentile_midrank(returns: pd.Series) -> float:
    """Percentil (0-100) del último rendimiento dentro de la muestra
    completa, usando el método midrank (promedia rangos en empates —
    scipy kind='mean')."""
    last_value = returns.iloc[-1]
    return float(stats.percentileofscore(returns.values, last_value, kind="mean"))


@dataclass(frozen=True)
class RecentWindowComparison:
    full_sample: DescriptiveStats
    recent_window: DescriptiveStats
    recent_window_size: int
    is_partial: bool  # True si T < m (ventana reciente rotulada 'parcial')


def compare_full_vs_recent_window(
    returns: pd.Series, frequency: str
) -> RecentWindowComparison:
    """Punto RF-12: 'comparación entre muestra completa y ventana
    reciente min(m, T)'. Si T < m, la ventana reciente es en realidad
    toda la muestra y debe rotularse como parcial."""
    m = annualization_factor(frequency)
    t = len(returns)
    window_size = min(m, t)
    recent = returns.iloc[-window_size:]

    return RecentWindowComparison(
        full_sample=descriptive_stats(returns, frequency),
        recent_window=descriptive_stats(recent, frequency),
        recent_window_size=window_size,
        is_partial=t < m,
    )


@dataclass(frozen=True)
class PresentContext:
    last_price: float
    last_date: pd.Timestamp
    last_log_return: float
    drawdown_now: float
    max_drawdown_value: float
    last_return_percentile: float


def build_present_context(prices: pd.Series, returns: pd.Series) -> PresentContext:
    """RF-12: 'mostrar último precio y fecha, último log-rendimiento,
    drawdown D_t, máxima caída, percentil midrank del último
    rendimiento'."""
    drawdown_series = compute_drawdown_series(prices)
    return PresentContext(
        last_price=float(prices.iloc[-1]),
        last_date=prices.index[-1],
        last_log_return=float(returns.iloc[-1]),
        drawdown_now=float(drawdown_series.iloc[-1]),
        max_drawdown_value=float(drawdown_series.min()),
        last_return_percentile=last_return_percentile_midrank(returns),
    )
