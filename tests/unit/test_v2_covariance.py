"""Pruebas de shrinkage hacia la diagonal (GUIA_V2 P39)."""
import json
from pathlib import Path

import numpy as np
import pytest

from src.covariance import shrink_to_diagonal

V2_DATA = Path(__file__).resolve().parents[2] / "v2" / "data"

SIGMA_2X2 = np.array([[0.01, 0.004], [0.004, 0.04]])


def test_delta_zero_returns_sample_unchanged():
    result = shrink_to_diagonal(SIGMA_2X2, delta=0.0)
    np.testing.assert_allclose(result.Sigma, SIGMA_2X2, atol=1e-12)


def test_delta_one_zeroes_off_diagonal_keeps_variances():
    result = shrink_to_diagonal(SIGMA_2X2, delta=1.0)
    np.testing.assert_allclose(result.Sigma, [[0.01, 0.0], [0.0, 0.04]], atol=1e-12)


def test_delta_half_matches_manual_calculation():
    # Off-diagonal: (1-0.5)*0.004 + 0.5*0 = 0.002. Diagonal sin cambio.
    result = shrink_to_diagonal(SIGMA_2X2, delta=0.5)
    np.testing.assert_allclose(result.Sigma, [[0.01, 0.002], [0.002, 0.04]], atol=1e-12)


def test_diagonal_is_always_preserved_regardless_of_delta():
    for delta in (0.0, 0.2, 0.5, 0.8, 1.0):
        result = shrink_to_diagonal(SIGMA_2X2, delta)
        np.testing.assert_allclose(np.diag(result.Sigma), np.diag(SIGMA_2X2), atol=1e-12)


def test_off_diagonal_scales_linearly_with_one_minus_delta():
    for delta in (0.0, 0.3, 0.7, 1.0):
        result = shrink_to_diagonal(SIGMA_2X2, delta)
        assert result.Sigma[0, 1] == pytest.approx((1 - delta) * SIGMA_2X2[0, 1])
        assert result.Sigma[1, 0] == pytest.approx((1 - delta) * SIGMA_2X2[1, 0])


def test_result_is_symmetric_and_psd_for_synthetic_20_asset_universe():
    import pandas as pd

    prices = pd.read_csv(
        V2_DATA / "precios_sinteticos_20.csv", parse_dates=["fecha"]
    ).set_index("fecha").sort_index()
    returns = prices.pct_change(fill_method=None).dropna(how="any")
    Sigma_sample = returns.cov(ddof=1).to_numpy()

    for delta in (0.0, 0.25, 0.5, 0.75, 1.0):
        result = shrink_to_diagonal(Sigma_sample, delta)
        np.testing.assert_allclose(result.Sigma, result.Sigma.T, atol=1e-12)
        eigenvalues = np.linalg.eigvalsh(result.Sigma)
        assert eigenvalues.min() >= -1e-10


def test_rejects_delta_outside_unit_interval():
    with pytest.raises(ValueError, match="delta"):
        shrink_to_diagonal(SIGMA_2X2, delta=1.5)
    with pytest.raises(ValueError, match="delta"):
        shrink_to_diagonal(SIGMA_2X2, delta=-0.1)


def test_rejects_asymmetric_sigma():
    with pytest.raises(ValueError, match="simétrica"):
        shrink_to_diagonal([[0.01, 0.004], [0.005, 0.04]], delta=0.5)


def test_rejects_non_square_sigma():
    with pytest.raises(ValueError, match="NxN"):
        shrink_to_diagonal(np.zeros((2, 3)), delta=0.5)
