"""Pruebas de valoración (GUIA_V2 §9, M8), control: Alimentos del Norte.

P2-34: FCFF/FCFE, WACC y terminal inválido comprobados.
"""
import json
from pathlib import Path

import pytest

from src.beta_capm import capm_ke, convert_ke_by_inflation, relever_beta, unlever_beta
from src.valuation import (
    ValuationError,
    fcfe,
    fcff,
    present_value,
    project_years,
    terminal_value_gordon,
    wacc,
)

V2_DATA = Path(__file__).resolve().parents[2] / "v2" / "data"


@pytest.fixture
def parametros():
    return json.loads((V2_DATA / "caso_alimentos_parametros.json").read_text())


def test_wacc_matches_manual_control(parametros):
    beta_L_comparable = 1.5142857142857142  # ver test_v2_beta_capm.py
    beta_U = unlever_beta(beta_L_comparable, parametros["tax_supuesto"], parametros["de_comparable"])
    beta_L_alimentos = relever_beta(beta_U, parametros["tax_supuesto"], parametros["de_empresa"])
    ke_usd = capm_ke(
        parametros["rf_USD"], beta_L_alimentos, parametros["erp_madura"],
        country_risk_premium=parametros["proxy_pais"], lambda_=parametros["lambda"],
    )
    ke_cop = convert_ke_by_inflation(ke_usd, parametros["inflacion_COL"], parametros["inflacion_USA"])

    de = parametros["de_empresa"]
    E, D = 1.0, de  # D/E = de_empresa, cualquier escala sirve para la proporción
    result = wacc(E, D, ke_cop, parametros["kd_EA"], parametros["tax_supuesto"])

    assert result == pytest.approx(0.1443741, abs=1e-6)


def test_wacc_rejects_zero_capital():
    with pytest.raises(ValuationError, match="D\\+E"):
        wacc(0, 0, 0.15, 0.10, 0.35)


def test_fcff_zero_growth_collapses_to_simple_formula(parametros):
    """Con crecimiento 0%, capex=depreciación y ΔNWC=0 exactamente, así
    que FCFF debe colapsar a EBIT*(1-tax) — control trivial pero exacto."""
    projections = project_years(
        sales_growth_rates=[0.0] * 3,
        sales0=parametros["ventas0"],
        capacity0=parametros["capacidad_ventas"],
        variable_cost_rate=parametros["costo_variable"],
        fixed_costs=parametros["gastos_fijos"],
        depreciation0=parametros["depreciacion0"],
        tax=parametros["tax_supuesto"],
        nwc_sales_rate=parametros["nwc_ventas"],
        capex_per_unit_expansion=parametros["capex_venta_adicional"],
        useful_life_years=parametros["vida_depreciacion"],
    )
    for p in projections:
        assert p.sales == pytest.approx(parametros["ventas0"], abs=1e-9)
        assert p.ebit == pytest.approx(parametros["ebit0"], abs=1e-9)
        assert p.delta_nwc == pytest.approx(0.0, abs=1e-9)
        assert p.capex == pytest.approx(p.depreciation, abs=1e-9)
        assert p.fcff == pytest.approx(parametros["ebit0"] * (1 - parametros["tax_supuesto"]), abs=1e-6)


def test_project_years_with_capacity_expansion_matches_manual_control(parametros):
    """Crecimiento que excede la capacidad en los años 1-2 dispara CAPEX
    de expansión; años 3-5 vuelven a capex=depreciación (mantenimiento).
    Valores derivados a mano y verificados numéricamente por separado."""
    projections = project_years(
        sales_growth_rates=[0.05, 0.05, 0.0, 0.0, 0.0],
        sales0=parametros["ventas0"],
        capacity0=parametros["capacidad_ventas"],
        variable_cost_rate=parametros["costo_variable"],
        fixed_costs=parametros["gastos_fijos"],
        depreciation0=parametros["depreciacion0"],
        tax=parametros["tax_supuesto"],
        nwc_sales_rate=parametros["nwc_ventas"],
        capex_per_unit_expansion=parametros["capex_venta_adicional"],
        useful_life_years=parametros["vida_depreciacion"],
    )
    assert len(projections) == 5

    y1, y2, y3, y4, y5 = projections

    assert y1.sales == pytest.approx(157500.0, abs=1e-6)
    assert y1.depreciation == pytest.approx(9000.0, abs=1e-6)
    assert y1.capex == pytest.approx(10500.0, abs=1e-6)
    assert y1.ebit == pytest.approx(21000.0, abs=1e-6)
    assert y1.delta_nwc == pytest.approx(900.0, abs=1e-6)
    assert y1.fcff == pytest.approx(11250.0, abs=1e-6)
    assert y1.capacity_end == pytest.approx(157500.0, abs=1e-6)

    assert y2.sales == pytest.approx(165375.0, abs=1e-6)
    assert y2.depreciation == pytest.approx(9187.5, abs=1e-6)
    assert y2.capex == pytest.approx(13912.5, abs=1e-6)
    assert y2.ebit == pytest.approx(23962.5, abs=1e-6)
    assert y2.fcff == pytest.approx(9905.625, abs=1e-6)

    # Años 3-5: ventas planas exactamente en la capacidad ampliada ->
    # sin expansión nueva, capex vuelve a ser solo mantenimiento.
    for y in (y3, y4, y5):
        assert y.sales == pytest.approx(165375.0, abs=1e-6)
        assert y.delta_nwc == pytest.approx(0.0, abs=1e-9)
        assert y.capex == pytest.approx(y.depreciation, abs=1e-9)
    assert y3.depreciation == pytest.approx(9778.125, abs=1e-6)
    assert y3.fcff == pytest.approx(15191.71875, abs=1e-6)
    # Ya no quedan tranches nuevos por agregar -> depreciación estable.
    assert y4.depreciation == pytest.approx(y3.depreciation, abs=1e-9)
    assert y5.depreciation == pytest.approx(y3.depreciation, abs=1e-9)


def test_project_years_rejects_non_positive_inputs():
    with pytest.raises(ValuationError, match="positivos"):
        project_years([0.0], sales0=0, capacity0=100, variable_cost_rate=0.5,
                       fixed_costs=10, depreciation0=1, tax=0.3, nwc_sales_rate=0.1,
                       capex_per_unit_expansion=0.5, useful_life_years=8)


def test_terminal_value_gordon_matches_formula():
    tv = terminal_value_gordon(cashflow_next=1000.0, discount_rate=0.10, g=0.04)
    assert tv == pytest.approx(1000.0 / 0.06, abs=1e-9)


def test_terminal_value_gordon_rejects_rate_not_above_g():
    with pytest.raises(ValuationError, match="mayor que g"):
        terminal_value_gordon(1000.0, discount_rate=0.04, g=0.04)
    with pytest.raises(ValuationError, match="mayor que g"):
        terminal_value_gordon(1000.0, discount_rate=0.03, g=0.04)


def test_present_value_matches_manual_discounting():
    pv = present_value([100.0, 100.0], discount_rate=0.10)
    expected = 100 / 1.10 + 100 / 1.10**2
    assert pv == pytest.approx(expected, abs=1e-9)


def test_fcff_and_fcfe_are_simple_linear_formulas():
    assert fcff(ebit=1000, tax=0.3, depreciation=200, capex=150, delta_nwc=50) == pytest.approx(
        1000 * 0.7 + 200 - 150 - 50
    )
    assert fcfe(net_income=700, depreciation=200, capex=150, delta_nwc=50, net_debt_issued=30) == pytest.approx(
        700 + 200 - 150 - 50 + 30
    )
