"""Pruebas RF-16 a RF-18: VaR, niveles, probabilidades."""
import pytest

from src.forecasting import TrainParams, horizon_params
from src.risk import (
    InvalidCostRate,
    InvalidTailProbabilities,
    compute_var,
    equilibrium_price,
    evaluate_signal,
    validate_cost_rate,
    validate_tail_probabilities,
)

ATOL = 1e-8


# --- RF-16: VaR (VAR99-A-01, VAR99-B-01) ------------------------------------

def test_var99_model_a_matches_official_case():
    params = TrainParams(mu_train=0.0, sigma_train=0.015811388300842)
    dist = horizon_params("A", params, h=4)
    result = compute_var(dist, confidence=0.99, capital=10000.0)

    assert result.fraction == pytest.approx(0.070924784140090, abs=ATOL)
    assert result.monetary == pytest.approx(709.247841400895, abs=1e-4)


def test_var99_model_b_matches_official_case():
    params = TrainParams(mu_train=0.01, sigma_train=0.02)
    dist = horizon_params("B", params, h=3)
    result = compute_var(dist, confidence=0.99, capital=10000.0)

    assert result.fraction == pytest.approx(0.049328834922328, abs=ATOL)
    assert result.monetary == pytest.approx(493.288349223279, abs=1e-4)


def test_var95_model_a_matches_earlier_official_case():
    # Mismo caso que MODEL-A-01 (RF-13/14), pero ahora como VaR al 95%.
    params = TrainParams(mu_train=0.0, sigma_train=0.015811388300842)
    dist = horizon_params("A", params, h=4)
    result = compute_var(dist, confidence=0.95, capital=10000.0)

    assert result.fraction == pytest.approx(0.050685219941970, abs=1e-6)
    assert result.monetary == pytest.approx(506.852199419704, abs=1e-3)


def test_var_is_never_negative_even_with_positive_drift():
    # Deriva positiva fuerte -> q_{1-c} podría ser positivo -> VaR se
    # trunca en 0 (piso max(0, ...) de la fórmula).
    params = TrainParams(mu_train=0.05, sigma_train=0.001)
    dist = horizon_params("B", params, h=10)
    result = compute_var(dist, confidence=0.95, capital=10000.0)
    assert result.fraction >= 0.0


def test_var_zero_when_volatility_zero():
    # 'Serie constante' (guía, 8.1): μ=σ=VaR=0.
    params = TrainParams(mu_train=0.0, sigma_train=0.0)
    dist = horizon_params("A", params, h=4)
    result = compute_var(dist, confidence=0.95, capital=10000.0)
    assert result.fraction == pytest.approx(0.0, abs=ATOL)


def test_compute_var_rejects_invalid_confidence():
    params = TrainParams(0.0, 0.02)
    dist = horizon_params("A", params, h=1)
    with pytest.raises(ValueError):
        compute_var(dist, confidence=1.5, capital=1000.0)


# --- RF-17: validaciones de entrada ------------------------------------------

def test_validate_tail_probabilities_accepts_defaults():
    validate_tail_probabilities(0.05, 0.95)  # no debe lanzar


@pytest.mark.parametrize(
    "p_l,p_u", [(0.5, 0.95), (0.05, 0.5), (0.6, 0.4), (-0.1, 0.95), (0.05, 1.1)]
)
def test_validate_tail_probabilities_rejects_invalid_order(p_l, p_u):
    with pytest.raises(InvalidTailProbabilities):
        validate_tail_probabilities(p_l, p_u)


def test_validate_cost_rate_accepts_zero_costs():
    validate_cost_rate(0.0, 0.0)  # no debe lanzar


def test_validate_cost_rate_rejects_negative_buy_cost():
    with pytest.raises(InvalidCostRate):
        validate_cost_rate(-0.001, 0.0)


def test_validate_cost_rate_rejects_sell_cost_of_one_or_more():
    with pytest.raises(InvalidCostRate):
        validate_cost_rate(0.0, 1.0)


def test_equilibrium_price_with_zero_costs_equals_entry():
    assert equilibrium_price(100.0, 0.0, 0.0) == pytest.approx(100.0)


def test_equilibrium_price_matches_official_cost_b01():
    p_be = equilibrium_price(100.0, c_b=0.001, c_s=0.001)
    assert p_be == pytest.approx(100.200200200200, abs=1e-9)


# --- RF-17/RF-18: evaluate_signal (COST-B-01, señal/no-señal) ---------------

def test_evaluate_signal_matches_official_cost_b01():
    params = TrainParams(mu_train=0.01, sigma_train=0.02)
    dist = horizon_params("B", params, h=3)

    result = evaluate_signal(
        p_t=100.0, dist=dist, p_l=0.05, p_u=0.95, br_min=1.0, c_b=0.001, c_s=0.001
    )

    assert result.p_be == pytest.approx(100.200200200200, abs=1e-9)
    assert result.u_neto == pytest.approx(8.878333442352, abs=1e-6)
    assert result.d_neto == pytest.approx(2.859208934922, abs=1e-6)
    assert result.br_neto == pytest.approx(3.105171270946, abs=1e-6)
    assert result.prob_win == pytest.approx(0.790538273989, abs=1e-6)
    assert result.prob_loss == pytest.approx(0.209461726011, abs=1e-6)
    assert result.has_signal is True
    assert result.failed_conditions == []


def test_evaluate_signal_probabilities_sum_to_one_in_continuous_branch():
    params = TrainParams(mu_train=0.01, sigma_train=0.02)
    dist = horizon_params("B", params, h=3)
    result = evaluate_signal(100.0, dist)
    assert result.prob_win + result.prob_loss + result.prob_neutral == pytest.approx(1.0)
    assert result.prob_neutral == pytest.approx(0.0)  # rama continua: sin empate posible


def test_evaluate_signal_deterministic_branch_constant_series_gives_no_signal():
    # 'Serie constante' (guía 8.1): SL_H=E=TP_H -> no señal porque
    # E > SL_H falla (no es estrictamente mayor).
    params = TrainParams(mu_train=0.0, sigma_train=0.0)
    dist = horizon_params("A", params, h=4)  # m_h=0, v_h=0
    result = evaluate_signal(100.0, dist)

    assert result.sl_h == pytest.approx(100.0)
    assert result.tp_h == pytest.approx(100.0)
    assert result.has_signal is False
    assert "SL_H < E < TP_H" in result.failed_conditions
    # Rama determinista con P*=P_t=P_BE (costos cero) -> neutral.
    assert result.prob_neutral == pytest.approx(1.0)


def test_evaluate_signal_no_signal_when_br_below_minimum():
    # BR_min muy alto fuerza 'no señal' aunque el resto sea válido.
    params = TrainParams(mu_train=0.01, sigma_train=0.02)
    dist = horizon_params("B", params, h=3)
    result = evaluate_signal(100.0, dist, br_min=100.0)

    assert result.has_signal is False
    assert any("BR_neto" in reason for reason in result.failed_conditions)


def test_evaluate_signal_never_raises_for_no_signal_case():
    # Una "no señal" es un resultado válido, nunca una excepción.
    params = TrainParams(mu_train=0.0, sigma_train=0.0)
    dist = horizon_params("A", params, h=1)
    result = evaluate_signal(100.0, dist)  # no debe lanzar
    assert result.has_signal is False


def test_evaluate_signal_rejects_invalid_tail_probabilities():
    params = TrainParams(0.01, 0.02)
    dist = horizon_params("B", params, h=3)
    with pytest.raises(InvalidTailProbabilities):
        evaluate_signal(100.0, dist, p_l=0.5, p_u=0.4)


def test_evaluate_signal_br_bruto_none_when_entry_not_above_sl():
    params = TrainParams(mu_train=0.0, sigma_train=0.0)
    dist = horizon_params("A", params, h=1)
    result = evaluate_signal(100.0, dist)
    assert result.br_bruto is None  # E == SL_H, no calculable
