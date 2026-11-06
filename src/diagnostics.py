"""Diagnósticos de los supuestos del modelo sobre un activo individual
(Guía de Sustentación Final, "Historia y supuestos": "diagnósticos de
normalidad, autocorrelación y homocedasticidad [...] distingue
estimación histórica, pronóstico y falta de evidencia").

Jarque-Bera usa scipy.stats directamente (ya está en scipy). Ljung-Box
y ARCH-LM usan statsmodels en vez de reimplementar las fórmulas a
mano — son tests estadísticos no triviales y la librería ya está
revisada por pares; verificados contra casos sintéticos conocidos
(ruido blanco i.i.d. no rechaza nada; un AR(1) fuerte rechaza
Ljung-Box; una t-student de colas pesadas rechaza Jarque-Bera; un
proceso ARCH(1) real rechaza ARCH-LM) antes de confiar en la llamada.
"""
from dataclasses import dataclass

import numpy as np
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch


class DiagnosticsError(Exception):
    """Muestra insuficiente para el diagnóstico pedido."""


@dataclass(frozen=True)
class NormalityTest:
    statistic: float
    p_value: float
    rejects_normality: bool  # al nivel alpha
    interpretation: str


def jarque_bera_test(returns, alpha: float = 0.05) -> NormalityTest:
    """H0: los retornos provienen de una distribución normal (en
    asimetría y curtosis). Se rechaza H0 si p_value < alpha."""
    returns = np.asarray(returns, dtype=float)
    if len(returns) < 8:  # mínimo razonable para el test asintótico
        raise DiagnosticsError("se necesitan al menos 8 observaciones")
    statistic, p_value = stats.jarque_bera(returns)
    rejects = bool(p_value < alpha)
    interpretation = (
        f"Se rechaza la normalidad al {alpha:.0%}: la distribución muestral "
        "de los retornos difiere de una normal en asimetría y/o curtosis."
        if rejects else
        f"No se rechaza la normalidad al {alpha:.0%}: no hay evidencia "
        "suficiente para descartar que los retornos provienen de una normal."
    )
    return NormalityTest(float(statistic), float(p_value), rejects, interpretation)


@dataclass(frozen=True)
class AutocorrelationTest:
    lags: int
    statistic: float
    p_value: float
    rejects_independence: bool
    interpretation: str


def ljung_box_test(returns, lags: int = 10, alpha: float = 0.05) -> AutocorrelationTest:
    """H0: los retornos no están autocorrelacionados hasta `lags`
    rezagos. Se rechaza H0 (independencia) si p_value < alpha."""
    returns = np.asarray(returns, dtype=float)
    if len(returns) <= lags:
        raise DiagnosticsError(f"se necesitan más de {lags} observaciones")
    result = acorr_ljungbox(returns, lags=[lags], return_df=True)
    statistic = float(result["lb_stat"].iloc[-1])
    p_value = float(result["lb_pvalue"].iloc[-1])
    rejects = bool(p_value < alpha)
    interpretation = (
        f"Se rechaza independencia al {alpha:.0%} (rezago {lags}): hay "
        "autocorrelación significativa — el supuesto de retornos i.i.d. "
        "no se sostiene para este activo y esta muestra."
        if rejects else
        f"No se rechaza independencia al {alpha:.0%} (rezago {lags}): no "
        "hay evidencia suficiente de autocorrelación en los retornos."
    )
    return AutocorrelationTest(lags, statistic, p_value, rejects, interpretation)


@dataclass(frozen=True)
class HomoscedasticityTest:
    lags: int
    statistic: float
    p_value: float
    rejects_homoscedasticity: bool
    interpretation: str


def arch_lm_test(returns, lags: int = 5, alpha: float = 0.05) -> HomoscedasticityTest:
    """H0: no hay efectos ARCH (varianza condicional constante) hasta
    `lags` rezagos. Se rechaza H0 (homocedasticidad) si p_value < alpha."""
    returns = np.asarray(returns, dtype=float)
    if len(returns) <= lags:
        raise DiagnosticsError(f"se necesitan más de {lags} observaciones")
    lm_stat, lm_pvalue, _, _ = het_arch(returns, nlags=lags)
    rejects = bool(lm_pvalue < alpha)
    interpretation = (
        f"Se rechaza homocedasticidad al {alpha:.0%} (ARCH-LM, {lags} "
        "rezagos): hay efectos ARCH (varianza condicional dependiente del "
        "tiempo) — el supuesto homocedástico de los modelos A/B no se "
        "sostiene estrictamente para este activo y esta muestra."
        if rejects else
        f"No se rechaza homocedasticidad al {alpha:.0%} (ARCH-LM, {lags} "
        "rezagos): no hay evidencia suficiente de efectos ARCH."
    )
    return HomoscedasticityTest(lags, float(lm_stat), float(lm_pvalue), rejects, interpretation)
