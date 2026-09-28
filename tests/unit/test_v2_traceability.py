"""Pruebas de trazabilidad v2 (GUIA_V2 §11, P153/P154)."""
import json
from pathlib import Path
from unittest.mock import patch

from src.traceability import (
    build_trace_record,
    compute_analysis_id,
    compute_snapshot_sha256,
    get_code_commit,
)

V2_PLANTILLA = (
    Path(__file__).resolve().parents[2] / "v2" / "plantillas" / "trazabilidad.json"
)


def test_analysis_id_is_unique_each_call():
    ids = {compute_analysis_id() for _ in range(50)}
    assert len(ids) == 50


def test_snapshot_hash_is_deterministic_for_same_payload():
    payload = {"a": 1, "b": [1, 2, 3]}
    assert compute_snapshot_sha256(payload) == compute_snapshot_sha256(payload)


def test_snapshot_hash_differs_for_different_payload():
    h1 = compute_snapshot_sha256({"a": 1})
    h2 = compute_snapshot_sha256({"a": 2})
    assert h1 != h2


def test_snapshot_hash_ignores_key_order():
    h1 = compute_snapshot_sha256({"a": 1, "b": 2})
    h2 = compute_snapshot_sha256({"b": 2, "a": 1})
    assert h1 == h2


def test_get_code_commit_returns_string_without_raising():
    commit = get_code_commit()
    assert isinstance(commit, str)
    assert commit != ""


def test_get_code_commit_falls_back_gracefully_when_git_unavailable():
    with patch("src.traceability.subprocess.run", side_effect=FileNotFoundError("no git")):
        assert get_code_commit() == "no_disponible"


def test_build_trace_record_has_same_keys_as_template():
    template_keys = set(json.loads(V2_PLANTILLA.read_text()).keys())
    record = build_trace_record(
        source="Yahoo Finance (yfinance)",
        currency="USD",
        frequency="Diaria",
        return_convention="retornos simples",
        annualization="lineal (mu*m, Sigma*m)",
        asset_order=["AAPL", "MSFT"],
        common_rows=250,
        parameters={"rf": 0.03, "gamma": 5.0},
        solver="scipy.optimize.minimize SLSQP",
    )
    assert set(record.keys()) == template_keys


def test_build_trace_record_status_is_executed_not_template_placeholder():
    record = build_trace_record(
        source="fixture", currency="USD", frequency="Diaria",
        return_convention="simple", annualization="lineal",
        asset_order=["A"], common_rows=10, parameters={}, solver="x",
    )
    assert record["status"] == "ejecutado"


def test_build_trace_record_preserves_given_parameters_and_asset_order():
    params = {"rf": 0.05, "delta_shrinkage": 0.2}
    record = build_trace_record(
        source="fixture", currency="COP", frequency="Mensual",
        return_convention="simple", annualization="lineal",
        asset_order=["B", "A"], common_rows=60, parameters=params, solver="x",
    )
    assert record["parameters"] == params
    assert record["asset_order"] == ["B", "A"]
    assert record["currency"] == "COP"
    assert record["common_rows"] == 60


def test_build_trace_record_leaves_student_decision_none_when_not_provided():
    """El estudiante debe llenarlo — no se inventa un valor por defecto
    con apariencia de decisión real."""
    record = build_trace_record(
        source="fixture", currency="USD", frequency="Diaria",
        return_convention="simple", annualization="lineal",
        asset_order=["A"], common_rows=10, parameters={}, solver="x",
    )
    assert record["student_decision"] is None
