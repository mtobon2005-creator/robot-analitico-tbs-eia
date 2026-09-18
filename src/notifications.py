"""Outbox de notificaciones (RF-02 punto 10, sección 7.3 punto 66-67).

`enqueue_session_started` se llama DENTRO de la misma transacción
atómica que crea la sesión y el auth_event (ver src/auth.py). El
UNIQUE(session_id, type) en BD impide más de una intención
'session_started' por sesión aunque se reintente la escritura.
"""
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_session_started(
    conn: sqlite3.Connection,
    event_id: str,
    session_id: str,
    destination_alias: str,
) -> str:
    outbox_id = str(uuid4())
    now = _now_iso()
    conn.execute(
        "INSERT INTO notification_outbox "
        "(outbox_id, event_id, session_id, type, destination_alias, status, "
        " attempt_count, next_attempt_at, error, sent_at, purge_at) "
        "VALUES (?, ?, ?, 'session_started', ?, 'pending', 0, ?, NULL, NULL, NULL)",
        (outbox_id, event_id, session_id, destination_alias, now),
    )
    return outbox_id
