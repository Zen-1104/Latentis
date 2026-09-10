#!/usr/bin/env python3
"""API contract drift gate (T-505, QG-API-01).

Regenerates the committed OpenAPI document and the generated
TypeScript client from the live application and fails on any diff —
in either direction. A backend change without regeneration fails here;
a hand edit to either committed file fails here too.

Usage:
    uv run python scripts/check_api_drift.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Run both --check legs and report the combined verdict."""
    failures: list[str] = []
    for script in ("scripts/generate_openapi.py", "scripts/generate_ts_client.py"):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / script), "--check"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        sys.stdout.write(f"--- {script} --check ---" + "\n")
        sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stdout.write(proc.stderr)
        if proc.returncode != 0:
            failures.append(script)
    if failures:
        sys.stdout.write(
            f"API DRIFT: {', '.join(failures)} out of date; regenerate and commit." + "\n"
        )
        return 1
    sys.stdout.write(
        "API DRIFT: no changes (openapi.json and client.ts match the live app)." + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
