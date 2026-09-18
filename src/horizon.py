"""RF-04: fechas, frecuencia y horizonte de pronóstico H.

Lógica pura (sin Streamlit), testeable con pytest. H puede definirse
como (a) una cantidad entera positiva de periodos, o (b) una fecha
objetivo que este módulo convierte a periodos en la frecuencia
elegida — nunca limitado a una lista fija de botones (punto 69).

LIMITACIÓN CONOCIDA: la conversión fecha objetivo -> periodos que se
hace aquí es una aproximación CALENDARIO (días hábiles para diaria,
semanas y meses de calendario para semanal/mensual). La sección 5.5 de
la guía exige contar "periodos negociables o remuestreados" — es
decir, el conteo final y exacto solo puede hacerse una vez existan
datos reales descargados (RF-05 a RF-08), porque depende de qué
fechas quedaron en la serie después del remuestreo (fines de semana y
festivos no son observaciones ficticias). Este módulo da la mejor
estimación disponible en el momento de la configuración; RF-14
deberá recalcular el H efectivo contra el índice real de fechas.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from src.config import FRECUENCIAS, MAX_HORIZON_PERIODS

MIN_HORIZON_PERIODS = 1


class InvalidDateRange(ValueError):
    pass


class InvalidHorizon(ValueError):
    pass


class InvalidFrequency(ValueError):
    pass


def validate_frequency(frequency: str) -> None:
    if frequency not in FRECUENCIAS:
        raise InvalidFrequency(
            f"Frecuencia '{frequency}' no soportada. Usa una de: "
            f"{', '.join(FRECUENCIAS)}."
        )


def validate_date_range(start: date, end: date, today: date | None = None) -> None:
    """`today` es inyectable para pruebas deterministas; en producción
    se usa la fecha real del sistema."""
    today = today or date.today()
    if start >= end:
        raise InvalidDateRange("La fecha inicial debe ser anterior a la fecha final.")
    if end > today:
        raise InvalidDateRange("La fecha final no puede ser posterior a hoy.")


def validate_horizon_periods(h: int) -> None:
    """Punto 69: rechazar vacío, cero, negativos, no enteros o valores
    superiores al límite operacional, SIN redondeo silencioso."""
    if not isinstance(h, int) or isinstance(h, bool):
        raise InvalidHorizon("El horizonte H debe ser un número entero.")
    if h < MIN_HORIZON_PERIODS:
        raise InvalidHorizon("El horizonte H debe ser un entero positivo (≥ 1).")
    if h > MAX_HORIZON_PERIODS:
        raise InvalidHorizon(
            f"El horizonte H no puede superar el límite operacional "
            f"({MAX_HORIZON_PERIODS} periodos)."
        )


def _business_days_between(start: date, end: date) -> int:
    """Días hábiles (lun-vie) estrictamente después de `start` hasta
    `end` inclusive. Aproximación calendario, no trading calendar real."""
    if end <= start:
        return 0
    count = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:  # 0=lunes ... 4=viernes
            count += 1
        current += timedelta(days=1)
    return count


def _calendar_months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day > start.day:
        months += 1
    return max(0, months)


def convert_target_date_to_periods(
    reference_date: date, target_date: date, frequency: str
) -> int:
    """Convierte una fecha objetivo a cantidad de periodos H en la
    frecuencia elegida, tomando `reference_date` (normalmente la
    última fecha con dato disponible) como origen."""
    validate_frequency(frequency)
    if target_date <= reference_date:
        raise InvalidHorizon(
            "La fecha objetivo debe ser posterior a la fecha de referencia "
            "(último dato disponible)."
        )

    if frequency == "Diaria":
        h = _business_days_between(reference_date, target_date)
    elif frequency == "Semanal":
        delta_days = (target_date - reference_date).days
        h = -(-delta_days // 7)  # ceil division
    elif frequency == "Mensual":
        h = _calendar_months_between(reference_date, target_date)
    else:  # pragma: no cover — validate_frequency ya lo cubre
        raise InvalidFrequency(frequency)

    validate_horizon_periods(h)
    return h


@dataclass(frozen=True)
class HorizonConfig:
    mode: str  # "periods" | "target_date"
    frequency: str
    periods: int  # siempre resuelto a un entero, sin importar el modo de entrada
    target_date: date | None  # solo informativo si mode == "target_date"


def resolve_horizon(
    frequency: str,
    reference_date: date,
    mode: str,
    periods: int | None = None,
    target_date: date | None = None,
) -> HorizonConfig:
    """Punto de entrada único para RF-04: valida y devuelve un
    HorizonConfig con H ya resuelto a periodos enteros."""
    validate_frequency(frequency)

    if mode == "periods":
        if periods is None:
            raise InvalidHorizon("Debes indicar la cantidad de periodos.")
        validate_horizon_periods(periods)
        return HorizonConfig(mode=mode, frequency=frequency, periods=periods, target_date=None)

    if mode == "target_date":
        if target_date is None:
            raise InvalidHorizon("Debes indicar la fecha objetivo.")
        h = convert_target_date_to_periods(reference_date, target_date, frequency)
        return HorizonConfig(
            mode=mode, frequency=frequency, periods=h, target_date=target_date
        )

    raise InvalidHorizon(f"Modo de horizonte desconocido: '{mode}'.")
