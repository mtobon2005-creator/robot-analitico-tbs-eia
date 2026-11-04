"""Pruebas de CML, Treynor, Jensen, Information Ratio y descomposición
de riesgo sistemático (sustentación final — núcleo financiero de
referencia)."""
import numpy as np
import pytest

from src.performance import (
    InformationRatioResult,
    PerformanceError,
    capital_market_line,
    information_ratio,
    jensens_alpha,
    systematic_risk_share,
    treynor_ratio,
)


# --- capital_market_line ----------------------------------------------------

def test_cml_matches_manual_control():
    # pendiente = (0.10-0.03)/0.15 = 0.466666...7
    result = capital_market_line(rf=0.03, tangency_return=0.10, tangency_volatility=0.15, sigma_values=[0.0, 0.15, 0.30])
    np.testing.assert_allclose(result, [0.03, 0.10, 0.17], atol=1e-10)


def test_cml_at_tangency_point_equals_tangency_return():
    result = capital_market_line(rf=0.02, tangency_return=0.12, tangency_volatility=0.18, sigma_values=[0.18])
    np.testing.assert_allclose(result, [0.12], atol=1e-10)


def test_cml_rejects_non_positive_tangency_volatility():
    with pytest.raises(PerformanceError, match="tangency_volatility"):
        capital_market_line(0.03, 0.10, 0.0, [0.1])


# --- treynor_ratio -----------------------------------------------------------

def test_treynor_matches_manual_calculation():
    assert treynor_ratio(portfolio_return=0.12, rf=0.03, beta_p=0.8) == pytest.approx(0.1125, abs=1e-12)


def test_treynor_rejects_zero_beta():
    with pytest.raises(PerformanceError, match="beta_p"):
        treynor_ratio(0.1, 0.03, 0.0)


# --- jensens_alpha -------------------------------------------------------

def test_jensens_alpha_matches_manual_calculation():
    # requerido = 0.03+0.8*(0.09-0.03) = 0.078; alpha = 0.12-0.078 = 0.042
    result = jensens_alpha(portfolio_return=0.12, rf=0.03, beta_p=0.8, market_return=0.09)
    assert result == pytest.approx(0.042, abs=1e-12)


def test_jensens_alpha_zero_when_return_matches_capm_exactly():
    result = jensens_alpha(portfolio_return=0.078, rf=0.03, beta_p=0.8, market_return=0.09)
    assert result == pytest.approx(0.0, abs=1e-12)


# --- information_ratio ------------------------------------------------------

def test_information_ratio_matches_manual_control():
    active = [0.01, -0.005, 0.02, 0.0]
    result = information_ratio(active, periods_per_year=252)
    assert isinstance(result, InformationRatioResult)
    # Verificado por separado con numpy: mean_period=0.00625,
    # std_period(ddof=1)=0.011086778913041726.
    assert result.mean_active_annual == pytest.approx(1.575, abs=1e-9)
    assert result.tracking_error_annual == pytest.approx(0.1759971590679804, abs=1e-9)
    assert result.information_ratio == pytest.approx(8.949008088202396, abs=1e-6)
    assert result.n_obs == 4


def test_information_ratio_rejects_insufficient_observations():
    with pytest.raises(PerformanceError, match="al menos"):
        information_ratio([0.01], periods_per_year=252)


def test_information_ratio_rejects_zero_tracking_error():
    with pytest.raises(PerformanceError, match="tracking error"):
        information_ratio([0.01, 0.01, 0.01], periods_per_year=252)


def test_information_ratio_rejects_non_positive_periods():
    with pytest.raises(PerformanceError, match="periods_per_year"):
        information_ratio([0.01, -0.01], periods_per_year=0)


# --- systematic_risk_share --------------------------------------------------

def test_systematic_risk_share_splits_correctly():
    result = systematic_risk_share(0.64)
    assert result == {"sistematico": 0.64, "no_sistematico": pytest.approx(0.36)}


def test_systematic_risk_share_edges():
    assert systematic_risk_share(0.0) == {"sistematico": 0.0, "no_sistematico": 1.0}
    assert systematic_risk_share(1.0) == {"sistematico": 1.0, "no_sistematico": 0.0}


def test_systematic_risk_share_rejects_out_of_range():
    with pytest.raises(PerformanceError, match="r_squared"):
        systematic_risk_share(1.5)
    with pytest.raises(PerformanceError, match="r_squared"):
        systematic_risk_share(-0.1)
