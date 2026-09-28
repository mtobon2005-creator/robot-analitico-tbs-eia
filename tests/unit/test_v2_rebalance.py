"""Pruebas del motor de rebalanceo (GUIA_V2 §7).

P2-25: deriva de pesos y cantidades previas correctamente calculadas.
P2-26: turnover, nominal negociado, costos y caja reconciliados.
P2-28: abstención/estado explícito cuando algo impide operar
       (aquí: caja negativa, apalancamiento, patrimonio no positivo).
"""
import json
from pathlib import Path

import numpy as np
import pytest

from src.rebalance import RebalanceError, rebalance

V2_DATA = Path(__file__).resolve().parents[2] / "v2" / "data"


@pytest.fixture
def control():
    return json.loads((V2_DATA / "rebalanceo_control.json").read_text())


def test_rebalance_matches_manual_control(control):
    result = rebalance(
        cantidades=control["cantidades"],
        precios_nuevos=control["precios_nuevos"],
        caja=control["caja"],
        pesos_objetivo=control["pesos_objetivo"],
        costo_por_nominal=control["costo_por_nominal"],
        slippage=control["slippage"],
        flujos=control["flujos"],
        fracciones=control["fracciones"],
    )
    # Derivado a mano: nominal negociado es constante (2800) porque el
    # objetivo 50/50 queda entre los valores actuales (6600 y 3800) sin
    # importar el pequeño ajuste de V_post por costos.
    assert result.patrimonio_pre == pytest.approx(10400.0)
    assert result.nominal_negociado == pytest.approx(2800.0, abs=1e-6)
    assert result.costos_totales == pytest.approx(2.8, abs=1e-9)
    assert result.patrimonio_post == pytest.approx(10397.2, abs=1e-6)
    np.testing.assert_allclose(
        result.cantidades_finales, [47.26, 54.722105263], atol=1e-6
    )
    assert result.caja_final == pytest.approx(0.0, abs=1e-6)
    assert result.turnover_unilateral == pytest.approx(0.134615385, abs=1e-6)


def test_v_post_equals_v_pre_minus_costos_no_flujos(control):
    result = rebalance(
        cantidades=control["cantidades"],
        precios_nuevos=control["precios_nuevos"],
        caja=control["caja"],
        pesos_objetivo=control["pesos_objetivo"],
        costo_por_nominal=control["costo_por_nominal"],
    )
    # GUIA_V2 §7.1: V_post = V_pre - costos (sin flujos).
    assert result.patrimonio_post == pytest.approx(
        result.patrimonio_pre - result.costos_totales, abs=1e-9
    )


def test_no_trade_needed_has_zero_cost():
    """Si los pesos objetivo ya coinciden con los actuales, no hay nada
    que operar ni costo que pagar (evita costos fantasma)."""
    result = rebalance(
        cantidades=[50, 50],
        precios_nuevos=[100, 100],
        caja=0,
        pesos_objetivo=[0.5, 0.5],
        costo_por_nominal=0.001,
    )
    assert result.costos_totales == pytest.approx(0.0, abs=1e-9)
    assert result.nominal_negociado == pytest.approx(0.0, abs=1e-9)
    np.testing.assert_allclose(result.cantidades_finales, [50, 50], atol=1e-9)


def test_partial_cash_target_leaves_positive_cash():
    """Si suma(pesos_objetivo)<1, el resto queda en caja, no se fuerza
    a invertir todo (GUIA_V2 §7.1: no renormalizar para ocultar caja)."""
    result = rebalance(
        cantidades=[100, 0],
        precios_nuevos=[100, 100],
        caja=0,
        pesos_objetivo=[0.5, 0.0],
        costo_por_nominal=0.0,
    )
    assert result.caja_final == pytest.approx(5000.0, abs=1e-6)


def test_rejects_leverage_above_budget():
    with pytest.raises(RebalanceError, match="apalancamiento"):
        rebalance([50, 50], [100, 100], 0, pesos_objetivo=[0.7, 0.7], costo_por_nominal=0.001)


def test_rejects_short_positions_in_target():
    with pytest.raises(RebalanceError, match="cortas"):
        rebalance([50, 50], [100, 100], 0, pesos_objetivo=[1.2, -0.2], costo_por_nominal=0.001)


def test_rejects_non_positive_wealth():
    with pytest.raises(RebalanceError, match="patrimonio disponible"):
        rebalance([0, 0], [100, 100], caja=-500, pesos_objetivo=[0.5, 0.5], costo_por_nominal=0.001)


def test_rejects_negative_final_cash_from_excessive_costs():
    """Con costo_por_nominal=1.5 (150%, deliberadamente absurdo) y un
    objetivo que deja la mitad en caja, el punto fijo converge (factor
    de contracción 0.75, verificado por separado) a un patrimonio
    posterior negativo: la caja no puede quedar en cero como si nada
    hubiera pasado, se reporta como error, no se oculta."""
    with pytest.raises(RebalanceError, match="caja final negativa"):
        rebalance(
            cantidades=[100, 0],
            precios_nuevos=[100, 100],
            caja=0,
            pesos_objetivo=[0.0, 0.5],
            costo_por_nominal=1.5,
        )


def test_integer_lots_round_and_report_actual_execution(control):
    """fracciones=False: las cantidades ejecutables son enteras y el
    costo/caja se recalculan sobre lo realmente ejecutado, no sobre el
    ideal fraccionario (GUIA_V2 §7.1, P90)."""
    result = rebalance(
        cantidades=control["cantidades"],
        precios_nuevos=control["precios_nuevos"],
        caja=control["caja"],
        pesos_objetivo=control["pesos_objetivo"],
        costo_por_nominal=control["costo_por_nominal"],
        fracciones=False,
    )
    assert np.all(result.cantidades_finales == np.round(result.cantidades_finales))
    # V_post = V_disponible - costos también debe cumplirse con enteros.
    assert result.patrimonio_post == pytest.approx(
        result.patrimonio_pre - result.costos_totales, abs=1e-9
    )
