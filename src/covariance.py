"""Covarianza con shrinkage hacia la diagonal (v2, GUIA_V2 §4.2, P39).

La covarianza muestral pura tiene ruido de estimación grande cuando N
se acerca a T (P37/P38) — visible en Portafolio v2 como carteras muy
concentradas y Sharpe irrealmente altos (Markowitz "puro" explota ese
ruido). Shrinkage la combina con un objetivo más simple y estable para
reducir el ruido a costa de sesgo:

    Sigma_shrunk = (1-delta)*Sigma_sample + delta*Sigma_target

Sigma_target aquí es diag(diag(Sigma_sample)): mismas varianzas
individuales, covarianzas cruzadas puestas en cero. delta es una
decisión del estudiante (P39: "cómo elige sus parámetros sin mirar la
prueba") — este módulo no la optimiza ni la infiere de ningún
resultado posterior.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ShrinkageResult:
    Sigma: np.ndarray
    delta: float
    Sigma_sample: np.ndarray
    Sigma_target: np.ndarray


def shrink_to_diagonal(Sigma_sample, delta: float) -> ShrinkageResult:
    """delta=0 reproduce la covarianza muestral sin cambios; delta=1
    trata los activos como independientes (covarianzas cruzadas en
    cero, varianzas individuales intactas). PSD por construcción:
    combinación convexa de dos matrices PSD (la muestral y su propia
    diagonal, que también es PSD al tener solo varianzas >=0)."""
    Sigma_sample = np.asarray(Sigma_sample, dtype=float)
    n = Sigma_sample.shape[0]
    if Sigma_sample.shape != (n, n):
        raise ValueError("Sigma_sample debe ser NxN")
    if not np.allclose(Sigma_sample, Sigma_sample.T, atol=1e-10):
        raise ValueError("Sigma_sample no es simétrica")
    if not (0.0 <= delta <= 1.0):
        raise ValueError("delta debe estar en [0,1]")

    Sigma_target = np.diag(np.diag(Sigma_sample))
    Sigma_shrunk = (1 - delta) * Sigma_sample + delta * Sigma_target
    return ShrinkageResult(
        Sigma=Sigma_shrunk, delta=delta, Sigma_sample=Sigma_sample, Sigma_target=Sigma_target
    )
