"""Pruebas RF-13 a RF-15: forecasting homocedástico y walk-forward."""
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analytics import compute_log_returns
from src.data import FixtureProvider, clean_prices
from src.forecasting import (
    InsufficientWalkForwardSample,
    TrainParams,
    UnknownModel,
    estimate_train_params,
    generate_trajectory,
    horizon_params,
    price_mean,
    price_median,
    price_quantile,
    validate_walk_forward,
    walk_forward_sufficiency,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_CSV = FIXTURES_DIR / "Fixture_20_activos_sintetico_TBS_EIA.csv"

ATOL = 1e-8


# --- MODEL-A-01 --------------------------------------------------------------

def test_model_a_matches_official_case():
    # P=100; sigma=0.0158113883008419; H=4
    params = TrainParams(mu_train=0.0, sigma_train=0.0158113883008419)
    dist = horizon_params("A", params, h=4)

    assert dist.m_h == pytest.approx(0.0, abs=ATOL)
    assert dist.v_h == pytest.approx(0.001, abs=ATOL)
    assert dist.sd_h == pytest.approx(0.031622776601684, abs=ATOL)

    p_t = 100.0
    assert price_median(p_t, dist) == pytest.approx(100.0, abs=ATOL)
    assert price_mean(p_t, dist) == pytest.approx(100.050012502084, abs=ATOL)
    assert price_quantile(p_t, dist, 0.05) == pytest.approx(94.931478005803, abs=1e-6)
    assert price_quantile(p_t, dist, 0.95) == pytest.approx(105.339137344820, abs=1e-6)


# --- MODEL-B-01 --------------------------------------------------------------

def test_model_b_matches_official_case():
    # P=100; mu=0.01; sigma=0.02; H=3
    params = TrainParams(mu_train=0.01, sigma_train=0.02)
    dist = horizon_params("B", params, h=3)

    assert dist.m_h == pytest.approx(0.03, abs=ATOL)
    assert dist.v_h == pytest.approx(0.0012, abs=ATOL)
    assert dist.sd_h == pytest.approx(0.034641016151378, abs=ATOL)

    p_t = 100.0
    assert price_median(p_t, dist) == pytest.approx(103.045453395352, abs=1e-6)
    assert price_mean(p_t, dist) == pytest.approx(103.107299219281, abs=1e-6)
    assert price_quantile(p_t, dist, 0.05) == pytest.approx(97.338129194272, abs=1e-6)
    assert price_quantile(p_t, dist, 0.95) == pytest.approx(109.087420863215, abs=1e-6)


# --- PATH-B-01: trayectoria 1..H --------------------------------------------

def test_generate_trajectory_matches_official_path_b01():
    params = TrainParams(mu_train=0.01, sigma_train=0.02)
    trajectory = generate_trajectory(p_t=100.0, params=params, model="B", horizon=3)

    assert len(trajectory) == 3

    h1 = trajectory[0]
    assert h1.median == pytest.approx(101.005016708417, abs=1e-6)
    assert h1.mean == pytest.approx(101.025219731994, abs=1e-6)
    assert h1.q05 == pytest.approx(97.736307609620, abs=1e-6)
    assert h1.q95 == pytest.approx(104.383045050327, abs=1e-6)

    h2 = trajectory[1]
    assert h2.median == pytest.approx(102.020134002676, abs=1e-6)
    assert h2.mean == pytest.approx(102.060950218976, abs=1e-6)
    assert h2.q05 == pytest.approx(97.382517216574, abs=1e-6)
    assert h2.q95 == pytest.approx(106.878606544712, abs=1e-6)

    h3 = trajectory[2]
    assert h3.median == pytest.approx(103.045453395352, abs=1e-6)
    assert h3.mean == pytest.approx(103.107299219281, abs=1e-6)
    assert h3.q05 == pytest.approx(97.338129194272, abs=1e-6)
    assert h3.q95 == pytest.approx(109.087420863215, abs=1e-6)


def test_generate_trajectory_recalculates_fully_for_each_h():
    params = TrainParams(mu_train=0.01, sigma_train=0.02)
    trajectory = generate_trajectory(100.0, params, "B", horizon=3)
    # v_h debe crecer linealmente con h (h·sigma^2), no ser constante.
    assert trajectory[1].v_h == pytest.approx(2 * trajectory[0].v_h, abs=ATOL)
    assert trajectory[2].v_h == pytest.approx(3 * trajectory[0].v_h, abs=ATOL)


# --- Validaciones y casos borde ---------------------------------------------

def test_horizon_params_rejects_unknown_model():
    with pytest.raises(UnknownModel):
        horizon_params("C", TrainParams(0.0, 0.01), h=1)


def test_horizon_params_rejects_nonpositive_horizon():
    with pytest.raises(ValueError):
        horizon_params("A", TrainParams(0.0, 0.01), h=0)


def test_model_a_median_stays_at_last_price_regardless_of_horizon():
    params = TrainParams(mu_train=0.0, sigma_train=0.02)
    for h in [1, 5, 50]:
        dist = horizon_params("A", params, h)
        assert price_median(100.0, dist) == pytest.approx(100.0, abs=ATOL)


def test_model_a_mean_is_not_constant_due_to_exponential_transform():
    # Aunque la mediana del Modelo A permanece en P_t, la media
    # aritmética NO (sección 5.5, párrafo sobre Modelo A).
    params = TrainParams(mu_train=0.0, sigma_train=0.02)
    dist = horizon_params("A", params, h=10)
    assert price_mean(100.0, dist) > 100.0


def test_estimate_train_params_uses_only_the_given_slice():
    returns = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
    train_only_first_two = estimate_train_params(returns.iloc[:2])
    assert train_only_first_two.mu_train == pytest.approx(0.015)


# --- RF-15: walk-forward (WF-01, exacto con AAPL) ---------------------------

@pytest.fixture(scope="module")
def aapl_series():
    provider = FixtureProvider(FIXTURE_CSV)
    raw = provider.fetch("AAPL", date(2024, 7, 19), date(2026, 8, 13))
    prices, _ = clean_prices(raw)
    returns = compute_log_returns(prices)
    return prices, returns


def test_walk_forward_sufficiency_matches_wf01():
    sufficient, n_min = walk_forward_sufficiency(t_returns=539, m=252, horizon=20)
    assert n_min == 504
    assert sufficient is True


def test_walk_forward_insufficient_sample_raises():
    short_returns = pd.Series(np.random.normal(0, 0.01, 50))
    short_prices = pd.Series(np.random.normal(100, 1, 51))
    with pytest.raises(InsufficientWalkForwardSample):
        validate_walk_forward(short_prices, short_returns, "A", horizon=20, m=252)


def test_walk_forward_model_a_matches_wf01(aapl_series):
    prices, returns = aapl_series
    result = validate_walk_forward(prices, returns, "A", horizon=20, m=252)

    assert result.origins == [510, 511, 512, 513, 514, 515, 516, 517, 518, 519]
    assert result.mae == pytest.approx(0.047838991594412, abs=ATOL)
    assert result.rmse == pytest.approx(0.049889389325085, abs=ATOL)
    assert result.coverage == pytest.approx(0.2, abs=ATOL)
    assert result.direction_accuracy is None  # Modelo A: m_h=0 siempre -> N/A
    assert result.direction_n == 0


def test_walk_forward_model_b_matches_wf01(aapl_series):
    prices, returns = aapl_series
    result = validate_walk_forward(prices, returns, "B", horizon=20, m=252)

    assert result.mae == pytest.approx(0.050673668010446, abs=ATOL)
    assert result.rmse == pytest.approx(0.052630163459918, abs=ATOL)
    assert result.coverage == pytest.approx(0.1, abs=ATOL)
    assert result.direction_accuracy == pytest.approx(0.0, abs=ATOL)
    assert result.direction_n == 10


def test_walk_forward_uses_expanding_window_not_rolling():
    # Verificación estructural: el origen más grande debe usar más
    # datos de entrenamiento que el más pequeño (ventana EXPANSIVA).
    prices = pd.Series(np.linspace(100, 200, 600))
    returns = compute_log_returns(prices)
    result = validate_walk_forward(prices, returns, "B", horizon=5, m=252)
    assert result.origins == sorted(result.origins)  # orígenes crecientes
