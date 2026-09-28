"""Beta, CAPM y apalancamiento (v2, GUIA_V2 §8).

Beta por covarianza/varianza y por OLS con intercepto deben coincidir
exactamente para una regresión simple de una variable — es una
identidad matemática, no dos métodos independientes (P98). OLS además
da alpha, R² y error estándar, que cov/var no entrega por sí solo.

Hamada permite comparar el riesgo del negocio (beta desapalancada) sin
el efecto de la estructura de capital de un comparable, y reapalancarla
a la estructura objetivo de otra empresa (P105-P108).
"""
from dataclasses import dataclass

import numpy as np
from scipy import stats

# Un benchmark "constante" en punto flotante rara vez da varianza
# EXACTAMENTE 0.0 (ej. np.var([0.05]*3, ddof=1) ~= 7e-35 por redondeo
# binario) — comparar con == 0 dejaría pasar ruido numérico como si
# fuera una varianza real y produciría un beta absurdo en vez de
# reportarlo como indefinido.
_ZERO_VARIANCE_ATOL = 1e-12


class BetaCapmError(Exception):
    """Entrada inválida (series de distinta longitud, varianza cero,
    parámetros de apalancamiento fuera de rango)."""


@dataclass(frozen=True)
class OLSBetaResult:
    beta: float
    alpha: float
    r_squared: float
    std_err: float
    n: int


def beta_covariance(asset_returns, benchmark_returns) -> float:
    """beta = Cov(activo, benchmark) / Var(benchmark) (P98).

    Indefinida si el benchmark tiene varianza cero (benchmark
    constante) — se reporta como error explícito, no como división
    forzada (GUIA_V2 §8: "un benchmark constante produce una salida
    indefinida, no una división forzada")."""
    asset_returns = np.asarray(asset_returns, dtype=float)
    benchmark_returns = np.asarray(benchmark_returns, dtype=float)
    if asset_returns.shape != benchmark_returns.shape:
        raise BetaCapmError("asset_returns y benchmark_returns deben tener la misma longitud")
    if len(asset_returns) < 2:
        raise BetaCapmError("se necesitan al menos 2 observaciones")

    var_benchmark = np.var(benchmark_returns, ddof=1)
    if np.isclose(var_benchmark, 0.0, atol=_ZERO_VARIANCE_ATOL):
        raise BetaCapmError("varianza del benchmark es cero: beta indefinida")

    cov = np.cov(asset_returns, benchmark_returns, ddof=1)[0, 1]
    return float(cov / var_benchmark)


def beta_ols(asset_returns, benchmark_returns) -> OLSBetaResult:
    """Regresión OLS con intercepto: asset = alpha + beta*benchmark.
    El beta debe coincidir con `beta_covariance` (P98) — R²/alpha/error
    estándar son el diagnóstico adicional que cov/var no da (P100)."""
    asset_returns = np.asarray(asset_returns, dtype=float)
    benchmark_returns = np.asarray(benchmark_returns, dtype=float)
    if asset_returns.shape != benchmark_returns.shape:
        raise BetaCapmError("asset_returns y benchmark_returns deben tener la misma longitud")
    if len(asset_returns) < 3:
        raise BetaCapmError("se necesitan al menos 3 observaciones para un error estándar significativo")
    if np.isclose(np.var(benchmark_returns, ddof=1), 0.0, atol=_ZERO_VARIANCE_ATOL):
        raise BetaCapmError("varianza del benchmark es cero: regresión indefinida")

    result = stats.linregress(benchmark_returns, asset_returns)
    return OLSBetaResult(
        beta=float(result.slope),
        alpha=float(result.intercept),
        r_squared=float(result.rvalue ** 2),
        std_err=float(result.stderr),
        n=len(asset_returns),
    )


def unlever_beta(beta_L: float, tax: float, d_e: float, beta_D: float = 0.0) -> float:
    """Hamada: beta_U = (beta_L + beta_D*(1-tax)*D/E) / (1+(1-tax)*D/E)
    (GUIA_V2 §8.1). beta_D=0 (deuda sin riesgo sistemático) es el
    supuesto por defecto — pásalo explícito si la extensión con deuda
    riesgosa aplica a tu caso."""
    if not (0 <= tax < 1):
        raise BetaCapmError("tax debe estar en [0, 1)")
    if d_e < 0:
        raise BetaCapmError("D/E no puede ser negativo")
    return (beta_L + beta_D * (1 - tax) * d_e) / (1 + (1 - tax) * d_e)


def relever_beta(beta_U: float, tax: float, d_e: float, beta_D: float = 0.0) -> float:
    """Hamada: beta_L = beta_U + (beta_U-beta_D)*(1-tax)*D/E (GUIA_V2
    §8.1). Debe compartir el mismo supuesto de beta_D que se usó para
    desapalancar (P105: "ambas transformaciones deben compartir
    supuestos")."""
    if not (0 <= tax < 1):
        raise BetaCapmError("tax debe estar en [0, 1)")
    if d_e < 0:
        raise BetaCapmError("D/E no puede ser negativo")
    return beta_U + (beta_U - beta_D) * (1 - tax) * d_e


def capm_ke(rf: float, beta_L: float, erp: float, country_risk_premium: float = 0.0, lambda_: float = 1.0) -> float:
    """Ke = rf + beta_L*ERP + lambda*CRP (GUIA_V2 §8.2). country_risk_premium
    y lambda en 0 reproducen el CAPM básico sin extensión de país."""
    return rf + beta_L * erp + lambda_ * country_risk_premium


def convert_ke_by_inflation(ke_foreign: float, inflation_domestic: float, inflation_foreign: float) -> float:
    """Ke_dom = (1+Ke_foreign)*(1+infl_dom)/(1+infl_foreign) - 1
    (GUIA_V2 §8.2). Es un supuesto de consistencia nominal (paridad de
    tasas), no una predicción cierta de tipo de cambio (P111)."""
    if inflation_foreign <= -1:
        raise BetaCapmError("inflation_foreign debe ser mayor a -1")
    return (1 + ke_foreign) * (1 + inflation_domestic) / (1 + inflation_foreign) - 1
