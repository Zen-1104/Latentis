#!/usr/bin/env bash
# scripts/verify_reproducibility.sh — Gate: QG-REL-03 (INV-8)
# Contract: scripts/README.md, tests/QUALITY_GATES.md § QG-REL-03
#
# Stage 1: Regenerate dataset from seed, compare SHA-256 byte-wise against reference (T-210).
# Stage 2: Retrain, compare artifact hashes (Phase 4 / T-401).
# Stage 3: Re-score calibration split, compare metrics exactly (Phase 4 / T-402).
#
# Any drift blocks the tag (INV-8).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if command -v uv >/dev/null 2>&1; then
    exec uv run python scripts/verify_reproducibility.py "$@"
elif [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    exec "$REPO_ROOT/.venv/bin/python" scripts/verify_reproducibility.py "$@"
else
    exec python3 scripts/verify_reproducibility.py "$@"
fi
