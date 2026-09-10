#!/usr/bin/env bash
# generate_demo_dataset.sh — Generate synthetic burn-in dataset artifacts (T-206)
# Contract: scripts/README.md
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== LATENTIS: Generating Demo Dataset Artifacts (T-206 / QG-DATA-01) ==="
uv run python scripts/generate_dataset.py "$@"
