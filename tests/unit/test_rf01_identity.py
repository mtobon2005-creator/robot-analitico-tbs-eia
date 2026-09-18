"""Pruebas RF-01: identidad, política de ejecución y disclaimer.

Estas pruebas verifican el contenido (texto obligatorio, campos mínimos)
que RF-01 exige, sin depender de renderizar Streamlit.
"""
from src.config import APP_IDENTITY, FRECUENCIAS, N_MIN_ACTIVOS
from src.disclaimer import (
    DISCLAIMER_TEXT,
    EXECUTION_POLICY_SECTIONS,
)

REQUIRED_POLICY_FIELDS = {
    "Universo",
    "Datos",
    "Acceso y privacidad",
    "Posición",
    "Ventana y frecuencia",
    "Rendimiento",
    "Horizonte",
    "Modelo",
    "Riesgo",
    "Entrada y salidas",
    "Selección",
    "No operar",
    "Limitaciones",
}


def test_identity_has_required_fields():
    assert APP_IDENTITY.system_name
    assert APP_IDENTITY.version
    assert APP_IDENTITY.updated_at
    assert APP_IDENTITY.team_name
    assert len(APP_IDENTITY.members) >= 1
    assert APP_IDENTITY.avatar_alt_text  # accesibilidad, punto 42


def test_disclaimer_mentions_mandatory_scope_limits():
    # El texto no puede reducir el alcance mínimo (sección 3.3).
    lowered = DISCLAIMER_TEXT.lower()
    for phrase in [
        "teoría moderna de portafolios",
        "tech business school",
        "universidad eia",
        "fines académicos y educativos",
        "no ejecuta operaciones",
        "ni garantiza resultados",
    ]:
        assert phrase in lowered, f"Falta frase obligatoria: {phrase!r}"


def test_execution_policy_covers_all_mandatory_fields():
    # Tabla de campos obligatorios de la política de ejecución (sección 3.3).
    assert REQUIRED_POLICY_FIELDS.issubset(EXECUTION_POLICY_SECTIONS.keys())
    for section, text in EXECUTION_POLICY_SECTIONS.items():
        assert text.strip(), f"Sección de política vacía: {section}"


def test_execution_policy_declares_long_only():
    text = EXECUTION_POLICY_SECTIONS["Posición"].lower()
    assert "larga" in text


def test_execution_policy_forbids_simple_returns_language():
    text = EXECUTION_POLICY_SECTIONS["Rendimiento"].lower()
    assert "logar" in text
    assert "simple" not in text or "no existe" in text


def test_config_minimum_assets_is_at_least_20():
    assert N_MIN_ACTIVOS >= 20


def test_config_frequencies_have_correct_annualization_periods():
    assert FRECUENCIAS["Diaria"] == 252
    assert FRECUENCIAS["Semanal"] == 52
    assert FRECUENCIAS["Mensual"] == 12
