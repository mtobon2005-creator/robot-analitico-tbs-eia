"""Optimización de cartera media-varianza para N activos (v2, GUIA_V2 §5).

Generaliza el cálculo manual de dos activos (ver v2/documentos/GUIA_V2.md
y la demostración con v2/data/dos_activos.json): con N=2 y cotas no
activas, global_min_variance y tangency_portfolio deben reproducir las
fórmulas cerradas Sigma^-1*1/(1'*Sigma^-1*1) y la normalización de
Sigma^-1*(mu-rf*1). Con N>2 o cotas activas no hay fórmula cerrada en
general, por eso se resuelve con SLSQP (scipy).
"""
from dataclasses import dataclass

import numpy as np
from scipy import stats
from scipy.optimize import minimize


class PortfolioOptimizationError(Exception):
    """El solver no convergió, o el problema es inviable o no acotado."""


@dataclass(frozen=True)
class PortfolioResult:
    weights: np.ndarray
    expected_return: float
    volatility: float
    solver_success: bool
    solver_message: str


def _validate_inputs(mu: np.ndarray, Sigma: np.ndarray, bounds) -> None:
    n = len(mu)
    if Sigma.shape != (n, n):
        raise ValueError("Sigma debe ser NxN, con N=len(mu)")
    if not np.allclose(Sigma, Sigma.T, atol=1e-10):
        raise ValueError("Sigma no es simétrica")
    if len(bounds) != n:
        raise ValueError("bounds debe tener un par (lo, hi) por activo")


def _portfolio_stats(w: np.ndarray, mu: np.ndarray, Sigma: np.ndarray) -> tuple[float, float]:
    mu_p = float(w @ mu)
    var_p = float(w @ Sigma @ w)
    return mu_p, float(np.sqrt(max(var_p, 0.0)))


def _budget_constraint():
    return {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}


# ftol por defecto de SLSQP (1e-6) es insuficiente para el ratio de
# Sharpe cerca del óptimo (ver P2-13): se aprieta la tolerancia del
# solver en vez de relajar la de las pruebas de control.
_SOLVER_OPTIONS = {"ftol": 1e-12, "maxiter": 1000}


def global_min_variance(mu, Sigma, bounds=None) -> PortfolioResult:
    """min(w'Sigma w) sujeto a suma(w)=1 y w en `bounds` (GUIA_V2 §5.1)."""
    mu = np.asarray(mu, dtype=float)
    Sigma = np.asarray(Sigma, dtype=float)
    n = len(mu)
    bounds = bounds or [(0.0, 1.0)] * n
    _validate_inputs(mu, Sigma, bounds)

    w0 = np.full(n, 1.0 / n)
    res = minimize(
        lambda w: w @ Sigma @ w,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=[_budget_constraint()],
        options=_SOLVER_OPTIONS,
    )
    if not res.success:
        raise PortfolioOptimizationError(res.message)
    mu_p, sigma_p = _portfolio_stats(res.x, mu, Sigma)
    return PortfolioResult(res.x, mu_p, sigma_p, res.success, res.message)


def efficient_frontier(mu, Sigma, target_returns, bounds=None):
    """Para cada r en `target_returns`: min(w'Sigma w) s.a. w'mu=r,
    suma(w)=1, w en `bounds` (GUIA_V2 §5). Un r por debajo del mínimo
    alcanzable o por encima del máximo bajo las cotas es inviable y se
    reporta aparte, no se descarta en silencio (P2-14, P2-15)."""
    mu = np.asarray(mu, dtype=float)
    Sigma = np.asarray(Sigma, dtype=float)
    n = len(mu)
    bounds = bounds or [(0.0, 1.0)] * n
    _validate_inputs(mu, Sigma, bounds)

    results: list[PortfolioResult] = []
    infeasible: list[tuple[float, str]] = []
    w0 = np.full(n, 1.0 / n)
    for r in target_returns:
        constraints = [
            _budget_constraint(),
            {"type": "eq", "fun": lambda w, r=r: w @ mu - r},
        ]
        res = minimize(
            lambda w: w @ Sigma @ w,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options=_SOLVER_OPTIONS,
        )
        if res.success:
            mu_p, sigma_p = _portfolio_stats(res.x, mu, Sigma)
            results.append(PortfolioResult(res.x, mu_p, sigma_p, True, res.message))
        else:
            infeasible.append((float(r), res.message))
    return results, infeasible


def tangency_portfolio(mu, Sigma, rf, bounds=None) -> PortfolioResult:
    """max (w'mu-rf)/sqrt(w'Sigma w) sujeto a suma(w)=1, w en `bounds`
    (GUIA_V2 §5.2). No es la misma cartera que el óptimo personal salvo
    que gamma la reproduzca exactamente (ver P58)."""
    mu = np.asarray(mu, dtype=float)
    Sigma = np.asarray(Sigma, dtype=float)
    n = len(mu)
    bounds = bounds or [(0.0, 1.0)] * n
    _validate_inputs(mu, Sigma, bounds)

    def neg_sharpe(w):
        mu_p, sigma_p = _portfolio_stats(w, mu, Sigma)
        if sigma_p <= 0:
            return 0.0
        return -(mu_p - rf) / sigma_p

    w0 = np.full(n, 1.0 / n)
    res = minimize(
        neg_sharpe,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=[_budget_constraint()],
        options=_SOLVER_OPTIONS,
    )
    if not res.success:
        raise PortfolioOptimizationError(res.message)
    mu_p, sigma_p = _portfolio_stats(res.x, mu, Sigma)
    return PortfolioResult(res.x, mu_p, sigma_p, res.success, res.message)


def max_expected_return(mu, Sigma, bounds=None) -> PortfolioResult:
    """max(w'mu) sujeto a suma(w)=1, w en `bounds`. Puede concentrarse
    en un solo activo si las cotas lo permiten (GUIA_V2, tabla 5.1)."""
    mu = np.asarray(mu, dtype=float)
    Sigma = np.asarray(Sigma, dtype=float)
    n = len(mu)
    bounds = bounds or [(0.0, 1.0)] * n
    _validate_inputs(mu, Sigma, bounds)

    w0 = np.full(n, 1.0 / n)
    res = minimize(
        lambda w: -(w @ mu),
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=[_budget_constraint()],
        options=_SOLVER_OPTIONS,
    )
    if not res.success:
        raise PortfolioOptimizationError(res.message)
    mu_p, sigma_p = _portfolio_stats(res.x, mu, Sigma)
    return PortfolioResult(res.x, mu_p, sigma_p, res.success, res.message)


def portfolio_log_returns(simple_returns, weights) -> np.ndarray:
    """Retorno log de la cartera por periodo, para usarla como benchmark
    de beta (GUIA_V2 §8, "beta frente al índice de mercado o el
    portafolio óptimo").

    Los retornos individuales se agregan en espacio SIMPLE porque son
    los que se suman linealmente ponderados por peso (GUIA_V2 §4.1,
    agregación de cartera) — un log-retorno simple ponderado no es el
    log-retorno real de la cartera. El resultado agregado se convierte
    a log (ln(1+r_simple)) para quedar en la misma convención que el
    resto de los retornos de activo individual usados en beta (RF-09)."""
    simple_returns = np.asarray(simple_returns, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if simple_returns.ndim != 2:
        raise ValueError("simple_returns debe ser una matriz TxN")
    if simple_returns.shape[1] != len(weights):
        raise ValueError("weights debe tener un valor por columna de simple_returns")
    portfolio_simple = simple_returns @ weights
    if np.any(portfolio_simple <= -1):
        raise ValueError("retorno simple de cartera <= -100% no tiene log-retorno definido")
    return np.log1p(portfolio_simple)


def portfolio_var(expected_return: float, volatility: float, confidence: float, capital: float) -> dict:
    """VaR paramétrico normal de la cartera a 1 año, sobre el mismo
    retorno/volatilidad SIMPLE anualizados de Markowitz (GUIA_V2 §9,
    ficha técnica) — no es el VaR log-normal de RF-16 (ese es por
    activo individual y depende de un horizonte de forecasting A/B que
    Markowitz no usa).

    VaR_frac = max(0, -(mu_p - z_c*sigma_p)); VaR_$ = capital*VaR_frac.
    """
    if not (0 < confidence < 1):
        raise ValueError("confidence debe estar en (0, 1)")
    if volatility < 0:
        raise ValueError("volatility no puede ser negativa")
    if capital < 0:
        raise ValueError("capital no puede ser negativo")

    z_c = float(stats.norm.ppf(confidence))
    fraction = max(0.0, -(float(expected_return) - z_c * float(volatility)))
    return {"fraction": fraction, "monetary": fraction * capital, "confidence": confidence}


def personal_optimum(mu, Sigma, gamma, bounds=None) -> PortfolioResult:
    """max U(w)=w'mu-(gamma/2)*w'Sigma*w sujeto a suma(w)=1, w en
    `bounds` (GUIA_V2 §5.1). gamma es del inversionista, no se infiere
    de los precios (P57) — debe llegar como parámetro explícito."""
    if gamma <= 0:
        raise ValueError("gamma debe ser positiva (aversión al riesgo)")
    mu = np.asarray(mu, dtype=float)
    Sigma = np.asarray(Sigma, dtype=float)
    n = len(mu)
    bounds = bounds or [(0.0, 1.0)] * n
    _validate_inputs(mu, Sigma, bounds)

    def neg_utility(w):
        mu_p, sigma_p = _portfolio_stats(w, mu, Sigma)
        return -(mu_p - (gamma / 2) * sigma_p**2)

    w0 = np.full(n, 1.0 / n)
    res = minimize(
        neg_utility,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=[_budget_constraint()],
        options=_SOLVER_OPTIONS,
    )
    if not res.success:
        raise PortfolioOptimizationError(res.message)
    mu_p, sigma_p = _portfolio_stats(res.x, mu, Sigma)
    return PortfolioResult(res.x, mu_p, sigma_p, res.success, res.message)
