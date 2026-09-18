"""Ciclo de vida y purga (RNF-03, sección 3.4 y 7.4-7.5).

Tres operaciones distintas:
1. `revoke_user_immediately` — revocación explícita de un usuario:
   bloquea y purga sus almacenes activos DE INMEDIATO.
2. `schedule_purge_for_all` — al cierre del curso: fija purge_at =
   firmeza_calificación + 90 días para todo lo que no tenga ya un
   purge_at más próximo (por una revocación previa).
3. `run_lifecycle_purge` — el worker periódico (al menos una vez al
   día, punto 46): purga flujos de preconsentimiento vencidos sin
   consumir, filas cuyo purge_at ya venció, y expira deletion_markers.

`reapply_purge_after_restore` cubre T-23: si un respaldo restaurado
trae de vuelta filas que ya deberían estar purgadas, se vuelven a
eliminar ANTES de habilitar cualquier acceso.
"""
import hashlib
import hmac
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

TECH_LOG_RETENTION_DAYS = 14
BACKUP_RETENTION_DAYS = 30
GRADING_RETENTION_DAYS = 90

_HMAC_SECRET_ENV = "LIFECYCLE_HMAC_SECRET"


class MissingLifecycleSecret(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _hmac_secret() -> bytes:
    secret = os.environ.get(_HMAC_SECRET_ENV)
    if not secret:
        raise MissingLifecycleSecret(
            f"Falta la variable de entorno {_HMAC_SECRET_ENV} (gestor de "
            "secretos institucional) para el worker de ciclo de vida."
        )
    return secret.encode("utf-8")


# --- Fecha de purga y deletion markers ---------------------------------------

def compute_purge_at(
    firmeza_calificacion: date, requested_at: datetime | None = None
) -> datetime:
    """purge_at = la MENOR entre una solicitud válida y 90 días después
    de la firmeza de la calificación (sección 3.4)."""
    grading_deadline = datetime.combine(
        firmeza_calificacion, datetime.min.time(), tzinfo=timezone.utc
    ) + timedelta(days=GRADING_RETENTION_DAYS)
    if requested_at is None:
        return grading_deadline
    return min(requested_at, grading_deadline)


def create_deletion_marker(conn: sqlite3.Connection, subject_id: str, reason: str) -> str:
    """marker_hmac es un HMAC con clave del subject_id — SIN nombre,
    correo, iss ni sub en claro (sección 7.3.1). Vence con el último
    respaldo (BACKUP_RETENTION_DAYS)."""
    digest = hmac.new(_hmac_secret(), subject_id.encode("utf-8"), hashlib.sha256).hexdigest()
    now = _now()
    conn.execute(
        "INSERT INTO deletion_markers "
        "(marker_hmac, created_at, expires_at, reason, status, last_reapplied_at) "
        "VALUES (?, ?, ?, ?, 'active', NULL)",
        (digest, _iso(now), _iso(now + timedelta(days=BACKUP_RETENTION_DAYS)), reason),
    )
    return digest


# --- Revocación inmediata -----------------------------------------------------

@dataclass(frozen=True)
class RevocationResult:
    user_id: str
    marker_hmac: str
    deleted_counts: dict


def _purge_user_cascade(cur: sqlite3.Cursor, user_id: str) -> dict:
    """Borra en cascada (respetando FKs: hijos antes que padres) todo
    lo identificable de un usuario. Reutilizado por revocación
    inmediata y por la purga programada."""
    counts = {}

    cur.execute(
        "DELETE FROM notification_outbox WHERE session_id IN "
        "(SELECT session_id FROM app_sessions WHERE user_id = ?)",
        (user_id,),
    )
    counts["notification_outbox"] = cur.rowcount

    cur.execute("DELETE FROM auth_events WHERE user_id = ?", (user_id,))
    counts["auth_events"] = cur.rowcount

    cur.execute("DELETE FROM app_sessions WHERE user_id = ?", (user_id,))
    counts["app_sessions"] = cur.rowcount

    cur.execute("DELETE FROM consent_events WHERE user_id = ?", (user_id,))
    counts["consent_events"] = cur.rowcount

    cur.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
    counts["profiles"] = cur.rowcount

    return counts


def revoke_user_immediately(
    conn: sqlite3.Connection, user_id: str, reason: str
) -> RevocationResult:
    """Punto 74 / T-23: la revocación bloquea (cierra sesión) y purga
    de inmediato — no espera a purge_at. Crea un deletion_marker para
    poder reaplicar la purga si un respaldo restaura estas filas."""
    from src.db import transaction

    with transaction(conn) as cur:
        cur.execute(
            "UPDATE app_sessions SET status='closed', closed_at=? "
            "WHERE user_id=? AND status='active'",
            (_iso(_now()), user_id),
        )
        deleted = _purge_user_cascade(cur, user_id)
        marker = create_deletion_marker(cur.connection, user_id, reason)

    return RevocationResult(user_id=user_id, marker_hmac=marker, deleted_counts=deleted)


# --- Purga programada al cierre del curso ------------------------------------

def schedule_purge_for_all(conn: sqlite3.Connection, firmeza_calificacion: date) -> int:
    """Al cierre del piloto: fija purge_at = firmeza+90d para todo
    perfil que no tenga ya un purge_at más próximo (por revocación
    previa). Devuelve cuántos perfiles se actualizaron."""
    purge_at_iso = _iso(compute_purge_at(firmeza_calificacion))
    cur = conn.execute(
        "UPDATE profiles SET purge_at = ? WHERE purge_at IS NULL OR purge_at > ?",
        (purge_at_iso, purge_at_iso),
    )
    conn.execute(
        "UPDATE auth_events SET purge_at = ? WHERE purge_at IS NULL OR purge_at > ?",
        (purge_at_iso, purge_at_iso),
    )
    conn.execute(
        "UPDATE notification_outbox SET purge_at = ? WHERE purge_at IS NULL OR purge_at > ?",
        (purge_at_iso, purge_at_iso),
    )
    return cur.rowcount


# --- Worker periódico de purga ------------------------------------------------

@dataclass(frozen=True)
class PurgeRunResult:
    job_id: str
    expired_flows_deleted: int
    profiles_purged: int
    markers_expired: int
    deleted_counts_by_table: dict


def run_lifecycle_purge(conn: sqlite3.Connection) -> PurgeRunResult:
    """Ejecutar al menos una vez al día, al cierre del piloto, y bajo
    demanda por revocación (punto 46). Purga:
    1. Flujos de preconsentimiento NO consumidos ya vencidos (>15 min).
    2. Perfiles (y todo lo asociado en cascada) cuyo purge_at venció.
    3. Expira deletion_markers cuyo expires_at ya pasó.
    Registra un lifecycle_job con los conteos — sin conservar
    identificadores (punto: 'al terminar no conserva identificadores')."""
    from src.db import transaction

    job_id = str(uuid4())
    now_iso = _iso(_now())
    totals = {"notification_outbox": 0, "auth_events": 0, "app_sessions": 0,
              "consent_events": 0, "profiles": 0}

    with transaction(conn) as cur:
        cur.execute(
            "DELETE FROM preconsent_flows WHERE consumed_at IS NULL AND expires_at <= ?",
            (now_iso,),
        )
        expired_flows = cur.rowcount

        due_profiles = cur.execute(
            "SELECT user_id FROM profiles WHERE purge_at IS NOT NULL AND purge_at <= ?",
            (now_iso,),
        ).fetchall()
        for row in due_profiles:
            counts = _purge_user_cascade(cur, row["user_id"])
            for table, n in counts.items():
                totals[table] += n

        cur.execute(
            "UPDATE deletion_markers SET status='expired' "
            "WHERE status='active' AND expires_at <= ?",
            (now_iso,),
        )
        markers_expired = cur.rowcount

        cur.execute(
            "INSERT INTO lifecycle_jobs "
            "(job_id, reason, scheduled_at, executed_at, status, deleted_counts) "
            "VALUES (?, 'scheduled_purge', ?, ?, 'completed', ?)",
            (job_id, now_iso, now_iso, json.dumps(totals)),
        )

    return PurgeRunResult(
        job_id=job_id,
        expired_flows_deleted=expired_flows,
        profiles_purged=len(due_profiles),
        markers_expired=markers_expired,
        deleted_counts_by_table=totals,
    )


def reapply_purge_after_restore(conn: sqlite3.Connection) -> PurgeRunResult:
    """T-23: tras restaurar un respaldo, reaplicar la purga ANTES de
    habilitar cualquier acceso — un respaldo puede traer de vuelta
    filas que ya deberían estar purgadas (perfiles con purge_at
    vencido, o correspondientes a un deletion_marker activo)."""
    result = run_lifecycle_purge(conn)
    conn.execute(
        "UPDATE deletion_markers SET last_reapplied_at = ? WHERE status IN ('active','expired')",
        (_iso(_now()),),
    )
    return result


if __name__ == "__main__":
    # Ejecutar como proceso independiente: python -m src.lifecycle
    # El scheduler debe invocarlo al menos una vez al día (punto 46).
    from src.db import get_connection, init_schema

    connection = get_connection()
    init_schema(connection)
    outcome = run_lifecycle_purge(connection)
    print(
        f"lifecycle_worker: job={outcome.job_id} "
        f"flujos_vencidos={outcome.expired_flows_deleted} "
        f"perfiles_purgados={outcome.profiles_purged} "
        f"markers_expirados={outcome.markers_expired}"
    )
