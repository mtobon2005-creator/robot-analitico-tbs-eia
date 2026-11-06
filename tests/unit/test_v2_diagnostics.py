"""Pruebas de diagnósticos de normalidad/autocorrelación/homocedasticidad
(Guía de Sustentación Final, "Historia y supuestos").

Casos de control construidos con semilla fija y verificados por
separado con un script (ver conversación del mandato v2): ruido
blanco i.i.d. no debe rechazar ninguno de los tres; un AR(1) fuerte
debe rechazar Ljung-Box; una t-student de colas pesadas debe rechazar
Jarque-Bera; un proceso ARCH(1) real debe rechazar ARCH-LM.
"""
import numpy as np
import pytest

from src.diagnostics import (
    AutocorrelationTest,
    DiagnosticsError,
    HomoscedasticityTest,
    NormalityTest,
    arch_lm_test,
    jarque_bera_test,
    ljung_box_test,
)


def _white_noise(n=500, seed=42):
    rng = np.random.default_rng(seed)
    return rng.normal(0, 0.01, n)


def _strong_ar1(n=500, phi=0.8, seed=42):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + rng.normal(0, 0.01)
    return x


def _heavy_tailed(n=500, df=3, seed=42):
    rng = np.random.default_rng(seed)
    return rng.standard_t(df, size=n) * 0.01


def _arch1_process(n=500, omega=1e-5, alpha=0.85, seed=1):
    rng = np.random.default_rng(seed)
    eps = np.zeros(n)
    sigma2 = omega / (1 - alpha)
    for t in range(n):
        sigma2 = omega + alpha * (eps[t - 1] ** 2 if t > 0 else sigma2)
        eps[t] = rng.normal(0, np.sqrt(sigma2))
    return eps


# --- jarque_bera_test --------------------------------------------------------

def test_jarque_bera_does_not_reject_white_noise():
    result = jarque_bera_test(_white_noise())
    assert isinstance(result, NormalityTest)
    assert result.rejects_normality is False
    assert result.p_value > 0.05


def test_jarque_bera_rejects_heavy_tailed_distribution():
    result = jarque_bera_test(_heavy_tailed())
    assert result.rejects_normality is True
    assert result.p_value < 0.05


def test_jarque_bera_rejects_insufficient_observations():
    with pytest.raises(DiagnosticsError, match="al menos"):
        jarque_bera_test([0.01, -0.02, 0.03])


# --- ljung_box_test ----------------------------------------------------------

def test_ljung_box_does_not_reject_white_noise():
    result = ljung_box_test(_white_noise(), lags=10)
    assert isinstance(result, AutocorrelationTest)
    assert result.rejects_independence is False
    assert result.p_value > 0.05


def test_ljung_box_rejects_strong_autocorrelation():
    result = ljung_box_test(_strong_ar1(), lags=10)
    assert result.rejects_independence is True
    assert result.p_value < 0.05


def test_ljung_box_rejects_insufficient_observations():
    with pytest.raises(DiagnosticsError, match="observaciones"):
        ljung_box_test(np.zeros(5), lags=10)


# --- arch_lm_test --------------------------------------------------------

def test_arch_lm_does_not_reject_white_noise():
    result = arch_lm_test(_white_noise(), lags=5)
    assert isinstance(result, HomoscedasticityTest)
    assert result.rejects_homoscedasticity is False
    assert result.p_value > 0.05


def test_arch_lm_rejects_real_arch_process():
    result = arch_lm_test(_arch1_process(), lags=5)
    assert result.rejects_homoscedasticity is True
    assert result.p_value < 0.05


def test_arch_lm_rejects_insufficient_observations():
    with pytest.raises(DiagnosticsError, match="observaciones"):
        arch_lm_test(np.zeros(3), lags=5)
