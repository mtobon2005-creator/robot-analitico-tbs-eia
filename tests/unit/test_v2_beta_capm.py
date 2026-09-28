"""Pruebas de beta/CAPM/Hamada (GUIA_V2 §8), control: caso Alimentos del
Norte (v2/data/caso_alimentos_retornos.csv + caso_alimentos_parametros.json).

P2-31: beta manual/OLS y benchmark constante controlados.
P2-32: Hamada ida/vuelta con igual supuesto de deuda.
P2-33: CAPM, país, inflación y moneda sin doble conteo.
"""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from src.beta_capm import (
    BetaCapmError,
    beta_covariance,
    beta_ols,
    capm_ke,
    convert_ke_by_inflation,
    relever_beta,
    unlever_beta,
)

V2_DATA = Path(__file__).resolve().parents[2] / "v2" / "data"


@pytest.fixture
def caso_returns():
    with open(V2_DATA / "caso_alimentos_retornos.csv") as f:
        rows = list(csv.DictReader(f))
    comparable = [float(r["comparable"]) for r in rows]
    referencia = [float(r["referencia"]) for r in rows]
    return comparable, referencia


@pytest.fixture
def caso_parametros():
    return json.loads((V2_DATA / "caso_alimentos_parametros.json").read_text())


def test_beta_covariance_matches_manual_control(caso_returns):
    comparable, referencia = caso_returns
    beta = beta_covariance(comparable, referencia)
    assert beta == pytest.approx(1.5142857142857142, abs=1e-10)


def test_beta_ols_matches_covariance_beta_exactly(caso_returns):
    """P98: para una regresión de una sola variable, cov/var y OLS con
    intercepto deben dar EXACTAMENTE el mismo beta — es una identidad
    matemática, no una coincidencia."""
    comparable, referencia = caso_returns
    beta_cov = beta_covariance(comparable, referencia)
    result = beta_ols(comparable, referencia)
    assert result.beta == pytest.approx(beta_cov, abs=1e-10)


def test_beta_ols_reports_alpha_r_squared_and_stderr(caso_returns):
    comparable, referencia = caso_returns
    result = beta_ols(comparable, referencia)
    assert result.alpha == pytest.approx(-0.021142857142857116, abs=1e-9)
    assert result.r_squared == pytest.approx(0.7643537414965985, abs=1e-9)
    assert result.std_err == pytest.approx(0.4203982562732047, abs=1e-9)
    assert result.n == 6


def test_beta_covariance_rejects_constant_benchmark():
    with pytest.raises(BetaCapmError, match="indefinida"):
        beta_covariance([0.1, 0.2, 0.3], [0.05, 0.05, 0.05])


def test_beta_ols_rejects_constant_benchmark():
    with pytest.raises(BetaCapmError, match="indefinida"):
        beta_ols([0.1, 0.2, 0.3], [0.05, 0.05, 0.05])


def test_beta_covariance_rejects_mismatched_lengths():
    with pytest.raises(BetaCapmError, match="misma longitud"):
        beta_covariance([0.1, 0.2], [0.1, 0.2, 0.3])


def test_hamada_unlever_relever_round_trip_with_same_de(caso_returns, caso_parametros):
    comparable, referencia = caso_returns
    beta_L = beta_covariance(comparable, referencia)
    tax = caso_parametros["tax_supuesto"]
    de = caso_parametros["de_comparable"]

    beta_U = unlever_beta(beta_L, tax, de)
    beta_L_roundtrip = relever_beta(beta_U, tax, de)

    assert beta_L_roundtrip == pytest.approx(beta_L, abs=1e-12)


def test_hamada_relever_to_target_structure_matches_manual_control(caso_returns, caso_parametros):
    comparable, referencia = caso_returns
    beta_L_comparable = beta_covariance(comparable, referencia)
    tax = caso_parametros["tax_supuesto"]

    beta_U = unlever_beta(beta_L_comparable, tax, caso_parametros["de_comparable"])
    beta_L_alimentos = relever_beta(beta_U, tax, caso_parametros["de_empresa"])

    assert beta_U == pytest.approx(1.0894141829393627, abs=1e-9)
    assert beta_L_alimentos == pytest.approx(1.620503597122302, abs=1e-9)


def test_hamada_rejects_negative_leverage():
    with pytest.raises(BetaCapmError, match="D/E"):
        unlever_beta(1.5, tax=0.35, d_e=-0.1)
    with pytest.raises(BetaCapmError, match="D/E"):
        relever_beta(1.0, tax=0.35, d_e=-0.1)


def test_hamada_rejects_tax_out_of_range():
    with pytest.raises(BetaCapmError, match="tax"):
        unlever_beta(1.5, tax=1.0, d_e=0.6)
    with pytest.raises(BetaCapmError, match="tax"):
        unlever_beta(1.5, tax=-0.1, d_e=0.6)


def test_hamada_with_nonzero_beta_debt_reduces_to_classic_when_zero():
    beta_L, tax, de = 1.5, 0.3, 0.5
    classic = unlever_beta(beta_L, tax, de)
    extended = unlever_beta(beta_L, tax, de, beta_D=0.0)
    assert classic == pytest.approx(extended, abs=1e-12)


def test_capm_ke_matches_manual_control(caso_parametros):
    beta_L_alimentos = 1.620503597122302
    ke_usd = capm_ke(
        rf=caso_parametros["rf_USD"],
        beta_L=beta_L_alimentos,
        erp=caso_parametros["erp_madura"],
        country_risk_premium=caso_parametros["proxy_pais"],
        lambda_=caso_parametros["lambda"],
    )
    assert ke_usd == pytest.approx(0.16412769784172662, abs=1e-9)


def test_capm_ke_without_country_extension_is_plain_capm():
    ke = capm_ke(rf=0.04, beta_L=1.2, erp=0.06)
    assert ke == pytest.approx(0.04 + 1.2 * 0.06, abs=1e-12)


def test_convert_ke_by_inflation_matches_manual_control(caso_parametros):
    ke_cop = convert_ke_by_inflation(
        ke_foreign=0.16412769784172662,
        inflation_domestic=caso_parametros["inflacion_COL"],
        inflation_foreign=caso_parametros["inflacion_USA"],
    )
    assert ke_cop == pytest.approx(0.18684238462888225, abs=1e-9)


def test_convert_ke_by_inflation_no_change_when_inflations_equal():
    ke = convert_ke_by_inflation(0.10, inflation_domestic=0.03, inflation_foreign=0.03)
    assert ke == pytest.approx(0.10, abs=1e-12)


def test_convert_ke_by_inflation_rejects_impossible_foreign_inflation():
    with pytest.raises(BetaCapmError, match="inflation_foreign"):
        convert_ke_by_inflation(0.10, inflation_domestic=0.03, inflation_foreign=-1.0)
