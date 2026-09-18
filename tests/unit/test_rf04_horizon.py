"""Pruebas RF-04: fechas, frecuencia y horizonte H."""
from datetime import date

import pytest

from src.config import MAX_HORIZON_PERIODS
from src.horizon import (
    InvalidDateRange,
    InvalidFrequency,
    InvalidHorizon,
    convert_target_date_to_periods,
    resolve_horizon,
    validate_date_range,
    validate_frequency,
    validate_horizon_periods,
)

TODAY = date(2026, 9, 14)


# --- Frecuencia ------------------------------------------------------------

def test_validate_frequency_accepts_known():
    for freq in ["Diaria", "Semanal", "Mensual"]:
        validate_frequency(freq)  # no debe lanzar


def test_validate_frequency_rejects_unknown():
    with pytest.raises(InvalidFrequency):
        validate_frequency("Quincenal")


# --- Rango de fechas --------------------------------------------------------

def test_validate_date_range_accepts_valid():
    validate_date_range(date(2024, 1, 1), date(2025, 1, 1), today=TODAY)


def test_validate_date_range_rejects_start_after_end():
    with pytest.raises(InvalidDateRange):
        validate_date_range(date(2025, 1, 1), date(2024, 1, 1), today=TODAY)


def test_validate_date_range_rejects_start_equal_end():
    with pytest.raises(InvalidDateRange):
        validate_date_range(date(2024, 1, 1), date(2024, 1, 1), today=TODAY)


def test_validate_date_range_rejects_future_end_date():
    with pytest.raises(InvalidDateRange):
        validate_date_range(date(2024, 1, 1), date(2027, 1, 1), today=TODAY)


# --- Horizonte en periodos ---------------------------------------------------

def test_validate_horizon_periods_accepts_valid():
    validate_horizon_periods(1)
    validate_horizon_periods(17)
    validate_horizon_periods(MAX_HORIZON_PERIODS)


@pytest.mark.parametrize("bad_h", [0, -1, -100])
def test_validate_horizon_periods_rejects_non_positive(bad_h):
    with pytest.raises(InvalidHorizon):
        validate_horizon_periods(bad_h)


def test_validate_horizon_periods_rejects_non_integer():
    with pytest.raises(InvalidHorizon):
        validate_horizon_periods(3.5)


def test_validate_horizon_periods_rejects_bool_disguised_as_int():
    # bool es subclase de int en Python — se rechaza explícitamente.
    with pytest.raises(InvalidHorizon):
        validate_horizon_periods(True)


def test_validate_horizon_periods_rejects_above_limit():
    with pytest.raises(InvalidHorizon):
        validate_horizon_periods(MAX_HORIZON_PERIODS + 1)


def test_validate_horizon_periods_does_not_silently_round():
    # No hay redondeo: un flotante entero-como 5.0 tampoco se acepta.
    with pytest.raises(InvalidHorizon):
        validate_horizon_periods(5.0)


# --- Conversión fecha objetivo -> periodos ------------------------------------

def test_convert_target_date_daily_counts_business_days_only():
    # Lunes 2026-09-14 -> Lunes 2026-09-21: 5 días hábiles (mar-vie + lun).
    h = convert_target_date_to_periods(date(2026, 9, 14), date(2026, 9, 21), "Diaria")
    assert h == 5


def test_convert_target_date_weekly_ceils_partial_weeks():
    # 10 días de diferencia -> ceil(10/7) = 2 semanas.
    h = convert_target_date_to_periods(date(2026, 1, 1), date(2026, 1, 11), "Semanal")
    assert h == 2


def test_convert_target_date_monthly_counts_calendar_months():
    h = convert_target_date_to_periods(date(2026, 1, 15), date(2026, 4, 15), "Mensual")
    assert h == 3


def test_convert_target_date_rejects_target_before_reference():
    with pytest.raises(InvalidHorizon):
        convert_target_date_to_periods(date(2026, 9, 14), date(2026, 9, 1), "Diaria")


def test_convert_target_date_rejects_target_equal_reference():
    with pytest.raises(InvalidHorizon):
        convert_target_date_to_periods(date(2026, 9, 14), date(2026, 9, 14), "Diaria")


def test_convert_target_date_enforces_max_horizon():
    # Una fecha objetivo muy lejana en frecuencia diaria debe superar
    # el límite operacional y ser rechazada, no truncada en silencio.
    with pytest.raises(InvalidHorizon):
        convert_target_date_to_periods(date(2020, 1, 1), date(2026, 1, 1), "Diaria")


# --- resolve_horizon (punto de entrada único) --------------------------------

def test_resolve_horizon_periods_mode():
    cfg = resolve_horizon("Diaria", date(2026, 9, 14), mode="periods", periods=17)
    assert cfg.periods == 17
    assert cfg.mode == "periods"
    assert cfg.target_date is None


def test_resolve_horizon_target_date_mode():
    cfg = resolve_horizon(
        "Mensual", date(2026, 1, 15), mode="target_date", target_date=date(2026, 4, 15)
    )
    assert cfg.periods == 3
    assert cfg.mode == "target_date"
    assert cfg.target_date == date(2026, 4, 15)


def test_resolve_horizon_requires_periods_in_periods_mode():
    with pytest.raises(InvalidHorizon):
        resolve_horizon("Diaria", date(2026, 9, 14), mode="periods")


def test_resolve_horizon_requires_target_date_in_target_date_mode():
    with pytest.raises(InvalidHorizon):
        resolve_horizon("Diaria", date(2026, 9, 14), mode="target_date")


def test_resolve_horizon_rejects_unknown_mode():
    with pytest.raises(InvalidHorizon):
        resolve_horizon("Diaria", date(2026, 9, 14), mode="algo_raro", periods=5)


def test_resolve_horizon_not_limited_to_preset_buttons():
    # Punto 69: cualquier entero positivo dentro del límite debe
    # aceptarse, no solo valores "predefinidos" como 1, 5, 17.
    for h in [1, 2, 3, 4, 6, 7, 8, 9, 10, 100, 200, 252]:
        cfg = resolve_horizon("Diaria", date(2026, 9, 14), mode="periods", periods=h)
        assert cfg.periods == h
