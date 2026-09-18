"""Sesión lógica del servidor (RF-02, sección 7.3, puntos 64-65).

Reglas:
- Una única sesión 'active' por user_id (impuesto por índice único en BD).
- Expira a los 30 minutos de inactividad O a las 8 horas desde created_at,
  lo que ocurra primero.
- Cada rerun protegido debe llamar a `touch_session` para actualizar
  last_seen_at; si la sesión expiró, `guard` la cierra y bloquea.
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

INACTIVITY_TIMEOUT_MINUTES = 30
ABSOLUTE_TIMEOUT_HOURS = 8


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def create_session(conn: sqlite3.Connection, user_id: str, idp_iat: str | None) -> str:
    """Crea la sesión lógica. Debe llamarse dentro de la misma transacción
    atómica que crea/actualiza el perfil y registra los consentimientos
    (ver src/auth.py: complete_login).

    Cierra primero cualquier sesión 'active' huérfana del mismo usuario
    (ej. de un reinicio previo del servidor que dejó la fila activa en
    BD sin que nadie hiciera logout formal) — un nuevo login siempre
    reemplaza a cualquier sesión anterior, nunca falla por la
    restricción de unicidad."""
    now = _now()
    conn.execute(
        "UPDATE app_sessions SET status = 'closed', closed_at = ? "
        "WHERE user_id = ? AND status = 'active'",
        (_iso(now), user_id),
    )

    session_id = str(uuid4())
    conn.execute(
        "INSERT INTO app_sessions "
        "(session_id, user_id, idp_iat, created_at, last_seen_at, absolute_expires_at, status, closed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'active', NULL)",
        (
            session_id,
            user_id,
            idp_iat,
            _iso(now),
            _iso(now),
            _iso(now + timedelta(hours=ABSOLUTE_TIMEOUT_HOURS)),
        ),
    )
    return session_id


class SessionExpired(Exception):
    pass


class SessionNotFound(Exception):
    pass


def touch_session(conn: sqlite3.Connection, session_id: str) -> None:
    """Actualiza last_seen_at si la sesión sigue viva; si no, la cierra
    y lanza SessionExpired. Debe llamarse en cada rerun protegido
    (punto 64: 'cada rerun protegido consultará el estado y actualizará
    last_seen_at')."""
    row = conn.execute(
        "SELECT status, last_seen_at, absolute_expires_at FROM app_sessions "
        "WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        raise SessionNotFound(session_id)

    now = _now()
    if row["status"] != "active":
        raise SessionExpired("sesión ya cerrada")

    inactivity_deadline = datetime.fromisoformat(row["last_seen_at"]) + timedelta(
        minutes=INACTIVITY_TIMEOUT_MINUTES
    )
    absolute_deadline = datetime.fromisoformat(row["absolute_expires_at"])

    if now > inactivity_deadline or now > absolute_deadline:
        conn.execute(
            "UPDATE app_sessions SET status = 'closed', closed_at = ? WHERE session_id = ?",
            (_iso(now), session_id),
        )
        raise SessionExpired("inactividad u 8 horas superadas")

    conn.execute(
        "UPDATE app_sessions SET last_seen_at = ? WHERE session_id = ?",
        (_iso(now), session_id),
    )


def close_session(conn: sqlite3.Connection, session_id: str) -> None:
    """Logout local: marca la sesión como cerrada. No promete cerrar la
    sesión global del proveedor (punto 65)."""
    conn.execute(
        "UPDATE app_sessions SET status = 'closed', closed_at = ? "
        "WHERE session_id = ? AND status = 'active'",
        (_iso(_now()), session_id),
    )
