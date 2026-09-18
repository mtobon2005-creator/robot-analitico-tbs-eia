"""Pruebas del ciclo de vida (RNF-03): revocación, purga programada,
worker periódico, reaplicación tras restaurar un respaldo (T-23)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from src.db import get_connection, init_schema
from src.lifecycle import (
    MissingLifecycleSecret,
    compute_purge_at,
    create_deletion_marker,
    reapply_purge_after_restore,
    revoke_user_immediately,
    run_lifecycle_purge,
    schedule_purge_for_all,
)


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LIFECYCLE_HMAC_SECRET", "test-secret-not-for-production")
    connection = get_connection()
    init_schema(connection)
    yield connection
    connection.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_full_user(conn, user_id="u1", issuer="https://accounts.google.com", subject="sub-1"):
    """Crea un perfil + sesión + evento + outbox completos para probar
    la purga en cascada."""
    now = _now_iso()
    conn.execute(
        "INSERT INTO preconsent_flows (flow_id_hash, disclaimer_version, "
        "privacy_version, accepted_at, expires_at, consumed_at) VALUES "
        "(?, '1.0', '1.0', ?, ?, ?)",
        (f"fake-hash-{user_id}", now, now, now),
    )
    conn.execute(
        "INSERT INTO profiles (user_id, issuer, subject, provider, display_name, "
        "email, first_seen_at, last_seen_at, purge_at) VALUES (?,?,?,?,?,?,?,?,NULL)",
        (user_id, issuer, subject, "google", "Ana Test", "ana@example.com", now, now),
    )
    conn.execute(
        "INSERT INTO app_sessions (session_id, user_id, idp_iat, created_at, "
        "last_seen_at, absolute_expires_at, status, closed_at) VALUES "
        "(?, ?, NULL, ?, ?, ?, 'active', NULL)",
        (f"s-{user_id}", user_id, now, now, now),
    )
    conn.execute(
        "INSERT INTO auth_events (event_id, user_id, session_id, event_type, "
        "result, occurred_at, app_version, purge_at) VALUES "
        "(?, ?, ?, 'session_started', 'success', ?, '0.1.0', NULL)",
        (f"e-{user_id}", user_id, f"s-{user_id}", now),
    )
    conn.execute(
        "INSERT INTO notification_outbox (outbox_id, event_id, session_id, type, "
        "destination_alias, status, attempt_count, next_attempt_at, error, sent_at, purge_at) "
        "VALUES (?, ?, ?, 'session_started', 'curso@example.com', 'sent', 1, ?, NULL, ?, NULL)",
        (f"o-{user_id}", f"e-{user_id}", f"s-{user_id}", now, now),
    )
    conn.execute(
        "INSERT INTO consent_events (consent_id, user_id, kind, version, status, "
        "occurred_at, method, preconsent_id) VALUES "
        "(?, ?, 'disclaimer', '1.0', 'accepted', ?, 'checkbox_explicit', ?)",
        (f"c-{user_id}", user_id, now, f"fake-hash-{user_id}"),
    )


# --- compute_purge_at --------------------------------------------------------

def test_compute_purge_at_defaults_to_grading_plus_90_days():
    firmeza = date(2026, 1, 1)
    purge_at = compute_purge_at(firmeza)
    assert purge_at == datetime(2026, 4, 1, tzinfo=timezone.utc)


def test_compute_purge_at_uses_earlier_of_request_and_grading_deadline():
    firmeza = date(2026, 1, 1)  # deadline = 2026-04-01
    early_request = datetime(2026, 2, 1, tzinfo=timezone.utc)
    assert compute_purge_at(firmeza, early_request) == early_request


def test_compute_purge_at_ignores_late_request_uses_grading_deadline():
    firmeza = date(2026, 1, 1)  # deadline = 2026-04-01
    late_request = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert compute_purge_at(firmeza, late_request) == datetime(2026, 4, 1, tzinfo=timezone.utc)


# --- deletion markers: sin PII ------------------------------------------------

def test_create_deletion_marker_never_stores_raw_subject_id(conn):
    marker = create_deletion_marker(conn, subject_id="sub-super-secreto-123", reason="test")
    assert "sub-super-secreto-123" not in marker  # es un hash, no el valor crudo
    assert len(marker) == 64  # sha256 hex digest


def test_create_deletion_marker_requires_hmac_secret(conn, monkeypatch):
    monkeypatch.delenv("LIFECYCLE_HMAC_SECRET", raising=False)
    with pytest.raises(MissingLifecycleSecret):
        create_deletion_marker(conn, "sub-1", "test")


# --- revocación inmediata -----------------------------------------------------

def test_revoke_user_immediately_purges_all_identifiable_rows(conn):
    _make_full_user(conn)
    result = revoke_user_immediately(conn, "u1", reason="usuario solicitó eliminación")

    assert result.deleted_counts["profiles"] == 1
    assert result.deleted_counts["app_sessions"] == 1
    assert result.deleted_counts["auth_events"] == 1
    assert result.deleted_counts["notification_outbox"] == 1

    for table in ["profiles", "app_sessions", "auth_events", "notification_outbox", "consent_events"]:
        count = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
        assert count == 0, f"{table} debería estar vacío tras la revocación"


def test_revoke_user_immediately_creates_deletion_marker(conn):
    _make_full_user(conn)
    result = revoke_user_immediately(conn, "u1", reason="revocación de prueba")
    marker = conn.execute(
        "SELECT * FROM deletion_markers WHERE marker_hmac = ?", (result.marker_hmac,)
    ).fetchone()
    assert marker is not None
    assert marker["status"] == "active"


def test_revoke_user_immediately_does_not_affect_other_users(conn):
    _make_full_user(conn, user_id="u1", subject="sub-1")
    _make_full_user(conn, user_id="u2", subject="sub-2")
    revoke_user_immediately(conn, "u1", reason="test")
    remaining = conn.execute("SELECT COUNT(*) AS c FROM profiles").fetchone()["c"]
    assert remaining == 1  # u2 sigue existiendo


# --- purga programada al cierre -----------------------------------------------

def test_schedule_purge_for_all_sets_purge_at_on_profiles(conn):
    _make_full_user(conn)
    updated = schedule_purge_for_all(conn, firmeza_calificacion=date(2026, 1, 1))
    assert updated == 1
    row = conn.execute("SELECT purge_at FROM profiles WHERE user_id='u1'").fetchone()
    assert row["purge_at"] is not None


def test_schedule_purge_for_all_does_not_overwrite_earlier_purge_at(conn):
    _make_full_user(conn)
    early = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    conn.execute("UPDATE profiles SET purge_at = ? WHERE user_id='u1'", (early,))
    far_future_firmeza = (date.today() + timedelta(days=365))  # deadline muy lejano
    schedule_purge_for_all(conn, firmeza_calificacion=far_future_firmeza)
    row = conn.execute("SELECT purge_at FROM profiles WHERE user_id='u1'").fetchone()
    assert row["purge_at"] == early  # no se sobrescribe con una fecha más lejana


# --- worker periódico ---------------------------------------------------------

def test_run_lifecycle_purge_deletes_expired_unconsumed_flows(conn):
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    conn.execute(
        "INSERT INTO preconsent_flows (flow_id_hash, disclaimer_version, "
        "privacy_version, accepted_at, expires_at, consumed_at) VALUES "
        "('hash1', '1.0', '1.0', ?, ?, NULL)",
        (past, past),
    )
    result = run_lifecycle_purge(conn)
    assert result.expired_flows_deleted == 1
    remaining = conn.execute("SELECT COUNT(*) AS c FROM preconsent_flows").fetchone()["c"]
    assert remaining == 0


def test_run_lifecycle_purge_keeps_unexpired_flows(conn):
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    conn.execute(
        "INSERT INTO preconsent_flows (flow_id_hash, disclaimer_version, "
        "privacy_version, accepted_at, expires_at, consumed_at) VALUES "
        "('hash2', '1.0', '1.0', ?, ?, NULL)",
        (future, future),
    )
    run_lifecycle_purge(conn)
    remaining = conn.execute("SELECT COUNT(*) AS c FROM preconsent_flows").fetchone()["c"]
    assert remaining == 1  # no vencido -> se conserva


def test_run_lifecycle_purge_cascades_profiles_past_purge_at(conn):
    _make_full_user(conn)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn.execute("UPDATE profiles SET purge_at = ? WHERE user_id='u1'", (past,))

    result = run_lifecycle_purge(conn)

    assert result.profiles_purged == 1
    assert conn.execute("SELECT COUNT(*) AS c FROM profiles").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) AS c FROM app_sessions").fetchone()["c"] == 0


def test_run_lifecycle_purge_records_lifecycle_job_without_identifiers(conn):
    _make_full_user(conn)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn.execute("UPDATE profiles SET purge_at = ? WHERE user_id='u1'", (past,))
    run_lifecycle_purge(conn)

    job = conn.execute("SELECT * FROM lifecycle_jobs").fetchone()
    assert job is not None
    assert job["status"] == "completed"
    assert "u1" not in job["deleted_counts"]  # solo conteos, sin identificadores


def test_run_lifecycle_purge_expires_due_deletion_markers(conn, monkeypatch):
    monkeypatch.setenv("LIFECYCLE_HMAC_SECRET", "test-secret")
    marker = create_deletion_marker(conn, "sub-x", "test")
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn.execute("UPDATE deletion_markers SET expires_at = ? WHERE marker_hmac = ?", (past, marker))

    result = run_lifecycle_purge(conn)

    assert result.markers_expired == 1
    row = conn.execute(
        "SELECT status FROM deletion_markers WHERE marker_hmac = ?", (marker,)
    ).fetchone()
    assert row["status"] == "expired"


# --- reaplicación tras restaurar un respaldo (T-23) --------------------------

def test_reapply_purge_after_restore_removes_resurrected_profile(conn):
    # Simula: el usuario fue purgado, pero un respaldo restaurado
    # "resucita" su perfil con un purge_at ya vencido.
    _make_full_user(conn)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn.execute("UPDATE profiles SET purge_at = ? WHERE user_id='u1'", (past,))

    result = reapply_purge_after_restore(conn)

    assert result.profiles_purged == 1
    assert conn.execute("SELECT COUNT(*) AS c FROM profiles").fetchone()["c"] == 0


def test_reapply_purge_after_restore_touches_last_reapplied_at(conn):
    create_deletion_marker(conn, "sub-y", "test")
    reapply_purge_after_restore(conn)
    row = conn.execute("SELECT last_reapplied_at FROM deletion_markers").fetchone()
    assert row["last_reapplied_at"] is not None
