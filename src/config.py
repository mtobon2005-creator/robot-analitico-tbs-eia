"""Configuración de identidad del sistema (RF-01).

EDITAR estos valores cuando el equipo esté conformado (nombre del equipo,
integrantes completos). No afecta la lógica del sistema, solo la
identidad mostrada en la interfaz.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TeamMember:
    name: str
    role: str = ""


@dataclass(frozen=True)
class AppIdentity:
    team_name: str
    members: tuple[TeamMember, ...]
    system_name: str
    version: str
    updated_at: str  # fecha de la última actualización, formato AAAA-MM-DD
    avatar_alt_text: str


# --- EDITAR AQUÍ cuando se conforme el equipo (3-4 integrantes, punto 1.1 de la guía) ---
APP_IDENTITY = AppIdentity(
    team_name="Equipo pendiente de conformar",
    members=(
        TeamMember(name="Integrante 1 (pendiente)"),
        TeamMember(name="Integrante 2 (pendiente)"),
        TeamMember(name="Integrante 3 (pendiente)"),
    ),
    system_name="Robot Analítico TBS-EIA",
    version="0.1.0",
    updated_at="2026-09-14",
    avatar_alt_text="Logo del Robot Analítico TBS-EIA: un ícono de gráfico de "
    "dispersión estilizado sobre fondo oscuro, representando el mapa "
    "rendimiento-riesgo.",
)

# Mínimo de activos exigido por la guía (RF-03, RF-19, 5.8).
N_MIN_ACTIVOS = 20

# Frecuencias soportadas y periodos por año (tabla sección 5.2).
FRECUENCIAS = {
    "Diaria": 252,
    "Semanal": 52,
    "Mensual": 12,
}

# Límite operacional de H (RF-04, punto 69): debe justificarse por los
# datos, la capacidad de cómputo y la utilidad analítica — no puede
# limitarse a botones fijos, pero sí necesita un tope documentado.
# 252 ≈ un año de periodos diarios: más allá de eso, la validación
# walk-forward (sección 5.5, T-11) empieza a exigir ventanas de
# entrenamiento poco realistas para un piloto académico.
MAX_HORIZON_PERIODS = 252
