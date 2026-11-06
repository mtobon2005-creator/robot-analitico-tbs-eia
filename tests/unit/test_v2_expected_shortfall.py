"""Pruebas de Expected Shortfall (pérdida esperada más allá del VaR —
Guía de Sustentación Final, "Riesgo y probabilidades")."""
import pytest

from src.forecasting import TrainParams, horizon_params
from src.risk import ExpectedShortfallResult, compute_expected_shortfall, compute_var


def test_expected_shortfall_matches_official_var99_a01_case():
    # Mismo caso oficial VAR99-A-01 de test_rf16_18_risk.py.
    params = TrainParams(mu_train=0.0, sigma_train=0.015811388300842)
    dist = horizon_params("A", params, h=4)
    result = compute_expected_shortfall(dist, confidence=0.99, capital=10000.0)
    assert isinstance(result, ExpectedShortfallResult)
    assert result.fraction == pytest.approx(0.08078322301765017, abs=1e-9)
    assert result.monetary == pytest.approx(807.8322301765018, abs=1e-4)


def test_expected_shortfall_matches_official_var99_b01_case():
    params = TrainParams(mu_train=0.01, sigma_train=0.02)
    dist = horizon_params("B", params, h=3)
    result = compute_expected_shortfall(dist, confidence=0.99, capital=10000.0)
    assert result.fraction == pytest.approx(0.06036892098292901, abs=1e-9)


def test_expected_shortfall_is_always_at_least_var():
    # ES promedia la cola MÁS ALLÁ del VaR — nunca puede ser menor.
    params = TrainParams(mu_train=0.0, sigma_train=0.015811388300842)
    dist = horizon_params("A", params, h=4)
    var_result = compute_var(dist, confidence=0.99, capital=10000.0)
    es_result = compute_expected_shortfall(dist, confidence=0.99, capital=10000.0)
    assert es_result.fraction >= var_result.fraction


def test_expected_shortfall_simple_round_case_matches_manual_derivation():
    # m_h=0, sd_h=0.1, c=0.95 — derivado a mano (ver docstring de
    # compute_expected_shortfall) y cruzado con scipy.stats.norm.
    params = TrainParams(mu_train=0.0, sigma_train=0.1)
    dist = horizon_params("A", params, h=1)
    result = compute_expected_shortfall(dist, confidence=0.95, capital=1.0)
    assert result.fraction == pytest.approx(0.18583582705677637, abs=1e-9)


def test_expected_shortfall_zero_when_volatility_zero():
    params = TrainParams(mu_train=0.0, sigma_train=0.0)
    dist = horizon_params("A", params, h=4)
    result = compute_expected_shortfall(dist, confidence=0.95, capital=10000.0)
    assert result.fraction == pytest.approx(0.0, abs=1e-8)


def test_expected_shortfall_floors_at_zero_with_strong_positive_drift():
    params = TrainParams(mu_train=0.05, sigma_train=0.001)
    dist = horizon_params("B", params, h=10)
    result = compute_expected_shortfall(dist, confidence=0.95, capital=10000.0)
    assert result.fraction >= 0.0


def test_expected_shortfall_rejects_invalid_confidence():
    params = TrainParams(0.0, 0.02)
    dist = horizon_params("A", params, h=1)
    with pytest.raises(ValueError):
        compute_expected_shortfall(dist, confidence=1.5, capital=1000.0)
