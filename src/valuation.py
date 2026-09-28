"""Valoración: WACC, FCFF/FCFE, valor terminal y proyección con el
bucle ventas-capacidad-CAPEX-depreciación (v2, GUIA_V2 §9).

Caso de control: Alimentos del Norte S.A.S.
(v2/data/caso_alimentos_parametros.json).
"""
from dataclasses import dataclass

import numpy as np


class ValuationError(Exception):
    """Entrada inválida (WACC<=g, estructura de capital nula, etc.)."""


def wacc(E: float, D: float, Ke: float, Kd: float, tax: float) -> float:
    """WACC = E/(D+E)*Ke + D/(D+E)*Kd*(1-tax) (GUIA_V2 §9.1)."""
    if E < 0 or D < 0:
        raise ValuationError("E y D deben ser no negativos")
    total = D + E
    if total <= 0:
        raise ValuationError("D+E debe ser positivo")
    return (E / total) * Ke + (D / total) * Kd * (1 - tax)


def fcff(ebit: float, tax: float, depreciation: float, capex: float, delta_nwc: float) -> float:
    """FCFF = EBIT*(1-tax) + D&A - CAPEX - ΔNWC (GUIA_V2 §9.1)."""
    return ebit * (1 - tax) + depreciation - capex - delta_nwc


def fcfe(net_income: float, depreciation: float, capex: float, delta_nwc: float, net_debt_issued: float) -> float:
    """FCFE = NI + D&A - CAPEX - ΔNWC + deuda_neta_emitida (GUIA_V2 §9.1)."""
    return net_income + depreciation - capex - delta_nwc + net_debt_issued


def terminal_value_gordon(cashflow_next: float, discount_rate: float, g: float) -> float:
    """TV_H = flujo_(H+1) / (tasa-g); exige tasa>g (GUIA_V2 §9.1)."""
    if discount_rate <= g:
        raise ValuationError("La tasa de descuento debe ser mayor que g (valor terminal infinito/negativo si no)")
    return cashflow_next / (discount_rate - g)


def present_value(cashflows, discount_rate: float) -> float:
    """VP de flujos en los periodos 1..H, con signo (GUIA_V2 §9.1)."""
    cashflows = np.asarray(cashflows, dtype=float)
    if discount_rate <= -1:
        raise ValuationError("discount_rate debe ser mayor a -1")
    periods = np.arange(1, len(cashflows) + 1)
    return float(np.sum(cashflows / (1 + discount_rate) ** periods))


@dataclass(frozen=True)
class YearProjection:
    year: int
    sales: float
    ebit: float
    depreciation: float
    capex: float
    delta_nwc: float
    fcff: float
    capacity_end: float


def project_years(
    sales_growth_rates,
    sales0: float,
    capacity0: float,
    variable_cost_rate: float,
    fixed_costs: float,
    depreciation0: float,
    tax: float,
    nwc_sales_rate: float,
    capex_per_unit_expansion: float,
    useful_life_years: int,
) -> list[YearProjection]:
    """Proyecta H años con el bucle ventas-capacidad-CAPEX-depreciación
    (GUIA_V2 §9.1, P115).

    Regla implementada (una interpretación razonable, no la única
    posible — documenta/ajusta la tuya si el caso fuente especifica
    otra): si las ventas del año caben en la capacidad disponible AL
    INICIO de ese año, el CAPEX es solo de mantenimiento (=la
    depreciación del año; la capacidad no cambia). Si las exceden, se
    invierte `capex_per_unit_expansion` por cada unidad de capacidad
    adicional necesaria; ese capex se deprecia en línea recta sobre
    `useful_life_years` empezando el año SIGUIENTE (evita circularidad
    dentro del mismo año) y la capacidad ampliada queda disponible
    desde el año siguiente en adelante."""
    if useful_life_years <= 0:
        raise ValuationError("useful_life_years debe ser positivo")
    if sales0 <= 0 or capacity0 <= 0:
        raise ValuationError("sales0 y capacity0 deben ser positivos")

    sales_prev = sales0
    capacity = capacity0
    nwc_prev = nwc_sales_rate * sales0
    tranches: list[tuple[int, float]] = []  # (año_creación, monto_anual)

    results = []
    for year, g in enumerate(sales_growth_rates, start=1):
        sales = sales_prev * (1 + g)

        depreciation = depreciation0 + sum(
            amt for created_year, amt in tranches if created_year < year <= created_year + useful_life_years
        )

        if sales <= capacity:
            capex_expansion = 0.0
        else:
            needed_capacity = sales - capacity
            capex_expansion = capex_per_unit_expansion * needed_capacity
            tranches.append((year, capex_expansion / useful_life_years))
            capacity += needed_capacity

        capex_total = depreciation + capex_expansion
        ebit = sales * (1 - variable_cost_rate) - fixed_costs - depreciation
        nwc = nwc_sales_rate * sales
        delta_nwc = nwc - nwc_prev
        fcff_year = fcff(ebit, tax, depreciation, capex_total, delta_nwc)

        results.append(
            YearProjection(
                year=year, sales=sales, ebit=ebit, depreciation=depreciation,
                capex=capex_total, delta_nwc=delta_nwc, fcff=fcff_year, capacity_end=capacity,
            )
        )
        sales_prev = sales
        nwc_prev = nwc

    return results
