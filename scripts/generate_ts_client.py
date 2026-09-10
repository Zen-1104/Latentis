#!/usr/bin/env python3
"""Generate the TypeScript API client from the OpenAPI document (T-505).

Reads ``frontend/src/api/generated/openapi.json`` and writes
``frontend/src/api/generated/client.ts``: one exported interface per
schema plus the route table. Deterministic (sorted keys, fixed
formatting) and dependency-free — the drift check regenerates and
diffs, so hand-editing the output fails the build (QG-API-01).

Variance note (DECISIONS D-046): the register oracle names Zod, but
the frontend ships no zod dependency; adding one is a
frontend-engineer call. The generated artifact is TypeScript
interfaces — the same single-source-of-truth mechanism, without a new
runtime dependency in the offline bundle.

Usage:
    uv run python scripts/generate_ts_client.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = REPO_ROOT / "frontend" / "src" / "api" / "generated"
OPENAPI_PATH = GENERATED_DIR / "openapi.json"
CLIENT_PATH = GENERATED_DIR / "client.ts"

_HEADER = """/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Produced by `uv run python scripts/generate_ts_client.py` from
 * `frontend/src/api/generated/openapi.json` (which is itself generated
 * from the live FastAPI application). Any hand edit is overwritten by
 * the next generation and fails the `api-contract` CI drift check
 * (QG-API-01, TEST-API-001 mechanism).
 */
"""

_TS_KEYWORDS = {
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "debugger",
    "default",
    "delete",
    "do",
    "else",
    "enum",
    "export",
    "extends",
    "false",
    "finally",
    "for",
    "function",
    "if",
    "import",
    "in",
    "instanceof",
    "new",
    "null",
    "return",
    "super",
    "switch",
    "this",
    "throw",
    "true",
    "try",
    "typeof",
    "var",
    "void",
    "while",
    "with",
}


def _safe_name(name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char == "_" else "_" for char in name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if cleaned in _TS_KEYWORDS:
        cleaned = f"{cleaned}_"
    return cleaned


def _ref_name(ref: str) -> str:
    return _safe_name(ref.split("/")[-1])


def _ts_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return _ref_name(str(schema["$ref"]))
    if "anyOf" in schema and isinstance(schema["anyOf"], list):
        return " | ".join(_ts_type(item) for item in schema["anyOf"])
    if "oneOf" in schema and isinstance(schema["oneOf"], list):
        return " | ".join(_ts_type(item) for item in schema["oneOf"])
    if "allOf" in schema and isinstance(schema["allOf"], list):
        parts = [_ts_type(item) for item in schema["allOf"] if item != {"type": "object"}]
        return " & ".join(parts) if parts else "Record<string, unknown>"
    if "enum" in schema and isinstance(schema["enum"], list):
        return " | ".join(json.dumps(item) for item in schema["enum"])
    kind = schema.get("type")
    if kind == "string":
        return "string"
    if kind == "integer":
        return "number"
    if kind == "number":
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind == "array":
        items = schema.get("items", {})
        return f"Array<{_ts_type(items) if isinstance(items, dict) else 'unknown'}>"
    if kind == "object":
        properties = schema.get("properties")
        if not isinstance(properties, dict) or not properties:
            additional = schema.get("additionalProperties")
            if isinstance(additional, dict):
                return f"Record<string, {_ts_type(additional)}>"
            return "Record<string, unknown>"
        required = set(schema.get("required", []))
        fields = []
        for prop in sorted(properties):
            optional = "" if prop in required else "?"
            fields.append(f"  {_safe_name(prop)}{optional}: {_ts_type(properties[prop])};")
        return "{\n" + "\n".join(fields) + "\n}"
    return "unknown"


def _interface_name(raw: str) -> str:
    return _safe_name(raw)


def generate(document: dict[str, Any]) -> str:
    """Render the full client source from the OpenAPI document."""
    schemas = document.get("components", {}).get("schemas", {})
    paths = document.get("paths", {})
    chunks: list[str] = [_HEADER.rstrip("\n"), ""]
    chunks.append("/* -- Schemas (one interface per OpenAPI component) -- */")
    for name in sorted(schemas):
        schema = schemas[name]
        body = _ts_type(schema)
        if body.startswith("{"):
            chunks.append(f"export interface {_interface_name(name)} {body}")
        else:
            chunks.append(f"export type {_interface_name(name)} = {body};")
        chunks.append("")
    chunks.append("/* -- Route table (method + path, for typed fetch wrappers) -- */")
    chunks.append(
        "export interface ApiRoute { method: string; path: string; operationId?: string }"
    )
    chunks.append("export const API_ROUTES: ApiRoute[] = [")
    routes: list[tuple[str, str, str]] = []
    for path in sorted(paths):
        item = paths[path]
        if not isinstance(item, dict):
            continue
        for method in sorted(item):
            if method.startswith("x-") or not isinstance(item[method], dict):
                continue
            operation = item[method]
            operation_id = operation.get("operationId", "")
            routes.append((method.upper(), path, str(operation_id)))
    for method, path, operation_id in routes:
        chunks.append(
            f'  {{ method: "{method}", path: {json.dumps(path)},'
            f" operationId: {json.dumps(operation_id)} }},"
        )
    chunks.append("];")
    chunks.append("")
    return "\n".join(chunks)


def main() -> int:
    """Generate (default) or verify (``--check``) the committed client."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when the committed client differs from a fresh render.",
    )
    args = parser.parse_args()
    if not OPENAPI_PATH.exists():
        sys.stdout.write(f"missing committed document: {OPENAPI_PATH}" + "\n")
        sys.stdout.write("run: uv run python scripts/generate_openapi.py" + "\n")
        return 1
    document: dict[str, Any] = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    rendered = generate(document)
    if args.check:
        if not CLIENT_PATH.exists():
            sys.stdout.write(f"missing committed client: {CLIENT_PATH}" + "\n")
            return 1
        if CLIENT_PATH.read_text(encoding="utf-8") != rendered:
            sys.stdout.write(
                "client drift: the committed client differs from a fresh render." + "\n"
            )
            sys.stdout.write("run: uv run python scripts/generate_ts_client.py" + "\n")
            return 1
        sys.stdout.write("client drift check: no changes." + "\n")
        return 0
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    CLIENT_PATH.write_text(rendered, encoding="utf-8")
    sys.stdout.write(f"wrote {CLIENT_PATH}" + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
