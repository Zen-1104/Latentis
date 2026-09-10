#!/usr/bin/env python3
"""Generate the committed OpenAPI document (T-505, QG-API-01).

Writes ``frontend/src/api/generated/openapi.json`` from the live
FastAPI application. The file is generated, never hand-edited: the
drift check (``scripts/check_api_drift.py``, CI ``api-contract`` job)
regenerates it and fails on any diff.

Usage:
    uv run python scripts/generate_openapi.py [--check]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = REPO_ROOT / "frontend" / "src" / "api" / "generated"
OPENAPI_PATH = GENERATED_DIR / "openapi.json"


def build_document() -> dict[str, object]:
    """Return the live OpenAPI 3.1 document from the real application."""
    # The OpenAPI document never touches storage, but importing the app
    # module builds its default state: point that at a throwaway database
    # so generation never locks (or creates) the demo file.
    scratch = Path(tempfile.mkdtemp(prefix="latentis-openapi-gen-"))
    db_path = scratch / "gen.duckdb"
    os.environ["LATENTIS_DB_PATH"] = str(db_path)
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from backend.app.main import create_app

        app = create_app()
        document: dict[str, object] = app.openapi()
        return document
    finally:
        import shutil

        shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    """Generate (default) or verify (``--check``) the committed document."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when the committed document differs from the live app.",
    )
    args = parser.parse_args()
    document = build_document()
    rendered = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not OPENAPI_PATH.exists():
            sys.stdout.write(f"missing committed document: {OPENAPI_PATH}" + "\n")
            return 1
        committed = OPENAPI_PATH.read_text(encoding="utf-8")
        if committed != rendered:
            sys.stdout.write(
                "openapi drift: the committed document differs from the live app." + "\n"
            )
            sys.stdout.write("run: uv run python scripts/generate_openapi.py" + "\n")
            return 1
        sys.stdout.write("openapi drift check: no changes." + "\n")
        return 0
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(rendered, encoding="utf-8")
    sys.stdout.write(f"wrote {OPENAPI_PATH}" + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
