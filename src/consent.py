"""Preconsentimiento de un solo uso previo al redirect OIDC.

Antes de enviar al usuario a Google/Microsoft, exigimos que acepte
DOS controles separados y no premarcados: aviso de privacidad y
disclaimer académico (sección 3.3). Ese momento se registra como un
`preconsent_flow` opaco, de un solo uso, sin PII y con vigencia de 15
minutos (sección 3.4). El callback OIDC debe consumirlo antes de
persistir cualquier perfil/sesión.

LIMITACIÓN CONOCIDA (documentarla en TRACEABILITY.md / discutirla con
el docente): la guía pide entregar este flow_id al navegador en una
cookie propia, Secure/HttpOnly/SameSite=Lax, separada del cookie de
identidad que gestiona st.login(). El modelo de script de Streamlit no
expone control nativo de cabeceras Set-Cookie con HttpOnly real desde
Python puro; hacerlo con librerías de cookies vía JS (p. ej.
extra-streamlit-components) no puede ser verdaderamente HttpOnly,
porque JS necesita poder leerla. Aquí usamos `st.session_state` como
almacén servidor-por-navegador para el flow_id_hash activo, que es el
equivalente más cercano disponible en Streamlit puro sin bajar a un
servidor ASGI (st.App) o Authlib manual. Si el criterio de evaluación
exige la cookie HttpOnly literal, este es el punto a migrar primero
(ver README).
"""
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

FLOW_TTL_MINUTES = 15


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def issue_preconsent_flow(
    conn: sqlite3.Connection, disclaimer_version: str, privacy_version: str
) -> str:
    """Crea un flow de un solo uso y devuelve el flow_id OPACO (sin hash).

    Solo el hash se persiste en BD; el valor crudo es lo que el
    servidor guarda en session_state para comparar en el consumo.
    """
    flow_id = secrets.token_urlsafe(32)
    flow_id_hash = hashlib.sha256(flow_id.encode("utf-8")).hexdigest()
    now = _now()
    expires_at = now + timedelta(minutes=FLOW_TTL_MINUTES)

    conn.execute(
        "INSERT INTO preconsent_flows "
        "(flow_id_hash, disclaimer_version, privacy_version, accepted_at, expires_at, consumed_at) "
        "VALUES (?, ?, ?, ?, ?, NULL)",
        (flow_id_hash, disclaimer_version, privacy_version, _iso(now), _iso(expires_at)),
    )
    return flow_id


class PreconsentInvalid(Exception):
    """El flow falta, expiró o ya fue usado."""


def consume_preconsent_flow(conn: sqlite3.Connection, flow_id: str | None) -> dict:
    """Valida y marca como consumido un flow. Lanza PreconsentInvalid si falla.

    Devuelve dict con disclaimer_version y privacy_version aceptadas,
    para registrar los consent_events correspondientes.
    """
    if not flow_id:
        raise PreconsentInvalid("flow_id ausente")

    flow_id_hash = hashlib.sha256(flow_id.encode("utf-8")).hexdigest()
    row = conn.execute(
        "SELECT flow_id_hash, disclaimer_version, privacy_version, expires_at, consumed_at "
        "FROM preconsent_flows WHERE flow_id_hash = ?",
        (flow_id_hash,),
    ).fetchone()

    if row is None:
        raise PreconsentInvalid("flow_id no existe")
    if row["consumed_at"] is not None:
        raise PreconsentInvalid("flow_id ya fue usado")
    if datetime.fromisoformat(row["expires_at"]) < _now():
        raise PreconsentInvalid("flow_id expirado")

    conn.execute(
        "UPDATE preconsent_flows SET consumed_at = ? WHERE flow_id_hash = ?",
        (_iso(_now()), flow_id_hash),
    )
    return {
        "flow_id_hash": flow_id_hash,
        "disclaimer_version": row["disclaimer_version"],
        "privacy_version": row["privacy_version"],
    }


def build_consent_event_rows(
    user_id: str, preconsent: dict, occurred_at: str
) -> list[tuple]:
    """Filas (consent_events) para privacy + disclaimer, mismo preconsent_id."""
    return [
        (
            str(uuid4()),
            user_id,
            "privacy",
            preconsent["privacy_version"],
            "accepted",
            occurred_at,
            "checkbox_explicit",
            preconsent["flow_id_hash"],
        ),
        (
            str(uuid4()),
            user_id,
            "disclaimer",
            preconsent["disclaimer_version"],
            "accepted",
            occurred_at,
            "checkbox_explicit",
            preconsent["flow_id_hash"],
        ),
    ]
