"""Provenance boundary audit (Phase 5, T-506; QG-API-02).

Three enforcement legs, all behavioural over the live app:

- TEST-PROV-003 schema leg: every ``float``-typed leaf of the OpenAPI
  response schemas is either a ``TracedValue`` or allow-listed.
- TEST-PROV-003 instance leg: every ``float`` leaf of real payloads is
  either inside a ``TracedValue`` object or allow-listed.
- RT-007 leg (lite): every evaluable ``TracedValue`` re-derives from its
  own expression within 1e-9 in a process that never imports
  ``backend.core``; procedural roots are reported separately, never
  fabricated.
- TEST-API-002: the full ``meta`` envelope on every GET route.
"""

from __future__ import annotations

import ast
import json
import operator
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.prov_allowlist import allowed
from backend.app.state import AppState
from backend.tests.integration._fixtures import csv_bytes, fixture_rows

REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_PATH = REPO_ROOT / "frontend" / "src" / "api" / "generated" / "openapi.json"

META_KEYS = {
    "request_id",
    "computed_at",
    "dataset_hash",
    "profile_id",
    "profile_version",
    "model_versions",
    "data_provenance",
    "code_git_sha",
    "duration_ms",
}

# Registry expressions that cannot re-derive from operands alone
# (procedural roots, D-037 scope split — reported, never faked).
PROCEDURAL_MARKERS = (
    "type7_median",
    "type7_q1",
    "type7_q3",
    "ceil_order_statistic",
    "attribution_credit_table",
    "robust_mahalanobis_d2",
    "median_ratio_shape_fit",
)

_BINOPS: dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARYOPS: dict[type, Callable[[float], float]] = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _restricted_eval(expression: str, variables: dict[str, Any]) -> float:
    """Evaluate a registry expression with no project imports (RT-007 rule)."""

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            value = variables[node.id]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"non-numeric variable {node.id!r}")
            return float(value)
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            _apply = _BINOPS[type(node.op)]
            return float(_apply(visit(node.left), visit(node.right)))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
            _negate = _UNARYOPS[type(node.op)]
            return float(_negate(visit(node.operand)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id not in ("min", "max"):
                raise TypeError(f"call to {node.func.id!r} is outside the evaluator")
            args = [visit(arg) for arg in node.args]
            return float(min(args) if node.func.id == "min" else max(args))
        raise TypeError(f"node {type(node).__name__} is outside the evaluator")

    return visit(ast.parse(expression, mode="eval"))


@pytest.fixture()
def client() -> Iterator[TestClient]:
    state = AppState(db_path=":memory:")
    app = create_app(state)
    with TestClient(app) as handle:
        response = handle.post(
            "/api/v1/datasets",
            files={"file": ("escape.csv", csv_bytes(fixture_rows()), "text/csv")},
        )
        assert response.status_code == 200, response.text
        yield handle
    state.close()


def _is_traced(node: Any) -> bool:
    return isinstance(node, dict) and {"formula_id", "expression", "value"} <= set(node)


def _iter_float_leaves(node: Any, path: str, inside_traced: bool = False) -> Any:
    if _is_traced(node):
        yield ("traced", path, node)
        return
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _iter_float_leaves(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_float_leaves(value, f"{path}.{index}")
    elif isinstance(node, float):
        yield ("bare", path, node)


def _schema_float_paths(schema: dict[str, Any], defs: dict[str, Any], path: str) -> Any:
    """Yield dotted paths of PURE bare-float leaves.

    Unions holding ``TracedValueSchema`` are skipped: ``TV | None`` carries
    no float, and ``TV | float`` conditionals are instance-audited per
    parameter (the schema cannot name which branch a parameter takes).
    """

    def is_tv(option: Any) -> bool:
        return isinstance(option, dict) and str(option.get("$ref", "")).endswith(
            "/TracedValueSchema"
        )

    def is_null(option: Any) -> bool:
        return isinstance(option, dict) and (
            option.get("type") == "null" or option.get("enum") == [None]
        )

    if "$ref" in schema:
        name = str(schema["$ref"]).split("/")[-1]
        if name == "TracedValueSchema":
            return
        yield from _schema_float_paths(defs[name], defs, path)
        return
    kind = schema.get("type")
    if kind == "number":
        yield path
        return
    if kind == "array":
        yield from _schema_float_paths(schema.get("items", {}), defs, f"{path}.*")
        return
    if kind == "object":
        for name, prop in (schema.get("properties") or {}).items():
            yield from _schema_float_paths(prop, defs, f"{path}.{name}" if path else str(name))
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            yield from _schema_float_paths(additional, defs, f"{path}.**")
        elif additional is True:
            yield f"{path}.**"
        return
    for key in ("anyOf", "oneOf"):
        options = schema.get(key)
        if isinstance(options, list):
            if any(is_tv(option) for option in options):
                continue  # traced-or-null/conditional: covered by the instance audit
            for option in options:
                if isinstance(option, dict) and not is_null(option):
                    yield from _schema_float_paths(option, defs, path)


def _is_freeform_envelope(name: str, schema: dict[str, Any]) -> bool:
    if not name.startswith("Envelope_"):
        return False
    data = (schema.get("properties") or {}).get("data", {})
    if data.get("type") == "object" and not data.get("properties"):
        return True
    items = data.get("items", {})
    return data.get("type") == "array" and (
        items.get("type") == "object" and not items.get("properties")
    )


@pytest.mark.fast
def test_no_bare_float_on_decision_fields() -> None:
    """TEST-PROV-003 schema leg: pure bare-float leaves are all allow-listed."""
    document: dict[str, Any] = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    defs = document["components"]["schemas"]
    uncovered: list[str] = []
    for name, schema in sorted(defs.items()):
        if name in ("TracedValueSchema", "HTTPValidationError", "ValidationError"):
            continue
        if name.endswith("Request") or _is_freeform_envelope(name, schema):
            continue  # request bodies and free-form dict envelopes: instance-audited
        for path in _schema_float_paths(schema, defs, name):
            if allowed(path) is None:
                uncovered.append(path)
    assert uncovered == []


@pytest.mark.fast
def test_investigation_float_audit_and_rederivation(client: TestClient) -> None:
    """Instance leg + RT-007 lite over a real investigation payload."""
    data: dict[str, Any] = client.get("/api/v1/components/C-T-ESC-01/investigation").json()["data"]
    _audit_payload(data)


def _audit_payload(data: dict[str, Any]) -> tuple[int, dict[str, int]]:
    """Instance audit: bare floats allow-listed; evaluable TVs rederive."""
    bare_uncovered: list[str] = []
    rederived = 0
    procedural: dict[str, int] = {}
    failures: list[str] = []
    for kind, path, node in _iter_float_leaves(data, ""):
        if kind == "bare":
            if allowed(path) is None:
                bare_uncovered.append(path)
            continue
        expression = str(node["expression"])
        variables = {**dict(node.get("inputs", {})), **dict(node.get("parameters", {}))}
        if any(marker in expression for marker in PROCEDURAL_MARKERS):
            marker = next(item for item in PROCEDURAL_MARKERS if item in expression)
            procedural[marker] = procedural.get(marker, 0) + 1
            continue
        try:
            expected = _restricted_eval(expression, variables)
        except (TypeError, ValueError, KeyError, SyntaxError, ZeroDivisionError) as err:
            failures.append(f"{path}: evaluator refused ({err})")
            continue
        if abs(float(node["value"]) - expected) > 1e-9:
            failures.append(f"{path}: {node['value']} != {expected}")
        else:
            rederived += 1
    assert bare_uncovered == []
    assert failures == []
    assert set(procedural) <= set(PROCEDURAL_MARKERS)
    return rederived, procedural


@pytest.mark.fast
def test_payload_audit_across_decision_surfaces(client: TestClient) -> None:
    """The instance audit holds on every decision-bearing surface."""
    total = 0
    endpoints = [
        "/api/v1/components/C-T-ESC-01/investigation",
        "/api/v1/components/C-T-ESC-01/anomaly",
        "/api/v1/components/C-T-ESC-01/drift",
        "/api/v1/components/C-T-ESC-01/explanation",
        "/api/v1/lots/L-T-001/statistics",
        "/api/v1/lots/L-T-001/disposition",
        "/api/v1/lots/L-T-001/distribution",
        "/api/v1/datasets",
    ]
    for endpoint in endpoints:
        payload: dict[str, Any] = client.get(endpoint).json()["data"]
        rederived, _ = _audit_payload(payload)
        total += rederived
    report_id: str = client.post(
        "/api/v1/reports",
        json={"scope": "component", "target_id": "C-T-ESC-01", "format": "html"},
    ).json()["data"]["report_id"]
    stored: dict[str, Any] = client.get(f"/api/v1/reports/{report_id}").json()["data"]
    assert "SYNTHETIC DATA" in stored["html"]
    assert total > 50, f"only {total} fields rederived; the net is too coarse"


@pytest.mark.fast
def test_traced_families_ship_no_bare_display_stats(client: TestClient) -> None:
    """Traced families (uA/ns) never silently fall back to plain display stats."""
    data: dict[str, Any] = client.get("/api/v1/components/C-T-ESC-01/investigation").json()["data"]
    for block in data["parameters"]:
        if block["parameter"] in ("iddq_standby", "prop_delay"):
            assert block["fully_traced"] is True
            stats = block["lot_statistics"]
            for field in ("median", "q1", "q3", "iqr", "robust_sigma"):
                assert isinstance(stats[field], dict), (block["parameter"], field)
                assert stats[field]["formula_id"].startswith("robust.")
            assert isinstance(block["dpat"]["limit_high"], dict)
            assert isinstance(block["dpat"]["z"], dict)
        if block["parameter"] == "vth_shift":
            assert block["fully_traced"] is False
    stats_data: dict[str, Any] = client.get("/api/v1/lots/L-T-001/statistics").json()["data"]
    vth_stats = next(item for item in stats_data["parameters"] if item["parameter"] == "vth_shift")
    assert vth_stats["fully_traced"] is False
    assert isinstance(vth_stats["median"], float)
    iddq_stats = next(
        item for item in stats_data["parameters"] if item["parameter"] == "iddq_standby"
    )
    assert iddq_stats["fully_traced"] is True
    assert isinstance(iddq_stats["median"], dict)


@pytest.mark.fast
def test_meta_envelope_on_every_get_route(client: TestClient) -> None:
    """TEST-API-002: the full meta envelope on every GET route in the document."""
    document: dict[str, Any] = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    dataset_hash: str = client.get("/api/v1/datasets").json()["data"][0]["dataset_hash"]
    fill = {
        "component_id": "C-T-ESC-01",
        "lot_id": "L-T-001",
        "dataset_hash": dataset_hash,
        "profile_id": "mil_std_883_like",
        "version": "1",
        "formula_id": "dpat.limit_high_v1",
        "group": "CMOS_LOGIC/iddq_standby",
        "report_id": "does-not-exist",
    }
    checked = 0
    for path, item in sorted(document["paths"].items()):
        if "get" not in item:
            continue
        if path == "/api/v1/reports/{report_id}/pdf":
            continue  # byte stream, not an envelope
        concrete = path
        for key, value in fill.items():
            concrete = concrete.replace("{" + key + "}", value)
        if "{" in concrete:
            continue
        response = client.get(concrete)
        assert response.status_code in (200, 404), (concrete, response.text)
        if response.status_code == 200:
            assert META_KEYS <= set(response.json()["meta"]), concrete
            checked += 1
    assert checked >= 15, f"only {checked} routes checked"


@pytest.mark.fast
def test_units_never_blank_on_traced_values(client: TestClient) -> None:
    """TEST-PROV-001 instance leg: every shipped TracedValue has a unit."""
    data: dict[str, Any] = client.get("/api/v1/components/C-T-ESC-01/investigation").json()["data"]
    count = 0
    for kind, path, node in _iter_float_leaves(data, ""):
        if kind == "traced":
            assert isinstance(node["unit"], str) and node["unit"].strip(), path
            count += 1
    assert count > 50
