"""RF-03: colección dinámica de tickers.

Lógica pura (sin Streamlit) para poder probarla con pytest sin
levantar la app. La UI en app.py solo llama a estas funciones y
guarda la lista resultante en st.session_state.

Alcance de RF-03: la COLECCIÓN (agregar, eliminar, deduplicar,
validar formato). La descarga y validación real contra el proveedor
de datos (ticker inexistente, respuesta vacía, timeout) es RF-05 a
RF-08 — todavía no implementado.
"""
import re

from src.config import N_MIN_ACTIVOS

# Formato permisivo: letras, números, punto, guion o guion bajo, 1 a 20
# caracteres. Debe cubrir el ticker oficial de prueba EIA_INVALID_2026
# (T-06, fallo parcial) además de casos reales como AAPL, BRK.B, TD.TO.
_TICKER_PATTERN = re.compile(r"^[A-Z0-9._-]{1,20}$")


class InvalidTicker(ValueError):
    pass


class DuplicateTicker(ValueError):
    pass


class TickerNotFound(ValueError):
    pass


def normalize_ticker(raw: str) -> str:
    return raw.strip().upper()


def validate_ticker_format(ticker: str) -> None:
    if not ticker:
        raise InvalidTicker("El ticker no puede estar vacío.")
    if not _TICKER_PATTERN.match(ticker):
        raise InvalidTicker(
            f"'{ticker}' no tiene un formato válido (letras, números, "
            "punto, guion o guion bajo, máx. 20 caracteres)."
        )


def add_ticker(collection: list[str], raw_ticker: str) -> list[str]:
    """Devuelve una NUEVA lista con el ticker agregado (no muta en sitio,
    para que sea fácil de usar desde st.session_state)."""
    ticker = normalize_ticker(raw_ticker)
    validate_ticker_format(ticker)
    if ticker in collection:
        raise DuplicateTicker(f"'{ticker}' ya está en la colección.")
    return [*collection, ticker]


def remove_ticker(collection: list[str], ticker: str) -> list[str]:
    ticker = normalize_ticker(ticker)
    if ticker not in collection:
        raise TickerNotFound(f"'{ticker}' no está en la colección.")
    return [t for t in collection if t != ticker]


def is_ready_for_single_asset(collection: list[str]) -> bool:
    """RF-03: 'el sistema deberá analizar un solo activo...'"""
    return len(collection) == 1


def is_ready_for_comparison(collection: list[str], minimum: int = N_MIN_ACTIVOS) -> bool:
    """RF-03/RF-19: comparación simultánea de al menos `minimum` activos
    ÚNICOS. `collection` puede tener más de `minimum` (RF-03 lo permite
    explícitamente: 'podrá admitir más de 20')."""
    return len(set(collection)) >= minimum


def missing_for_comparison(collection: list[str], minimum: int = N_MIN_ACTIVOS) -> int:
    """Cuántos activos válidos faltan para alcanzar el mínimo (para
    mostrarle al usuario un mensaje útil, ej. 'faltan 7 activos')."""
    return max(0, minimum - len(set(collection)))
