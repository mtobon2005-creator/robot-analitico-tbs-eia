"""Trazabilidad de un análisis v2 (GUIA_V2 §11, esquema en
v2/plantillas/trazabilidad.json).

Cada ejecución relevante debe poder reconstruirse: qué datos entraron,
qué parámetros y solver se usaron, y en qué commit del código — sin
transcribir nada a mano (P153/P154). Este módulo no reemplaza
README/BITACORA/ESTADO; genera el registro automático que esos
documentos deben referenciar.
"""
import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


def compute_analysis_id() -> str:
    return str(uuid.uuid4())


def compute_snapshot_sha256(payload) -> str:
    """Hash reproducible de los datos/parámetros de ENTRADA (no del
    resultado) — permite verificar si dos ejecuciones partieron
    exactamente de lo mismo."""
    serialized = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def get_code_commit(repo_path: Path | None = None) -> str:
    """Commit de git actual del código en ejecución, o 'no_disponible'
    si no se puede leer (ej. entorno sin carpeta .git) — nunca falla la
    traza por esto, solo lo reporta."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path or Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "no_disponible"


def build_trace_record(
    *,
    source: str,
    currency: str,
    frequency: str,
    return_convention: str,
    annualization: str,
    asset_order: list,
    common_rows: int,
    parameters: dict,
    solver: str,
    residuals: dict | None = None,
    views_ids: list | None = None,
    student_decision: str | None = None,
    test_evidence: str | None = None,
) -> dict:
    """Arma un registro con el esquema de v2/plantillas/trazabilidad.json,
    completado con los datos reales de esta ejecución (status="ejecutado",
    no el "plantilla_no_ejecucion" de la plantilla vacía)."""
    now = datetime.now(timezone.utc).isoformat()
    snapshot_payload = {
        "asset_order": asset_order,
        "parameters": parameters,
        "common_rows": common_rows,
        "frequency": frequency,
        "currency": currency,
    }
    return {
        "schema": "bot-portafolios/trace/v2",
        "analysis_id": compute_analysis_id(),
        "snapshot_sha256": compute_snapshot_sha256(snapshot_payload),
        "code_commit": get_code_commit(),
        "dependencies": {},
        "source": source,
        "rights": None,
        "source_fields": [],
        "event_at": None,
        "available_at": None,
        "received_at": now,
        "calculated_at": now,
        "timezone": "UTC",
        "currency": currency,
        "frequency": frequency,
        "return_convention": return_convention,
        "annualization": annualization,
        "asset_order": list(asset_order),
        "missing_data_rule": "intersección de fechas comunes tras alinear precios (dropna)",
        "common_rows": common_rows,
        "transformations": [],
        "parameters": parameters,
        "solver": solver,
        "residuals": residuals or {},
        "views_ids": views_ids or [],
        "trigger_id": None,
        "rebalance_id": None,
        "student_decision": student_decision,
        "test_evidence": test_evidence,
        "status": "ejecutado",
    }
