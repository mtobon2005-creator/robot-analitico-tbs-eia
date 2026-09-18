"""Integración RF-02: flujo completo de complete_login().

Simula claims OIDC (sin red real) para probar lo que exige T-18:
sin preconsentimiento no hay filas persistentes; con todo correcto,
perfil+consentimientos+sesión+evento+outbox quedan atómicos.
"""
import pytest

from src import auth, consent
from src.db import get_connection, init_schema


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    connection = get_connection()
    init_schema(connection)
    yield connection
    connection.close()


VALID_CLAIMS = {
    "iss": "https://accounts.google.com",
    "sub": "sub-abc-123",
    "name": "Ana Test",
    "email": "cuenta.prueba1@gmail.com",
    "email_verified": True,
    "iat": "1700000000",
}


def _allowlist(monkeypatch, emails):
    monkeypatch.setattr(auth, "ALLOWLISTED_TEST_EMAILS", set(emails))


def _row_counts(conn) -> dict:
    tables = [
        "profiles",
        "consent_events",
        "app_sessions",
        "auth_events",
        "notification_outbox",
    ]
    return {t: conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"] for t in tables}


def test_complete_login_happy_path_persists_everything_atomically(conn, monkeypatch):
    _allowlist(monkeypatch, [VALID_CLAIMS["email"]])
    flow_id = consent.issue_preconsent_flow(conn, "1.0", "1.0")

    result = auth.complete_login(conn, VALID_CLAIMS, "google", flow_id)

    assert result["user_id"]
    assert result["session_id"]
    counts = _row_counts(conn)
    assert counts["profiles"] == 1
    assert counts["consent_events"] == 2  # privacy + disclaimer
    assert counts["app_sessions"] == 1
    assert counts["auth_events"] == 1
    assert counts["notification_outbox"] == 1


def test_complete_login_without_flow_persists_nothing(conn, monkeypatch):
    _allowlist(monkeypatch, [VALID_CLAIMS["email"]])
    with pytest.raises(consent.PreconsentInvalid):
        auth.complete_login(conn, VALID_CLAIMS, "google", flow_id=None)

    counts = _row_counts(conn)
    assert all(c == 0 for c in counts.values())


def test_complete_login_rejects_incomplete_identity_and_persists_nothing(conn, monkeypatch):
    _allowlist(monkeypatch, [VALID_CLAIMS["email"]])
    flow_id = consent.issue_preconsent_flow(conn, "1.0", "1.0")
    bad_claims = {**VALID_CLAIMS, "name": ""}

    with pytest.raises(auth.IdentityIncomplete):
        auth.complete_login(conn, bad_claims, "google", flow_id)

    counts = _row_counts(conn)
    assert counts["profiles"] == 0
    assert counts["app_sessions"] == 0


def test_complete_login_rejects_non_allowlisted_account(conn, monkeypatch):
    _allowlist(monkeypatch, ["otra-cuenta@example.com"])
    flow_id = consent.issue_preconsent_flow(conn, "1.0", "1.0")

    with pytest.raises(auth.NotAuthorized):
        auth.complete_login(conn, VALID_CLAIMS, "google", flow_id)

    counts = _row_counts(conn)
    assert all(c == 0 for c in counts.values())


def test_complete_login_second_time_reuses_profile_not_creates_new(conn, monkeypatch):
    _allowlist(monkeypatch, [VALID_CLAIMS["email"]])

    flow_id_1 = consent.issue_preconsent_flow(conn, "1.0", "1.0")
    result_1 = auth.complete_login(conn, VALID_CLAIMS, "google", flow_id_1)

    # Cerrar la primera sesión para poder abrir una segunda (única activa por usuario).
    from src import sessions

    sessions.close_session(conn, result_1["session_id"])

    flow_id_2 = consent.issue_preconsent_flow(conn, "1.0", "1.0")
    result_2 = auth.complete_login(conn, VALID_CLAIMS, "google", flow_id_2)

    assert result_1["user_id"] == result_2["user_id"]  # mismo (iss, sub) -> mismo perfil
    assert result_1["session_id"] != result_2["session_id"]
    assert _row_counts(conn)["profiles"] == 1
