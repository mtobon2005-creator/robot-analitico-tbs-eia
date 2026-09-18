"""Capa de persistencia (SQLite) para RF-02 y siguientes.

Todas las escrituras que RF-02 exige como atómicas (perfil +
consentimientos + sesión + evento + outbox) deben pasar por
`transaction()`, que hace BEGIN IMMEDIATE / COMMIT / ROLLBACK real.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "migrations" / "001_init.sql"


def get_db_path() -> Path:
    """Resuelve la ruta de la BD en cada llamada (no al importar el módulo),
    para que los tests puedan sobreescribir APP_DB_PATH de forma aislada."""
    return Path(os.environ.get("APP_DB_PATH", "data/app.db"))


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        db_path, isolation_level=None, check_same_thread=False
    )  # autocommit off, control manual; check_same_thread=False porque
       # Streamlit puede ejecutar reruns en hilos distintos y la
       # conexión se comparte vía st.cache_resource (mismo proceso,
       # sin concurrencia real de escritura simultánea en este piloto).
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_schema(conn: sqlite3.Connection | None = None) -> None:
    own_conn = conn is None
    conn = conn or get_connection()
    try:
        conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    finally:
        if own_conn:
            conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Transacción atómica real: todo o nada.

    Uso:
        with transaction(conn) as cur:
            cur.execute(...)
            cur.execute(...)
    Si cualquier excepción ocurre dentro del bloque, se hace ROLLBACK
    completo y no queda ninguna fila nueva ni mutación parcial
    (requisito de RF-02 / prueba T-22).
    """
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE;")
    try:
        yield cur
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
