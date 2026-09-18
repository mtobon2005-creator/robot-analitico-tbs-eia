"""RF-13 a RF-15: forecasting homocedástico multihorizonte.

Modelo A (caminata aleatoria sin deriva, benchmark obligatorio) y
Modelo B (lognormal con deriva, parámetros constantes) — sección 5.5
de la guía. Todas las fórmulas verificadas contra MODEL-A-01,
MODEL-B-01, PATH-B-01 y WF-01 (ver tests/unit/test_rf13_15_forecasting.py).

RF-16 a RF-18 (VaR, niveles de entrada/salida, probabilidades) NO
están en este módulo — reutilizarán `TrainParams`/`horizon_params`
de aquí, pero se implementan aparte.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

MODEL_NAMES = ("A", "B")


class UnknownModel(ValueError):
    pass


class InsufficientWalkForwardSample(Exception):
    pass


# --- RF-13: estimación de parámetros (solo con entrenamiento) --------------

@dataclass(frozen=True)
class TrainParams:
    mu_train: float  # μ̂_train — media por periodo, solo con entrenamiento
    sigma_train: float  # σ̂_train — volatilidad por periodo, solo con entrenamiento


def estimate_train_params(returns_train: pd.Series) -> TrainParams:
    """Sección 5.5: 'Todos los parámetros se estimarán únicamente con
    el bloque de entrenamiento'. Estimaciones POR PERIODO, no
    anualizadas (a diferencia de RF-11)."""
    return TrainParams(
        mu_train=float(returns_train.mean()),
        sigma_train=float(returns_train.std(ddof=1)),
    )


# --- RF-13/14: distribución del modelo en el horizonte h --------------------

@dataclass(frozen=True)
class HorizonDistribution:
    model: str
    h: int
    m_h: float  # media de la distribución acumulada G_t,h
    v_h: float  # varianza de la distribución acumulada G_t,h

    @property
    def sd_h(self) -> float:
        return float(np.sqrt(self.v_h))


def horizon_params(model: str, params: TrainParams, h: int) -> HorizonDistribution:
    """Sección 5.5, notación común por modelo:
    Modelo A: m_{A,h}=0,           v_{A,h}=h·σ̂_train²
    Modelo B: m_{B,h}=h·μ̂_train,   v_{B,h}=h·σ̂_train²
    """
    if model not in MODEL_NAMES:
        raise UnknownModel(f"Modelo desconocido: '{model}'. Usa 'A' o 'B'.")
    if h < 1:
        raise ValueError("El horizonte h debe ser un entero positivo.")

    v_h = h * params.sigma_train**2
    m_h = 0.0 if model == "A" else h * params.mu_train
    return HorizonDistribution(model=model, h=h, m_h=m_h, v_h=v_h)


def price_median(p_t: float, dist: HorizonDistribution) -> float:
    """Mediana(P_t+h) = P_t · exp(m_h)."""
    return p_t * np.exp(dist.m_h)


def price_mean(p_t: float, dist: HorizonDistribution) -> float:
    """E(P_t+h) = P_t · exp(m_h + v_h/2) (la media aritmética NO es
    constante para el Modelo A por la transformación exponencial)."""
    return p_t * np.exp(dist.m_h + dist.v_h / 2)


def price_quantile(p_t: float, dist: HorizonDistribution, p: float) -> float:
    """Q_p(P_t+h) = P_t · exp(m_h + z_p·σ̂_train·√h), con z_p el cuantil
    de la normal estándar. `p` en (0, 1), ej. 0.05 o 0.95."""
    z_p = stats.norm.ppf(p)
    return p_t * np.exp(dist.m_h + z_p * dist.sd_h)


# --- RF-14: trayectoria analítica completa de 1 a H -------------------------

@dataclass(frozen=True)
class TrajectoryStep:
    h: int
    m_h: float
    v_h: float
    median: float
    mean: float
    q05: float
    q95: float


def generate_trajectory(
    p_t: float, params: TrainParams, model: str, horizon: int
) -> list[TrajectoryStep]:
    """RF-14: 'la trayectoria analítica completa de 1 a H y la
    distribución terminal'. Recalcula todo si cambian H, frecuencia,
    activo, ventana o modelo (porque siempre se llama de nuevo con los
    parámetros correspondientes — no hay caché oculto)."""
    steps = []
    for h in range(1, horizon + 1):
        dist = horizon_params(model, params, h)
        steps.append(
            TrajectoryStep(
                h=h,
                m_h=dist.m_h,
                v_h=dist.v_h,
                median=price_median(p_t, dist),
                mean=price_mean(p_t, dist),
                q05=price_quantile(p_t, dist, 0.05),
                q95=price_quantile(p_t, dist, 0.95),
            )
        )
    return steps


# --- RF-15: validación walk-forward (convención 5.5) ------------------------

@dataclass(frozen=True)
class WalkForwardResult:
    model: str
    horizon: int
    n_origins: int
    origins: list[int]
    mae: float
    rmse: float
    coverage: float  # fracción de orígenes con Y_j dentro del intervalo central 90%
    direction_accuracy: float | None  # None si no hay orígenes calificados (ej. Modelo A)
    direction_n: int  # orígenes que calificaron para exactitud direccional


_EPS_DIRECTION = 1e-12
_N_ORIGINS = 10
_ORIGIN_OFFSET = 9  # 'T-H-9+j' de la sección 5.5


def walk_forward_sufficiency(t_returns: int, m: int, horizon: int) -> tuple[bool, int]:
    """n_min = max(2m, 5H); suficiencia si T >= n_min + H + 9."""
    n_min = max(2 * m, 5 * horizon)
    sufficient = t_returns >= n_min + horizon + _ORIGIN_OFFSET
    return sufficient, n_min


def validate_walk_forward(
    prices: pd.Series, returns: pd.Series, model: str, horizon: int, m: int
) -> WalkForwardResult:
    """Sección 5.5 completa: ventana expansiva, últimos 10 orígenes,
    reestimación solo con datos disponibles en cada origen, MAE/RMSE
    en logespacio, cobertura del intervalo central 90%, y exactitud
    direccional solo cuando |m_h| y |Y_j| superan epsilon=1e-12.

    `prices` y `returns` deben corresponder a la MISMA serie ya
    limpia/remuestreada (RF-06/RF-07): returns.iloc[k] = ln(prices[k+1]/prices[k]).
    """
    t = len(returns)
    sufficient, n_min = walk_forward_sufficiency(t, m, horizon)
    if not sufficient:
        raise InsufficientWalkForwardSample(
            f"Muestra insuficiente para walk-forward: T={t}, se requiere "
            f"T >= n_min + H + 9 = {n_min + horizon + _ORIGIN_OFFSET}."
        )

    origins = [t - horizon - _ORIGIN_OFFSET + j for j in range(_N_ORIGINS)]

    errors = []
    covered = []
    direction_matches = []

    for origin in origins:
        train_returns = returns.iloc[:origin]  # g_1..g_origin (ventana expansiva)
        params = estimate_train_params(train_returns)
        dist = horizon_params(model, params, horizon)

        y_j = float(np.log(prices.iloc[origin + horizon] / prices.iloc[origin]))
        error = y_j - dist.m_h
        errors.append(error)

        q05 = dist.m_h + stats.norm.ppf(0.05) * dist.sd_h
        q95 = dist.m_h + stats.norm.ppf(0.95) * dist.sd_h
        covered.append(q05 <= y_j <= q95)

        if abs(dist.m_h) > _EPS_DIRECTION and abs(y_j) > _EPS_DIRECTION:
            direction_matches.append(np.sign(dist.m_h) == np.sign(y_j))

    errors_arr = np.array(errors)
    direction_n = len(direction_matches)

    return WalkForwardResult(
        model=model,
        horizon=horizon,
        n_origins=_N_ORIGINS,
        origins=origins,
        mae=float(np.mean(np.abs(errors_arr))),
        rmse=float(np.sqrt(np.mean(errors_arr**2))),
        coverage=float(np.mean(covered)),
        direction_accuracy=float(np.mean(direction_matches)) if direction_matches else None,
        direction_n=direction_n,
    )
