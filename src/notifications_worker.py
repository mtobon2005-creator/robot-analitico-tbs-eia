"""Worker independiente del proceso web (sección 7.3, punto 67).

Ejecutar por separado: `python -m src.notifications_worker` (idealmente
vía scheduler, al menos una vez por minuto). No depende de recargas
del navegador para reintentar.

PENDIENTE (el curso lo suministra, punto 46 de la guía): el sink
institucional real. Aquí se implementa un `Sink` con protocolo simple
y un `LocalFileSink` de referencia que simula una confirmación 2xx y
escribe a un archivo JSONL — reemplazar por el sink institucional
cuando esté disponible, sin cambiar la lógica de reintentos.
"""
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

MAX_ATTEMPTS = 3
RETRY_BACKOFF_MINUTES = 2


class Sink(Protocol):
    def send(self, event_id: str, payload: dict) -> bool:
        """Devuelve True si el envío fue confirmado (equivalente a 2xx)."""
        ...


@dataclass
class LocalFileSink:
    """Sink de referencia (placeholder). NO usar en el piloto final;
    el curso provee un sink institucional real. Es idempotente por
    event_id: si el mismo event_id ya fue registrado, no duplica."""

    path: Path = Path("data/sink_log.jsonl")

    def _already_sent(self, event_id: str) -> bool:
        if not self.path.exists():
            return False
        with self.path.open("r", encoding="utf-8") as f:
            return any(json.loads(line)["event_id"] == event_id for line in f if line.strip())

    def send(self, event_id: str, payload: dict) -> bool:
        if self._already_sent(event_id):
            return True  # idempotente: ya confirmado antes
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event_id": event_id, **payload}) + "\n")
        return True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def process_pending_notifications(conn: sqlite3.Connection, sink: Sink) -> dict:
    """Procesa filas 'pending' cuyo next_attempt_at ya pasó.

    Adquisición atómica por fila (UPDATE...WHERE status='pending' antes
    de leer detalles) para evitar que dos ejecuciones concurrentes del
    worker procesen la misma fila dos veces.
    Devuelve conteos {'sent': n, 'failed': n, 'retried': n}.
    """
    counts = {"sent": 0, "failed": 0, "retried": 0}
    now_iso = _iso(_now())

    rows = conn.execute(
        "SELECT outbox_id, event_id, session_id, type, destination_alias, attempt_count "
        "FROM notification_outbox "
        "WHERE status = 'pending' AND next_attempt_at <= ?",
        (now_iso,),
    ).fetchall()

    for row in rows:
        # Adquisición atómica: solo avanza si sigue 'pending' (evita doble
        # procesamiento por ejecuciones concurrentes del worker).
        cur = conn.execute(
            "UPDATE notification_outbox SET attempt_count = attempt_count + 1 "
            "WHERE outbox_id = ? AND status = 'pending'",
            (row["outbox_id"],),
        )
        if cur.rowcount == 0:
            continue  # otra ejecución ya la tomó

        attempt_count = row["attempt_count"] + 1
        payload = {
            "type": row["type"],
            "destination_alias": row["destination_alias"],
            "session_id": row["session_id"],
        }

        try:
            confirmed = sink.send(row["event_id"], payload)
        except Exception as exc:  # el sink falló (timeout, 5xx, etc.)
            confirmed = False
            last_error = str(exc)
        else:
            last_error = None if confirmed else "sink no confirmó (sin 2xx)"

        if confirmed:
            conn.execute(
                "UPDATE notification_outbox SET status = 'sent', sent_at = ?, error = NULL "
                "WHERE outbox_id = ?",
                (_iso(_now()), row["outbox_id"]),
            )
            counts["sent"] += 1
        elif attempt_count >= MAX_ATTEMPTS:
            conn.execute(
                "UPDATE notification_outbox SET status = 'failed', error = ? WHERE outbox_id = ?",
                (last_error, row["outbox_id"]),
            )
            counts["failed"] += 1
        else:
            next_attempt = _iso(_now() + timedelta(minutes=RETRY_BACKOFF_MINUTES))
            conn.execute(
                "UPDATE notification_outbox SET next_attempt_at = ?, error = ? WHERE outbox_id = ?",
                (next_attempt, last_error, row["outbox_id"]),
            )
            counts["retried"] += 1

    return counts


if __name__ == "__main__":
    from src.db import get_connection, init_schema

    connection = get_connection()
    init_schema(connection)
    result = process_pending_notifications(connection, LocalFileSink())
    print(f"notifications_worker: {result}")
