"""Autenticación OIDC (Google/Microsoft) y orquestación del login (RF-02).

No reimplementa criptografía ni el protocolo OIDC: eso lo resuelve
`st.login()` / `st.user` de Streamlit (Authlib por debajo), como exige
el punto 63 de la guía. Este módulo se encarga de todo lo que va
DESPUÉS del callback: validar el preconsentimiento, la identidad
mínima, la allowlist, y persistir perfil/consentimientos/sesión/evento/
notificación en una sola transacción atómica.
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src import audit, consent, notifications, sessions
from src.config import APP_IDENTITY

APP_VERSION = APP_IDENTITY.version

# --- Allowlist de cuentas de prueba (punto 63) ---------------------------
# NOTA: la identidad persistida SIEMPRE es (issuer, subject) — nunca el
# correo (punto 62). El correo aquí solo sirve como criterio de admisión
# en el primer login, porque (issuer, subject) no se conoce hasta que el
# usuario ya se autenticó. EDITAR con las cuentas ficticias reales del
# curso antes de desplegar.
ALLOWLISTED_TEST_EMAILS: set[str] = {
     "mtobon2005@gmail.com",
    # "cuenta.prueba2@outlook.com",
}


class IdentityIncomplete(Exception):
    pass


class NotAuthorized(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_identity(claims: dict) -> None:
    """Punto 62: rechazo si nombre o correo faltan o no son utilizables.
    `preferred_username` no se asume como correo verificado."""
    name = (claims.get("name") or "").strip()
    email = (claims.get("email") or "").strip()
    email_verified = claims.get("email_verified", True)  # algunos IdP no lo exponen
    if not name or not email or not email_verified:
        raise IdentityIncomplete("identity_incomplete: falta nombre o correo verificado")
    if not claims.get("iss") or not claims.get("sub"):
        raise IdentityIncomplete("identity_incomplete: falta (iss, sub)")


def check_allowlist(claims: dict) -> None:
    email = (claims.get("email") or "").strip().lower()
    if email not in {e.lower() for e in ALLOWLISTED_TEST_EMAILS}:
        raise NotAuthorized(f"cuenta no autorizada: {email or '(sin correo)'}")


def upsert_profile(conn: sqlite3.Connection, claims: dict, provider: str) -> str:
    """Crea o actualiza el perfil, identificado por UNIQUE(issuer, subject)."""
    issuer, subject = claims["iss"], claims["sub"]
    now = _now_iso()
    existing = conn.execute(
        "SELECT user_id FROM profiles WHERE issuer = ? AND subject = ?",
        (issuer, subject),
    ).fetchone()

    if existing:
        user_id = existing["user_id"]
        conn.execute(
            "UPDATE profiles SET display_name = ?, email = ?, last_seen_at = ? "
            "WHERE user_id = ?",
            (claims.get("name"), claims.get("email"), now, user_id),
        )
        return user_id

    user_id = str(uuid4())
    conn.execute(
        "INSERT INTO profiles "
        "(user_id, issuer, subject, provider, display_name, email, first_seen_at, last_seen_at, purge_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        (user_id, issuer, subject, provider, claims.get("name"), claims.get("email"), now, now),
    )
    return user_id


def complete_login(
    conn: sqlite3.Connection,
    claims: dict,
    provider: str,
    flow_id: str | None,
) -> dict:
    """Ejecuta todo el login lógico en una sola transacción atómica.

    Orden de validaciones ANTES de abrir la transacción (fail-fast, sin
    tocar la BD si algo falla):
      1. identidad completa (iss, sub, name, email verificado)
      2. cuenta permitida (allowlist)
      3. preconsentimiento válido (no expirado, no reutilizado) —
         SE CONSUME AL FINAL, justo antes de persistir. Si se
         consumiera primero y luego fallara identidad/allowlist, un
         rerun posterior de Streamlit mostraría el mensaje confuso
         "ya fue usado" en vez del motivo real del rechazo.

    Si TODO pasa: perfil + 2 consent_events + sesión + auth_event +
    notification_outbox se escriben juntos o no se escribe nada
    (prueba T-22).
    """
    validate_identity(claims)
    check_allowlist(claims)
    preconsent_info = consent.consume_preconsent_flow(conn, flow_id)

    from src.db import transaction

    with transaction(conn) as cur:
        user_id = upsert_profile(cur.connection, claims, provider)

        occurred_at = _now_iso()
        for row in consent.build_consent_event_rows(user_id, preconsent_info, occurred_at):
            cur.execute(
                "INSERT INTO consent_events "
                "(consent_id, user_id, kind, version, status, occurred_at, method, preconsent_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )

        session_id = sessions.create_session(cur.connection, user_id, claims.get("iat"))
        event_id = audit.record_auth_event(
            cur.connection,
            user_id=user_id,
            session_id=session_id,
            event_type="session_started",
            result="success",
            app_version=APP_VERSION,
        )
        notifications.enqueue_session_started(
            cur.connection,
            event_id=event_id,
            session_id=session_id,
            destination_alias="curso-tbs-eia@institucional.example",
        )

    return {"user_id": user_id, "session_id": session_id}
