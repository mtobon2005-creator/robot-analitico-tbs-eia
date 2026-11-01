"""Pruebas del motor de portafolios v2 (GUIA_V2 §5, Markowitz N activos).

P2-13: GMV/tangente de dos activos coinciden con el control analítico
       (ver la demostración manual con v2/data/dos_activos.json).
P2-14: frontera por optimización correcta.
P2-15: cotas/presupuesto se cumplen; residuales verificados.
P2-16: máximo esperado, tangencia y óptimo personal quedan
       diferenciados entre sí.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.portfolio import (
    PortfolioOptimizationError,
    efficient_frontier,
    global_min_variance,
    max_expected_return,
    personal_optimum,
    portfolio_log_returns,
    portfolio_var,
    tangency_portfolio,
)

V2_DATA = Path(__file__).resolve().parents[2] / "v2" / "data"

# Control analítico derivado a mano (ver conversación del mandato v2):
# GMV w=[0.857142857, 0.142857143], tangente w=[0.634146341, 0.365853659].
ATOL = 1e-6


@pytest.fixture
def dos_activos():
    return json.loads((V2_DATA / "dos_activos.json").read_text())


def _assert_valid_result(result, n_assets):
    assert result.solver_success, result.solver_message
    assert result.weights.shape == (n_assets,)
    np.testing.assert_allclose(result.weights.sum(), 1.0, atol=1e-8)
    assert (result.weights >= -1e-8).all(), "cota inferior (0) violada"
    assert (result.weights <= 1 + 1e-8).all(), "cota superior (1) violada"


def test_gmv_matches_analytic_two_asset_control(dos_activos):
    mu = dos_activos["mu"]
    Sigma = dos_activos["Sigma"]
    bounds = [tuple(b) for b in dos_activos["bounds"]]

    result = global_min_variance(mu, Sigma, bounds=bounds)

    _assert_valid_result(result, 2)
    np.testing.assert_allclose(result.weights, [0.857142857, 0.142857143], atol=1e-6)
    np.testing.assert_allclose(result.expected_return, 0.088571429, atol=1e-6)
    np.testing.assert_allclose(result.volatility, 0.095618289, atol=1e-6)


def test_tangency_matches_analytic_two_asset_control(dos_activos):
    mu = dos_activos["mu"]
    Sigma = dos_activos["Sigma"]
    rf = dos_activos["rf"]
    bounds = [tuple(b) for b in dos_activos["bounds"]]

    result = tangency_portfolio(mu, Sigma, rf, bounds=bounds)

    _assert_valid_result(result, 2)
    np.testing.assert_allclose(result.weights, [0.634146341, 0.365853659], atol=1e-6)
    np.testing.assert_allclose(result.expected_return, 0.101951220, atol=1e-6)
    np.testing.assert_allclose(result.volatility, 0.105978346, atol=1e-6)


def test_personal_optimum_matches_manual_utility_maximization(dos_activos):
    mu = dos_activos["mu"]
    Sigma = dos_activos["Sigma"]
    gamma = dos_activos["gamma"]
    bounds = [tuple(b) for b in dos_activos["bounds"]]

    result = personal_optimum(mu, Sigma, gamma, bounds=bounds)

    _assert_valid_result(result, 2)
    # x* = 0.12 / 0.21 derivado a mano de U(x)=0.04+0.12x-0.105x^2.
    np.testing.assert_allclose(result.weights, [0.571428571, 0.428571429], atol=1e-6)


def test_max_expected_return_concentrates_on_best_asset(dos_activos):
    mu = dos_activos["mu"]
    Sigma = dos_activos["Sigma"]
    bounds = [tuple(b) for b in dos_activos["bounds"]]

    result = max_expected_return(mu, Sigma, bounds=bounds)

    _assert_valid_result(result, 2)
    # B tiene mayor mu (0.14 > 0.08); con cotas [0,1] y sin más
    # restricciones, el máximo retorno concentra 100% en B.
    np.testing.assert_allclose(result.weights, [0.0, 1.0], atol=1e-6)


def test_the_three_portfolios_are_different(dos_activos):
    """P2-16: GMV, tangencia y óptimo personal no deben coincidir salvo
    coincidencia matemática — aquí verificamos que con este control sí
    están claramente diferenciados."""
    mu = dos_activos["mu"]
    Sigma = dos_activos["Sigma"]
    rf = dos_activos["rf"]
    gamma = dos_activos["gamma"]
    bounds = [tuple(b) for b in dos_activos["bounds"]]

    gmv = global_min_variance(mu, Sigma, bounds=bounds)
    tan = tangency_portfolio(mu, Sigma, rf, bounds=bounds)
    opt = personal_optimum(mu, Sigma, gamma, bounds=bounds)

    assert not np.allclose(gmv.weights, tan.weights, atol=1e-3)
    assert not np.allclose(tan.weights, opt.weights, atol=1e-3)
    assert not np.allclose(gmv.weights, opt.weights, atol=1e-3)


def test_efficient_frontier_variance_increases_away_from_gmv(dos_activos):
    """P2-14: la frontera (rama eficiente) debe tener varianza creciente
    a medida que el retorno objetivo se aleja del de la GMV hacia arriba."""
    mu = dos_activos["mu"]
    Sigma = dos_activos["Sigma"]
    bounds = [tuple(b) for b in dos_activos["bounds"]]

    gmv = global_min_variance(mu, Sigma, bounds=bounds)
    targets = np.linspace(gmv.expected_return, max(mu), 5)

    results, infeasible = efficient_frontier(mu, Sigma, targets, bounds=bounds)

    assert infeasible == []
    assert len(results) == 5
    volatilities = [r.volatility for r in results]
    assert volatilities == sorted(volatilities), "la rama eficiente debe ser no decreciente en riesgo"
    # El primer punto de la rama eficiente debe coincidir con la GMV.
    np.testing.assert_allclose(results[0].weights, gmv.weights, atol=1e-4)


def test_efficient_frontier_reports_infeasible_targets_explicitly(dos_activos):
    """Un retorno objetivo fuera de [min(mu), max(mu)] es inviable bajo
    cotas [0,1] y debe reportarse, no descartarse en silencio (P2-15)."""
    mu = dos_activos["mu"]
    Sigma = dos_activos["Sigma"]
    bounds = [tuple(b) for b in dos_activos["bounds"]]

    results, infeasible = efficient_frontier(mu, Sigma, [0.5], bounds=bounds)

    assert results == []
    assert len(infeasible) == 1
    assert infeasible[0][0] == 0.5


def test_global_min_variance_rejects_asymmetric_sigma():
    with pytest.raises(ValueError, match="simétrica"):
        global_min_variance([0.08, 0.14], [[0.01, 0.004], [0.005, 0.04]])


def test_personal_optimum_rejects_non_positive_gamma(dos_activos):
    with pytest.raises(ValueError, match="gamma"):
        personal_optimum(dos_activos["mu"], dos_activos["Sigma"], gamma=0)


# --- Generalización a N=20 activos (universo sintético del mandato v2) ----

@pytest.fixture(scope="module")
def synthetic_universe():
    prices = pd.read_csv(
        V2_DATA / "precios_sinteticos_20.csv", parse_dates=["fecha"]
    ).set_index("fecha").sort_index()
    returns = prices.pct_change(fill_method=None).dropna(how="any")
    mu = returns.mean().to_numpy()
    Sigma = returns.cov(ddof=1).to_numpy()
    return mu, Sigma, list(returns.columns)


def test_gmv_scales_to_twenty_assets(synthetic_universe):
    mu, Sigma, assets = synthetic_universe
    bounds = [(0.0, 1.0)] * len(assets)

    result = global_min_variance(mu, Sigma, bounds=bounds)

    _assert_valid_result(result, len(assets))
    # La GMV depende de Sigma, no de mu (GUIA_V2 tabla 5.1): su varianza
    # no puede ser menor que la de ningún activo individual tomado solo
    # como control de sanidad, pero sí debe ser <= la varianza promedio
    # ponderada por igual (1/N) por el efecto de diversificación.
    equal_weight = np.full(len(assets), 1.0 / len(assets))
    equal_weight_var = equal_weight @ Sigma @ equal_weight
    assert result.volatility**2 <= equal_weight_var + 1e-9


def test_frontier_twenty_assets_monotonic_and_feasible(synthetic_universe):
    mu, Sigma, assets = synthetic_universe
    bounds = [(0.0, 1.0)] * len(assets)

    gmv = global_min_variance(mu, Sigma, bounds=bounds)
    targets = np.linspace(gmv.expected_return, max(mu), 6)

    results, infeasible = efficient_frontier(mu, Sigma, targets, bounds=bounds)

    assert infeasible == []
    assert len(results) == 6
    for r in results:
        _assert_valid_result(r, len(assets))
    volatilities = [r.volatility for r in results]
    assert volatilities == sorted(volatilities)


# --- portfolio_log_returns (benchmark para beta vs. portafolio óptimo) -----

def test_portfolio_log_returns_matches_manual_weighted_aggregation():
    simple_returns = np.array([[0.10, -0.02], [0.05, 0.03]])
    weights = np.array([0.3, 0.7])
    # Agregación en espacio simple: fila0=0.3*0.10+0.7*(-0.02)=0.016;
    # fila1=0.3*0.05+0.7*0.03=0.036. Luego a log: ln(1+r).
    expected = np.log([1.016, 1.036])
    result = portfolio_log_returns(simple_returns, weights)
    np.testing.assert_allclose(result, expected, atol=1e-12)


def test_portfolio_log_returns_equal_weights_is_simple_average_then_log():
    simple_returns = np.array([[0.10, 0.20], [-0.05, 0.05]])
    weights = np.array([0.5, 0.5])
    expected = np.log([1.15, 1.00])
    result = portfolio_log_returns(simple_returns, weights)
    np.testing.assert_allclose(result, expected, atol=1e-12)


def test_portfolio_log_returns_rejects_weight_length_mismatch():
    with pytest.raises(ValueError, match="weights"):
        portfolio_log_returns(np.zeros((3, 2)), [1.0, 0.0, 0.0])


def test_portfolio_log_returns_rejects_total_loss_or_worse():
    with pytest.raises(ValueError, match="log-retorno"):
        portfolio_log_returns(np.array([[-1.5, 0.0]]), [1.0, 0.0])


# --- portfolio_var (VaR paramétrico de cartera para la ficha técnica) ------

_Z_95 = 1.6448536269514722  # Phi^-1(0.95), constante tabulada estándar


def test_portfolio_var_matches_manual_normal_formula():
    result = portfolio_var(expected_return=0.10, volatility=0.20, confidence=0.95, capital=10000.0)
    expected_fraction = -(0.10 - _Z_95 * 0.20)
    assert result["fraction"] == pytest.approx(expected_fraction, abs=1e-9)
    assert result["monetary"] == pytest.approx(expected_fraction * 10000.0, abs=1e-6)


def test_portfolio_var_floors_at_zero_when_return_dominates_risk():
    result = portfolio_var(expected_return=0.50, volatility=0.01, confidence=0.95, capital=10000.0)
    assert result["fraction"] == 0.0
    assert result["monetary"] == 0.0


def test_portfolio_var_zero_volatility_depends_only_on_sign_of_return():
    result = portfolio_var(expected_return=-0.02, volatility=0.0, confidence=0.95, capital=1000.0)
    assert result["fraction"] == pytest.approx(0.02, abs=1e-12)


def test_portfolio_var_rejects_invalid_confidence():
    with pytest.raises(ValueError, match="confidence"):
        portfolio_var(0.1, 0.2, confidence=1.5, capital=1000.0)
    with pytest.raises(ValueError, match="confidence"):
        portfolio_var(0.1, 0.2, confidence=0.0, capital=1000.0)


def test_portfolio_var_rejects_negative_volatility_or_capital():
    with pytest.raises(ValueError, match="volatility"):
        portfolio_var(0.1, -0.2, confidence=0.95, capital=1000.0)
    with pytest.raises(ValueError, match="capital"):
        portfolio_var(0.1, 0.2, confidence=0.95, capital=-1.0)
