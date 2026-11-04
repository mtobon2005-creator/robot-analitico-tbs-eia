"""Línea del Mercado de Capitales, desempeño ajustado por riesgo y
alfa de Jensen (sustentación final, núcleo financiero de referencia:
"Portafolios y frontera eficiente" y "Desempeño y benchmark").

Todas las funciones son agnósticas a la convención de retorno (simple
o log) de quien las llama, siempre que el mismo retorno/beta/volatilidad
anualizados que entran aquí sean consistentes con los que ya produce
`src/portfolio.py` (Markowitz, retornos simples) para la cartera en
cuestión — ver docstring de `portfolio_log_returns`.
"""
from dataclasses import dataclass

import numpy as np


class PerformanceError(Exception):
    """Entrada inválida (volatilidad/beta cero, muestra insuficiente)."""


def capital_market_line(rf: float, tangency_return: float, tangency_volatility: float, sigma_values) -> np.ndarray:
    """CML: E[R_p] = rf + ((E[R_tan]-rf)/sigma_tan) * sigma_p — la recta
    de combinaciones activo libre de riesgo + cartera tangente que
    domina la frontera eficiente de activos riesgosos solos."""
    if tangency_volatility <= 0:
        raise PerformanceError("tangency_volatility debe ser positiva")
    sigma_values = np.asarray(sigma_values, dtype=float)
    slope = (tangency_return - rf) / tangency_volatility
    return rf + slope * sigma_values


def treynor_ratio(portfolio_return: float, rf: float, beta_p: float) -> float:
    """Treynor = (R_p - rf) / beta_p — premio por riesgo SISTEMÁTICO
    únicamente (a diferencia de Sharpe, que divide por volatilidad
    total)."""
    if beta_p == 0:
        raise PerformanceError("beta_p no puede ser cero: Treynor indefinido")
    return (portfolio_return - rf) / beta_p


def jensens_alpha(portfolio_return: float, rf: float, beta_p: float, market_return: float) -> float:
    """Alfa de Jensen = R_p - [rf + beta_p*(R_m - rf)] — exceso de
    retorno de la cartera sobre lo que el CAPM exige dado su beta."""
    required_return = rf + beta_p * (market_return - rf)
    return portfolio_return - required_return


@dataclass(frozen=True)
class InformationRatioResult:
    mean_active_annual: float
    tracking_error_annual: float
    information_ratio: float
    n_obs: int


def information_ratio(active_returns, periods_per_year: int) -> InformationRatioResult:
    """IR = retorno activo anualizado / tracking error anualizado, con
    retorno activo = retorno de cartera - retorno de benchmark por
    periodo. El retorno activo anualiza linealmente (mean*m, igual que
    mu en Markowitz); el tracking error anualiza por raíz de m (igual
    que sigma) — NO es la misma convención de anualización, por
    diseño (varianza escala linealmente con el tiempo, no la
    desviación estándar)."""
    active_returns = np.asarray(active_returns, dtype=float)
    if len(active_returns) < 2:
        raise PerformanceError("se necesitan al menos 2 observaciones")
    if periods_per_year <= 0:
        raise PerformanceError("periods_per_year debe ser positivo")

    mean_period = float(active_returns.mean())
    std_period = float(active_returns.std(ddof=1))
    mean_annual = mean_period * periods_per_year
    std_annual = std_period * np.sqrt(periods_per_year)
    if np.isclose(std_annual, 0.0, atol=1e-12):
        raise PerformanceError("tracking error es cero: Information Ratio indefinido")

    return InformationRatioResult(
        mean_active_annual=mean_annual,
        tracking_error_annual=std_annual,
        information_ratio=mean_annual / std_annual,
        n_obs=len(active_returns),
    )


def systematic_risk_share(r_squared: float) -> dict:
    """R² de la regresión de un activo/cartera contra el mercado =
    proporción de su varianza explicada por el mercado (riesgo
    sistemático); 1-R² es la proporción idiosincrática (riesgo no
    sistemático, diversificable)."""
    if not (0 <= r_squared <= 1):
        raise PerformanceError("r_squared debe estar en [0, 1]")
    return {"sistematico": r_squared, "no_sistematico": 1.0 - r_squared}
