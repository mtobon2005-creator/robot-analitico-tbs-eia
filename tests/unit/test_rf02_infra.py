"""Pruebas unitarias RF-02: preconsentimiento, sesión, outbox.

Usan una BD SQLite en memoria por prueba (sin depender de OIDC real).
"""
import time
from datetime import datetime, timedelta, timezone

import pytest

from src import consent, sessions
from src.db import get_connection, init_schema
from src.notifications import enqueue_session_started
from src.notifications_worker import LocalFileSink, process_pending_notifications


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    connection = get_connection()
    init_schema(connection)
    yield connection
    connection.close()


# --- Preconsentimiento --------------------------------------------------

def test_issue_and_consume_preconsent_flow_succeeds_once(conn):
    flow_id = consent.issue_preconsent_flow(conn, "1.0", "1.0")
    result = consent.consume_preconsent_flow(conn, flow_id)
    assert result["disclaimer_version"] == "1.0"
    assert result["privacy_version"] == "1.0"


def test_consume_preconsent_flow_rejects_reuse(conn):
    flow_id = consent.issue_preconsent_flow(conn, "1.0", "1.0")
    consent.consume_preconsent_flow(conn, flow_id)
    with pytest.raises(consent.PreconsentInvalid):
        consent.consume_preconsent_flow(conn, flow_id)


def test_consume_preconsent_flow_rejects_missing(conn):
    with pytest.raises(consent.PreconsentInvalid):
        consent.consume_preconsent_flow(conn, None)


def test_consume_preconsent_flow_rejects_unknown(conn):
    with pytest.raises(consent.PreconsentInvalid):
        consent.consume_preconsent_flow(conn, "esto-no-existe")


def test_consume_preconsent_flow_rejects_expired(conn, monkeypatch):
    flow_id = consent.issue_preconsent_flow(conn, "1.0", "1.0")
    # Forzar expiración retrocediendo expires_at manualmente.
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    conn.execute(
        "UPDATE preconsent_flows SET expires_at = ? WHERE flow_id_hash = "
        "(SELECT flow_id_hash FROM preconsent_flows LIMIT 1)",
        (past,),
    )
    with pytest.raises(consent.PreconsentInvalid):
        consent.consume_preconsent_flow(conn, flow_id)


# --- Sesión lógica --------------------------------------------------------

def _make_profile(conn, user_id="u1", issuer="https://accounts.google.com", subject="sub-1"):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO profiles (user_id, issuer, subject, provider, display_name, "
        "email, first_seen_at, last_seen_at, purge_at) VALUES (?,?,?,?,?,?,?,?,NULL)",
        (user_id, issuer, subject, "google", "Ana Test", "ana@example.com", now, now),
    )


def test_create_session_and_touch_keeps_it_active(conn):
    _make_profile(conn)
    session_id = sessions.create_session(conn, "u1", idp_iat=None)
    sessions.touch_session(conn, session_id)  # no debe lanzar


def test_touch_session_not_found_raises(conn):
    with pytest.raises(sessions.SessionNotFound):
        sessions.touch_session(conn, "no-existe")


def test_only_one_active_session_per_user(conn):
    _make_profile(conn)
    sessions.create_session(conn, "u1", idp_iat=None)
    with pytest.raises(Exception):  # UNIQUE index violation esperado
        sessions.create_session(conn, "u1", idp_iat=None)


def test_touch_session_expires_after_inactivity(conn, monkeypatch):
    _make_profile(conn)
    session_id = sessions.create_session(conn, "u1", idp_iat=None)
    # Forzar last_seen_at 31 minutos atrás.
    stale = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
    conn.execute(
        "UPDATE app_sessions SET last_seen_at = ? WHERE session_id = ?",
        (stale, session_id),
    )
    with pytest.raises(sessions.SessionExpired):
        sessions.touch_session(conn, session_id)

    row = conn.execute(
        "SELECT status FROM app_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    assert row["status"] == "closed"


def test_close_session_marks_closed(conn):
    _make_profile(conn)
    session_id = sessions.create_session(conn, "u1", idp_iat=None)
    sessions.close_session(conn, session_id)
    row = conn.execute(
        "SELECT status, closed_at FROM app_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    assert row["status"] == "closed"
    assert row["closed_at"] is not None


# --- Outbox de notificaciones ---------------------------------------------

def test_enqueue_creates_pending_row_and_worker_sends_it(conn, tmp_path):
    _make_profile(conn)
    session_id = sessions.create_session(conn, "u1", idp_iat=None)
    conn.execute(
        "INSERT INTO auth_events (event_id, user_id, session_id, event_type, "
        "result, occurred_at, app_version, purge_at) VALUES "
        "('ev1','u1',?,'session_started','success',?,'0.1.0',NULL)",
        (session_id, datetime.now(timezone.utc).isoformat()),
    )
    enqueue_session_started(conn, "ev1", session_id, "curso@example.com")

    sink = LocalFileSink(path=tmp_path / "sink.jsonl")
    result = process_pending_notifications(conn, sink)
    assert result == {"sent": 1, "failed": 0, "retried": 0}

    row = conn.execute(
        "SELECT status FROM notification_outbox WHERE event_id = 'ev1'"
    ).fetchone()
    assert row["status"] == "sent"


def test_worker_fails_after_three_attempts(conn, tmp_path):
    _make_profile(conn)
    session_id = sessions.create_session(conn, "u1", idp_iat=None)
    conn.execute(
        "INSERT INTO auth_events (event_id, user_id, session_id, event_type, "
        "result, occurred_at, app_version, purge_at) VALUES "
        "('ev2','u1',?,'session_started','success',?,'0.1.0',NULL)",
        (session_id, datetime.now(timezone.utc).isoformat()),
    )
    enqueue_session_started(conn, "ev2", session_id, "curso@example.com")

    class AlwaysFailSink:
        def send(self, event_id, payload):
            return False

    sink = AlwaysFailSink()
    for _ in range(3):
        process_pending_notifications(conn, sink)
        # Forzar next_attempt_at al pasado para el siguiente intento inmediato.
        conn.execute(
            "UPDATE notification_outbox SET next_attempt_at = ? WHERE event_id = 'ev2'",
            ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),),
        )

    row = conn.execute(
        "SELECT status, attempt_count FROM notification_outbox WHERE event_id = 'ev2'"
    ).fetchone()
    assert row["status"] == "failed"
    assert row["attempt_count"] == 3
