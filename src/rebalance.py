"""Rebalanceo simulado con costos y caja (v2, GUIA_V2 §7).

El objetivo de pesos se define sobre el patrimonio POSTERIOR a costos
(ver v2/data/rebalanceo_control.json: "Objetivo sobre patrimonio
posterior a costos"). Esto es un punto fijo: el monto objetivo por
activo depende de V_post, pero V_post=V_pre-costos depende del monto
operado. Se resuelve por iteración (converge rápido porque el costo
es una fracción pequeña del patrimonio, GUIA_V2 §7.1).

No se renormaliza para ocultar caja negativa ni se permite apalancamiento
(GUIA_V2 §7.1): sum(pesos_objetivo)<=1 y solo posiciones largas.
"""
from dataclasses import dataclass

import numpy as np


class RebalanceError(Exception):
    """Entrada inválida o el punto fijo de costos no convergió."""


@dataclass(frozen=True)
class RebalanceResult:
    cantidades_finales: np.ndarray
    trades: np.ndarray  # positivo=compra, negativo=venta, en unidades
    caja_final: float
    patrimonio_pre: float
    patrimonio_post: float
    costos_totales: float
    nominal_negociado: float
    turnover_unilateral: float


def rebalance(
    cantidades,
    precios_nuevos,
    caja,
    pesos_objetivo,
    costo_por_nominal,
    slippage: float = 0.0,
    flujos: float = 0.0,
    fracciones: bool = True,
    max_iter: int = 500,
    tol: float = 1e-8,
) -> RebalanceResult:
    cantidades = np.asarray(cantidades, dtype=float)
    precios_nuevos = np.asarray(precios_nuevos, dtype=float)
    pesos_objetivo = np.asarray(pesos_objetivo, dtype=float)
    n = len(cantidades)

    if precios_nuevos.shape != (n,) or pesos_objetivo.shape != (n,):
        raise RebalanceError(
            "cantidades, precios_nuevos y pesos_objetivo deben tener la misma longitud"
        )
    if np.any(precios_nuevos <= 0):
        raise RebalanceError("los precios deben ser positivos")
    if np.any(pesos_objetivo < -1e-9):
        raise RebalanceError("pesos_objetivo no admite posiciones cortas en este modelo")
    if pesos_objetivo.sum() > 1 + 1e-9:
        raise RebalanceError("suma(pesos_objetivo) no puede exceder 1 (sin apalancamiento)")

    valores_actuales = cantidades * precios_nuevos
    v_pre = float(valores_actuales.sum() + caja)
    v_disponible = v_pre + flujos
    if v_disponible <= 0:
        raise RebalanceError("patrimonio disponible no positivo; no se puede rebalancear")

    cost_rate = costo_por_nominal + slippage

    v_post = v_disponible
    for _ in range(max_iter):
        objetivo_valor = pesos_objetivo * v_post
        nominal = float(np.abs(objetivo_valor - valores_actuales).sum())
        v_post_new = v_disponible - cost_rate * nominal
        if abs(v_post_new - v_post) < tol:
            v_post = v_post_new
            break
        v_post = v_post_new
    else:
        raise RebalanceError("el punto fijo costo/patrimonio no convergió")

    objetivo_valor = pesos_objetivo * v_post
    cantidades_finales = objetivo_valor / precios_nuevos
    nominal_negociado = float(np.abs(objetivo_valor - valores_actuales).sum())
    costos_totales = cost_rate * nominal_negociado

    if not fracciones:
        # Cantidades ejecutables pueden diferir del objetivo teórico por
        # lotes (GUIA_V2 §7.1); se recalculan costos y caja con las
        # cantidades enteras realmente ejecutadas, no con el ideal.
        cantidades_finales = np.round(cantidades_finales)
        trade_value = cantidades_finales * precios_nuevos - valores_actuales
        nominal_negociado = float(np.abs(trade_value).sum())
        costos_totales = cost_rate * nominal_negociado
        v_post = v_disponible - costos_totales

    caja_final = v_post - float((cantidades_finales * precios_nuevos).sum())
    if caja_final < -1e-6:
        raise RebalanceError(
            f"caja final negativa ({caja_final:.6f}); no se permite deuda (GUIA_V2 §7.1)"
        )

    trades = cantidades_finales - cantidades
    w_pre = valores_actuales / v_pre if v_pre > 0 else np.zeros(n)
    turnover_unilateral = 0.5 * float(np.abs(pesos_objetivo - w_pre).sum())

    return RebalanceResult(
        cantidades_finales=cantidades_finales,
        trades=trades,
        caja_final=max(caja_final, 0.0),
        patrimonio_pre=v_pre,
        patrimonio_post=v_post,
        costos_totales=costos_totales,
        nominal_negociado=nominal_negociado,
        turnover_unilateral=turnover_unilateral,
    )
