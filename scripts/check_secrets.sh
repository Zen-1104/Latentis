#!/usr/bin/env bash
# scripts/check_secrets.sh — Gate: INV-10 (pre-commit, fast, full)
#
# Contract (scripts/README.md):
#   Scan the working tree and staged changes for credential patterns — private keys,
#   AWS/cloud key shapes, bearer tokens, password=, .env contents, connection strings
#   with embedded credentials.
#   Explicitly includes HUMAN_ACTIONS.md.
#   Exit non-zero on any match, printing file and line number but NOT the matched value.
#   Deterministic, runs standalone from repository root, serves Gate: INV-10.
#   Never bypassed: --no-verify is prohibited (docs/GIT_WORKFLOW.md).

set -euo pipefail

SHOW_HELP=0
SCAN_MODE="all"
EXPLICIT_FILES=()

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            SHOW_HELP=1
            ;;
        --staged)
            SCAN_MODE="staged"
            ;;
        --all)
            SCAN_MODE="all"
            ;;
        *)
            EXPLICIT_FILES+=("$arg")
            ;;
    esac
done

if [ "$SHOW_HELP" -eq 1 ]; then
    cat << 'EOF'
Usage: scripts/check_secrets.sh [options] [files...]

Gate: INV-10 — No secrets in the repository (CLAUDE.md § 1, scripts/README.md).

Scans for credential patterns:
  - Private keys (RSA, EC, DSA, OpenSSH, PGP)
  - Cloud provider API keys (AWS Access/Secret Keys, Google API keys)
  - Platform tokens (GitHub PAT/tokens, Slack tokens, Bearer tokens)
  - Connection strings with embedded credentials (Postgres, MySQL, Redis, MongoDB)
  - Hardcoded password/secret variable assignments
  - Unencrypted .env files

Outputs offending file and line number without printing the matched secret.

Options:
  -h, --help    Show this help message and exit (serves Gate: INV-10)
  --staged      Scan only git staged changes (plus HUMAN_ACTIONS.md)
  --all         Scan all tracked and working tree files (default)
  [files...]    Scan only the specified files (plus HUMAN_ACTIONS.md if staged/tracked)

Exit codes:
  0: Clean — no secrets detected
  1: Non-zero — one or more potential secrets detected
EOF
    exit 0
fi

# Locate Python 3
PYTHON_BIN=""
if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "ERROR: python3 is required to execute scripts/check_secrets.sh" >&2
    exit 1
fi

export SCAN_MODE
export EXPLICIT_FILES_STR="${EXPLICIT_FILES[*]:-}"

exec "$PYTHON_BIN" - "$@" << 'PYEOF'
import os
import re
import sys
import subprocess

# Rules and regex patterns for credential detection (INV-10)
SECRET_RULES = [
    (
        "private-key",
        "Private Key header",
        re.compile(r"-----BEGIN\s+(?:[A-Z0-9_-]+\s+)?PRIVATE\s+KEY(?:[A-Z0-9_-]+\s+)?-----")
    ),
    (
        "ssh-private-key",
        "OpenSSH/RSA private key",
        re.compile(r"ssh-(?:rsa|ed25519)\s+AAAA[0-9A-Za-z+/]{60,}")
    ),
    (
        "aws-access-key-id",
        "AWS Access Key ID",
        re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b")
    ),
    (
        "aws-secret-access-key",
        "AWS Secret Access Key assignment",
        re.compile(r"(?i)(?:aws_secret_access_key|aws_session_token)\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{30,}['\"]?")
    ),
    (
        "google-api-key",
        "Google API Key",
        re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")
    ),
    (
        "github-token",
        "GitHub Personal Access Token",
        re.compile(r"\b(?:gh[pours]_[0-9a-zA-Z]{30,40}|github_pat_[0-9a-zA-Z_]{82})\b")
    ),
    (
        "slack-token",
        "Slack Token",
        re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,}\b")
    ),
    (
        "bearer-token",
        "Bearer Token",
        re.compile(r"(?i)\bbearer\s+[a-zA-Z0-9_\-\.]{25,}\b")
    ),
    (
        "db-connection-string",
        "Database connection string with credentials",
        re.compile(r"\b(?:postgres|postgresql|mysql|mongodb|redis):\/\/[a-zA-Z0-9_\-\.]+:[^@\s/:]+@[a-zA-Z0-9_\-\.]+")
    ),
    (
        "hardcoded-password-assignment",
        "Hardcoded password or secret assignment",
        re.compile(r"(?i)\b(?:password|passwd|secret_key|api_key|apikey|auth_token)\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']")
    ),
]

IGNORE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".parquet", ".joblib",
    ".pdf", ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf", ".eot", ".pyc"
}

IGNORE_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
IGNORE_FILES = {"uv.lock", "package-lock.json", "scripts/check_secrets.sh"}

PLACEHOLDER_REGEX = re.compile(
    r"(?i)(?:placeholder|changeme|example|dummy|your[_-]|<[^>]+>|\$\{[^}]+\}|\{\{[^}]+\}|"
    r"['\"](?:password|secret|none|null|undefined|true|false)['\"])"
)

IGNORE_LINE_DIRECTIVE = re.compile(r"(?:#|//|<!--)\s*(?:secret-scan:\s*ignore|noqa:\s*secrets)")

def should_skip_file(path: str) -> bool:
    norm = os.path.normpath(path)
    if norm in IGNORE_FILES:
        return True
    parts = norm.split(os.sep)
    if any(p in IGNORE_DIRS for p in parts):
        return True
    _, ext = os.path.splitext(norm)
    if ext.lower() in IGNORE_EXTENSIONS:
        return True
    return False

def collect_files_to_scan() -> list[str]:
    mode = os.environ.get("SCAN_MODE", "all")
    explicit_str = os.environ.get("EXPLICIT_FILES_STR", "").strip()
    
    files: set[str] = set()

    if explicit_str:
        for f in explicit_str.split():
            if os.path.exists(f):
                files.add(f)
    elif mode == "staged":
        try:
            res = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                capture_output=True, text=True, check=True
            )
            for f in res.stdout.splitlines():
                f = f.strip()
                if f and os.path.exists(f):
                    files.add(f)
        except Exception:
            pass
    else:  # mode == "all"
        try:
            res = subprocess.run(
                ["git", "ls-files"],
                capture_output=True, text=True, check=True
            )
            for f in res.stdout.splitlines():
                f = f.strip()
                if f and os.path.exists(f):
                    files.add(f)
        except Exception:
            # Fallback to os.walk if git is not available
            for root, dirs, filenames in os.walk("."):
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
                for fn in filenames:
                    rel = os.path.relpath(os.path.join(root, fn), ".")
                    files.add(rel)

    # Invariant: HUMAN_ACTIONS.md is explicitly included if it exists (INV-10, scripts/README.md)
    if os.path.exists("HUMAN_ACTIONS.md"):
        files.add("HUMAN_ACTIONS.md")

    return sorted([f for f in files if not should_skip_file(f)])

def scan_file(filepath: str) -> list[tuple[str, int, str, str]]:
    violations = []
    
    # Check for unencrypted environment files
    basename = os.path.basename(filepath)
    if basename == ".env" or (basename.startswith(".env.") and not basename.endswith((".example", ".template", ".sample"))):
        violations.append((filepath, 1, "unencrypted-env-file", "Unencrypted .env file tracked or staged in repository"))
        return violations

    if not os.path.isfile(filepath):
        return violations

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
            for line_idx, line in enumerate(fh, start=1):
                if IGNORE_LINE_DIRECTIVE.search(line):
                    continue
                if PLACEHOLDER_REGEX.search(line):
                    continue
                
                for rule_id, rule_desc, pattern in SECRET_RULES:
                    if pattern.search(line):
                        violations.append((filepath, line_idx, rule_id, rule_desc))
    except Exception as err:
        print(f"Warning: Could not read file '{filepath}': {err}", file=sys.stderr)

    return violations

def main() -> int:
    files = collect_files_to_scan()
    all_violations = []

    for f in files:
        violations = scan_file(f)
        all_violations.extend(violations)

    if all_violations:
        print("=" * 72)
        print("GATE FAILURE: INV-10 — Potential secret(s) detected in repository!")
        print("Contract: No keys, tokens, credentials permitted (CLAUDE.md § 1, INV-10).")
        print("Note: Secret values are masked and not printed for security.")
        print("=" * 72)
        for filepath, line_num, rule_id, rule_desc in all_violations:
            print(f"[INV-10 VIOLATION] {filepath}:{line_num}: [{rule_id}] {rule_desc}")
        print("-" * 72)
        print(f"Total violations found: {len(all_violations)} in {len({v[0] for v in all_violations})} file(s).")
        print("Action required: Remove secret(s) immediately before committing.")
        print("=" * 72)
        return 1
    else:
        print(f"INV-10 secret scan passed: 0 secrets detected across {len(files)} file(s).")
        return 0

if __name__ == "__main__":
    sys.exit(main())
PYEOF
