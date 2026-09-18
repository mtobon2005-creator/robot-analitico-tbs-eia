"""RF-16 a RF-18: VaR individual, niveles de entrada/salida y
probabilidades terminales para la posición larga obligatoria.

Todas las fórmulas de la sección 5.6/5.7 de la guía, verificadas
contra VAR99-A-01, VAR99-B-01 y COST-B-01 (ver
tests/unit/test_rf16_18_risk.py).
"""
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from src.forecasting import HorizonDistribution, price_quantile

DEFAULT_P_L = 0.05
DEFAULT_P_U = 0.95
DEFAULT_BR_MIN = 1.00
DEFAULT_C_B = 0.0
DEFAULT_C_S = 0.0

_EPS_DETERMINISTIC = 1e-12  # sección 5.7: ε = 1e-12·max(1, E)


class InvalidTailProbabilities(ValueError):
    pass


class InvalidCostRate(ValueError):
    pass


# --- RF-16: VaR paramétrico individual ---------------------------------------

@dataclass(frozen=True)
class VarResult:
    confidence: float  # c, ej. 0.95 o 0.99
    horizon: int
    capital: float
    fraction: float  # VaR_frac — nunca negativo (piso en 0)
    monetary: float  # VaR_$ = capital · fraction


def compute_var(dist: HorizonDistribution, confidence: float, capital: float) -> VarResult:
    """Sección 5.6:
    z_c = Φ⁻¹(c)
    q_{1-c} = m_h - z_c·√v_h
    VaR_frac = max(0, 1 - exp(q_{1-c}))
    VaR_$ = capital · VaR_frac
    """
    if not (0 < confidence < 1):
        raise ValueError("El nivel de confianza debe estar en (0, 1).")

    z_c = stats.norm.ppf(confidence)
    q_1_minus_c = dist.m_h - z_c * dist.sd_h
    fraction = max(0.0, 1.0 - np.exp(q_1_minus_c))

    return VarResult(
        confidence=confidence,
        horizon=dist.h,
        capital=capital,
        fraction=fraction,
        monetary=fraction * capital,
    )


# --- RF-17: niveles de entrada, stop-loss, take-profit -----------------------

def validate_tail_probabilities(p_l: float, p_u: float) -> None:
    if not (0 < p_l < 0.5 < p_u < 1):
        raise InvalidTailProbabilities(
            "Se requiere 0 < p_L < 0.5 < p_U < 1 "
            f"(recibido p_L={p_l}, p_U={p_u})."
        )


def validate_cost_rate(c_b: float, c_s: float) -> None:
    if c_b < 0:
        raise InvalidCostRate("c_b (costo de compra) debe ser >= 0.")
    if not (0 <= c_s < 1):
        raise InvalidCostRate("c_s (costo de venta) debe cumplir 0 <= c_s < 1.")


def equilibrium_price(entry: float, c_b: float, c_s: float) -> float:
    """P_BE = E · (1+c_b) / (1-c_s)."""
    validate_cost_rate(c_b, c_s)
    return entry * (1 + c_b) / (1 - c_s)


@dataclass(frozen=True)
class SignalResult:
    entry: float
    sl_h: float
    tp_h: float
    p_be: float
    d_neto: float
    u_neto: float
    br_bruto: float | None  # None si E <= SL_H (no calculable)
    br_neto: float | None  # None si D_neto <= 0
    prob_win: float
    prob_loss: float
    prob_neutral: float
    has_signal: bool
    failed_conditions: list[str] = field(default_factory=list)


def _compute_probabilities(
    p_t: float, dist: HorizonDistribution, p_be: float
) -> tuple[float, float, float]:
    """Sección 5.7: rama continua (v_h > 0) usa Φ; rama determinista
    (v_h == 0) asigna probabilidad 1 a ganar/perder/neutral según el
    precio de equilibrio ± epsilon, sin dividir por cero."""
    if dist.v_h > 0:
        z = (np.log(p_be / p_t) - dist.m_h) / dist.sd_h
        prob_win = 1 - stats.norm.cdf(z)
        prob_loss = stats.norm.cdf(z)
        return prob_win, prob_loss, 0.0

    # Rama determinista (v_h == 0).
    p_star = p_t * np.exp(dist.m_h)
    eps = _EPS_DETERMINISTIC * max(1.0, p_t)
    if p_star > p_be + eps:
        return 1.0, 0.0, 0.0
    if p_star < p_be - eps:
        return 0.0, 1.0, 0.0
    return 0.0, 0.0, 1.0


def evaluate_signal(
    p_t: float,
    dist: HorizonDistribution,
    p_l: float = DEFAULT_P_L,
    p_u: float = DEFAULT_P_U,
    br_min: float = DEFAULT_BR_MIN,
    c_b: float = DEFAULT_C_B,
    c_s: float = DEFAULT_C_S,
) -> SignalResult:
    """RF-17/RF-18 completos: calcula entrada, SL_H, TP_H, precio de
    equilibrio, montos netos, razón beneficio-riesgo y probabilidades
    terminales, y determina si hay señal reproducible. Cualquier falla
    de las condiciones de 5.7 produce 'no señal' (has_signal=False)
    pero SIEMPRE devuelve los valores calculados y qué condición(es)
    fallaron — nunca lanza una excepción por 'no señal', porque una no
    señal sustentada es un resultado válido, no un error."""
    validate_tail_probabilities(p_l, p_u)
    validate_cost_rate(c_b, c_s)

    entry = p_t
    sl_h = price_quantile(p_t, dist, p_l)
    tp_h = price_quantile(p_t, dist, p_u)
    p_be = equilibrium_price(entry, c_b, c_s)

    d_neto = entry * (1 + c_b) - sl_h * (1 - c_s)
    u_neto = tp_h * (1 - c_s) - entry * (1 + c_b)
    br_bruto = (tp_h - entry) / (entry - sl_h) if entry > sl_h else None
    br_neto = (u_neto / d_neto) if d_neto > 0 else None

    prob_win, prob_loss, prob_neutral = _compute_probabilities(p_t, dist, p_be)

    failed: list[str] = []
    if not (sl_h < entry < tp_h):
        failed.append("SL_H < E < TP_H")
    if not (p_be >= entry):
        failed.append("P_BE >= E")
    if not (p_be < tp_h):
        failed.append("P_BE < TP_H")
    if not (d_neto > 0):
        failed.append("D_neto > 0")
    if not (u_neto > 0):
        failed.append("U_neto > 0")
    if br_neto is None or br_neto < br_min:
        failed.append(f"BR_neto >= BR_min ({br_min})")

    return SignalResult(
        entry=entry,
        sl_h=sl_h,
        tp_h=tp_h,
        p_be=p_be,
        d_neto=d_neto,
        u_neto=u_neto,
        br_bruto=br_bruto,
        br_neto=br_neto,
        prob_win=prob_win,
        prob_loss=prob_loss,
        prob_neutral=prob_neutral,
        has_signal=(len(failed) == 0),
        failed_conditions=failed,
    )
