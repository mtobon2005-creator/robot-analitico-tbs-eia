"""Pruebas de Black-Litterman (GUIA_V2 §6).

P2-19: sin views, el posterior conserva el prior (mu_excess=pi, M=B).
P2-20: Q=P*pi no mueve la media.
P2-21/22: confianza (Omega) coherente; views absoluta/relativa con
          dimensiones correctas.
"""
import json
from pathlib import Path

import numpy as np
import pytest

from src.black_litterman import (
    BlackLittermanError,
    black_litterman,
    implied_equilibrium_returns,
)

V2_DATA = Path(__file__).resolve().parents[2] / "v2" / "data"


@pytest.fixture
def bl_control():
    return json.loads((V2_DATA / "black_litterman_control.json").read_text())


def test_implied_equilibrium_returns_matches_manual_control(bl_control):
    pi = implied_equilibrium_returns(bl_control["Sigma"], bl_control["w_ref"], bl_control["delta"])
    # pi = delta*Sigma*w_ref = 3*[[0.01,0.004],[0.004,0.04]]@[0.6,0.4]
    np.testing.assert_allclose(pi, [0.0228, 0.0552], atol=1e-10)


def test_black_litterman_matches_manual_control(bl_control):
    result = black_litterman(
        bl_control["Sigma"],
        bl_control["w_ref"],
        bl_control["delta"],
        bl_control["tau"],
        bl_control["P"],
        bl_control["Q"],
        bl_control["Omega"],
    )
    # Derivado a mano (ver conversación del mandato v2): A=P*tau*Sigma*P'+Omega,
    # x=solve(A, Q-P*pi), mu_excess=pi+B*P'*x.
    np.testing.assert_allclose(result.mu_excess, [0.0285, 0.045], atol=1e-8)
    np.testing.assert_allclose(
        result.M, [[0.00014038, 0.00011154], [0.00011154, 0.00074615]], atol=1e-6
    )
    np.testing.assert_allclose(
        result.Sigma_predictive,
        [[0.01014038, 0.00411154], [0.00411154, 0.04074615]],
        atol=1e-6,
    )
    # La vista 1 (A al 3% de exceso) empuja hacia arriba desde el prior
    # (2.28%), pero no llega exactamente al 3% porque Omega no es cero
    # (confianza no absoluta).
    assert result.pi_excess[0] < result.mu_excess[0] < 0.03


def test_no_views_conserves_prior(bl_control):
    result = black_litterman(
        bl_control["Sigma"], bl_control["w_ref"], bl_control["delta"], bl_control["tau"]
    )
    np.testing.assert_allclose(result.mu_excess, result.pi_excess, atol=1e-12)
    np.testing.assert_allclose(result.M, bl_control["tau"] * np.asarray(bl_control["Sigma"]), atol=1e-12)


def test_q_equal_p_times_pi_does_not_move_the_mean(bl_control):
    pi = implied_equilibrium_returns(bl_control["Sigma"], bl_control["w_ref"], bl_control["delta"])
    P = np.asarray(bl_control["P"], dtype=float)
    Q_neutral = P @ pi  # la vista "opina" exactamente lo que ya dice el prior

    result = black_litterman(
        bl_control["Sigma"], bl_control["w_ref"], bl_control["delta"], bl_control["tau"],
        P, Q_neutral, bl_control["Omega"],
    )
    np.testing.assert_allclose(result.mu_excess, pi, atol=1e-10)


def test_high_uncertainty_view_approaches_prior(bl_control):
    """Confianza muy baja (Omega grande) debe acercar el posterior al
    prior, no al valor de la vista (P76: cero confianza no es Omega
    cero, pero Omega grande sí debe diluir la vista)."""
    huge_omega = np.eye(2) * 1e6
    result = black_litterman(
        bl_control["Sigma"], bl_control["w_ref"], bl_control["delta"], bl_control["tau"],
        bl_control["P"], bl_control["Q"], huge_omega,
    )
    pi = implied_equilibrium_returns(bl_control["Sigma"], bl_control["w_ref"], bl_control["delta"])
    np.testing.assert_allclose(result.mu_excess, pi, atol=1e-4)


def test_rejects_dimension_mismatch(bl_control):
    with pytest.raises(BlackLittermanError, match="KxN"):
        black_litterman(
            bl_control["Sigma"], bl_control["w_ref"], bl_control["delta"], bl_control["tau"],
            P=[[1, 0, 0]], Q=[0.03], Omega=[[0.0002]],
        )


def test_rejects_asymmetric_sigma():
    with pytest.raises(BlackLittermanError, match="simétrica"):
        implied_equilibrium_returns([[0.01, 0.004], [0.005, 0.04]], [0.6, 0.4], delta=3)


def test_rejects_non_positive_delta(bl_control):
    with pytest.raises(BlackLittermanError, match="delta"):
        implied_equilibrium_returns(bl_control["Sigma"], bl_control["w_ref"], delta=0)


def test_rejects_non_positive_tau(bl_control):
    with pytest.raises(BlackLittermanError, match="tau"):
        black_litterman(bl_control["Sigma"], bl_control["w_ref"], bl_control["delta"], tau=0)
