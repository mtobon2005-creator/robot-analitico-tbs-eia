"""Eventos de auditoría (auth_events). Inmutables durante la retención
(sección 7.3, punto 66): este módulo deliberadamente no ofrece
funciones de update/delete. La purga real la hará lifecycle_worker
(módulo futuro, sección 7.5 RNF-03) al vencer purge_at.
"""
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_auth_event(
    conn: sqlite3.Connection,
    user_id: str,
    session_id: str,
    event_type: str,
    result: str,
    app_version: str,
    purge_at: str | None = None,
) -> str:
    event_id = str(uuid4())
    conn.execute(
        "INSERT INTO auth_events "
        "(event_id, user_id, session_id, event_type, result, occurred_at, app_version, purge_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, user_id, session_id, event_type, result, _now_iso(), app_version, purge_at),
    )
    return event_id
