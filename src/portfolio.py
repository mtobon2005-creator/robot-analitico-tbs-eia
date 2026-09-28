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
