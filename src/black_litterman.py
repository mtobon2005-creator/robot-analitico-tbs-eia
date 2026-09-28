"""Black-Litterman: actualiza expectativas mediante un prior y opiniones
con incertidumbre (v2, GUIA_V2 §6). No reemplaza el solver de
Markowitz: entrega mu/Sigma para que `src/portfolio.py` optimice.

Todo en excesos de rendimiento sobre rf (GUIA_V2 §6.1):
    pi = delta * Sigma @ w_ref
    B  = tau * Sigma
    A  = P @ B @ P.T + Omega
    mu_BL_exceso = pi + B @ P.T @ solve(A, Q - P @ pi)
    M  = B - B @ P.T @ solve(A, P @ B)
    Sigma_predictiva = Sigma + M

Sin views (K=0): mu_BL_exceso=pi y M=B (GUIA_V2 §6.2, P2-19).
"""
from dataclasses import dataclass

import numpy as np


class BlackLittermanError(Exception):
    """Dimensiones inconsistentes o matriz no invertible."""


@dataclass(frozen=True)
class BlackLittermanResult:
    mu_excess: np.ndarray
    Sigma_predictive: np.ndarray
    M: np.ndarray
    pi_excess: np.ndarray


def _validate_sigma(Sigma: np.ndarray) -> None:
    n = Sigma.shape[0]
    if Sigma.shape != (n, n):
        raise BlackLittermanError("Sigma debe ser NxN")
    if not np.allclose(Sigma, Sigma.T, atol=1e-10):
        raise BlackLittermanError("Sigma no es simétrica")


def implied_equilibrium_returns(Sigma, w_ref, delta) -> np.ndarray:
    """pi = delta * Sigma @ w_ref (GUIA_V2 §6.1). En excesos sobre rf:
    quien llama debe sumar rf aparte si necesita el total, para no
    sumarla dos veces (P67)."""
    Sigma = np.asarray(Sigma, dtype=float)
    w_ref = np.asarray(w_ref, dtype=float)
    _validate_sigma(Sigma)
    if w_ref.shape != (Sigma.shape[0],):
        raise BlackLittermanError("w_ref debe tener un peso por activo")
    if delta <= 0:
        raise BlackLittermanError("delta debe ser positiva (aversión implícita)")
    return delta * Sigma @ w_ref


def black_litterman(Sigma, w_ref, delta, tau, P=None, Q=None, Omega=None) -> BlackLittermanResult:
    """Calcula el posterior de Black-Litterman.

    `P`, `Q`, `Omega` en None (o K=0 filas) reproduce el estado sin
    views: mu_excess=pi, M=B (P2-19). Con Q=P@pi exacto, mu_excess no
    se mueve del prior aunque haya views (P2-20)."""
    Sigma = np.asarray(Sigma, dtype=float)
    w_ref = np.asarray(w_ref, dtype=float)
    _validate_sigma(Sigma)
    n = Sigma.shape[0]
    if tau <= 0:
        raise BlackLittermanError("tau debe ser positiva")

    pi = implied_equilibrium_returns(Sigma, w_ref, delta)
    B = tau * Sigma

    if P is None or len(P) == 0:
        return BlackLittermanResult(mu_excess=pi.copy(), Sigma_predictive=Sigma + B, M=B, pi_excess=pi)

    P = np.asarray(P, dtype=float)
    Q = np.asarray(Q, dtype=float)
    Omega = np.asarray(Omega, dtype=float)
    k = P.shape[0]
    if P.shape != (k, n):
        raise BlackLittermanError("P debe ser KxN (K=numero de views, N=activos)")
    if Q.shape != (k,):
        raise BlackLittermanError("Q debe tener K elementos, uno por view")
    if Omega.shape != (k, k):
        raise BlackLittermanError("Omega debe ser KxK")
    if not np.allclose(Omega, Omega.T, atol=1e-10):
        raise BlackLittermanError("Omega no es simétrica")

    A = P @ B @ P.T + Omega
    try:
        x = np.linalg.solve(A, Q - P @ pi)
        y = np.linalg.solve(A, P @ B)
    except np.linalg.LinAlgError as exc:
        raise BlackLittermanError(f"A=P*tau*Sigma*P'+Omega no es invertible: {exc}") from exc

    mu_excess = pi + B @ P.T @ x
    M = B - B @ P.T @ y
    Sigma_predictive = Sigma + M
    return BlackLittermanResult(mu_excess=mu_excess, Sigma_predictive=Sigma_predictive, M=M, pi_excess=pi)
