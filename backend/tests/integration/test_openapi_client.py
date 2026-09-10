"""Contract tests for the T-505 generation workflow (QG-API-01).

Oracle: the TEST-API-001 mechanism — regenerate the OpenAPI document
from the live app and the TypeScript client from that document, and
diff both against the committed files. Any diff fails, in either
direction: a backend change without regeneration, or a hand edit to a
generated file. The full frontend-side TEST-API-001 verdict stays with
QA; this suite pins the backend half of the mechanism.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.state import AppState

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATED_DIR = REPO_ROOT / "frontend" / "src" / "api" / "generated"
OPENAPI_PATH = GENERATED_DIR / "openapi.json"
CLIENT_PATH = GENERATED_DIR / "client.ts"


@pytest.fixture()
def client() -> Iterator[TestClient]:
    state = AppState(db_path=":memory:")
    app = create_app(state)
    with TestClient(app) as handle:
        yield handle
    state.close()


@pytest.mark.fast
def test_committed_openapi_matches_live_app(client: TestClient) -> None:
    """The committed document is byte-identical to a fresh render."""
    served: dict[str, Any] = client.get("/api/v1/openapi.json").json()
    rendered = json.dumps(served, indent=2, sort_keys=True) + "\n"
    assert OPENAPI_PATH.exists(), "committed openapi.json is missing"
    assert OPENAPI_PATH.read_text(encoding="utf-8") == rendered


@pytest.mark.fast
def test_generate_scripts_are_clean_and_current() -> None:
    """Both generators pass --check against the committed files."""
    for script in ("scripts/generate_openapi.py", "scripts/generate_ts_client.py"):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / script), "--check"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert proc.returncode == 0, f"{script} --check failed:\n{proc.stdout}\n{proc.stderr}"


@pytest.mark.fast
def test_generated_client_covers_served_routes(client: TestClient) -> None:
    """Every served route appears in the generated route table."""
    document: dict[str, Any] = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    served_paths = set(document["paths"])
    text = CLIENT_PATH.read_text(encoding="utf-8")
    assert "DO NOT EDIT" in text
    for path in sorted(served_paths):
        assert path in text, path
    assert document["openapi"].startswith("3.1")
    assert "TracedValueSchema" in text
    assert "InvestigationData" in text
