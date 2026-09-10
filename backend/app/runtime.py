"""Runtime provenance context (Phase 5, T-501).

Everything here is *computed at request time from the running process*:
no committed literals, no config-file results, no fabricated numbers
(INV-1). Values that have no backing store yet (dataset hash, model
versions, profile) are reported as absent — never invented — so health
truthfully reads ``degraded`` until T-401/T-502 land their stores.

Wall-clock appears only in response metadata (``computed_at``,
``duration_ms``), never inside a computation (CLAUDE.md § 5).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime
from typing import Final

from backend.app.schemas import CodeInfo, FormulaRegistryInfo, Meta
from backend.core.formulas import FORMULAS

API_VERSION: Final[str] = "v1"
SERVICE_NAME: Final[str] = "latentis"

_GIT_SHA_ENV: Final[str] = "LATENTIS_GIT_SHA"
_GIT_DIRTY_ENV: Final[str] = "LATENTIS_GIT_DIRTY"
_UNKNOWN_SHA: Final[str] = "unknown"


def utc_now_z() -> str:
    """Current UTC time as ISO-8601 with ``Z`` (metadata only)."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def new_request_id() -> str:
    """Fresh request identifier (opaque; carries no decision meaning)."""
    return uuid.uuid4().hex


def code_info() -> CodeInfo:
    """Identify the running code: env override, else git, else ``unknown``.

    ``LATENTIS_GIT_SHA`` / ``LATENTIS_GIT_DIRTY`` allow hermetic deployments
    (and deterministic tests) to state their identity without a worktree.
    Git failures degrade to ``unknown`` — introspection must never fault a
    health check (API_CONTRACT § 3: a health endpoint that cannot report ill
    health is useless).
    """
    override = os.environ.get(_GIT_SHA_ENV)
    if override:
        dirty_raw = os.environ.get(_GIT_DIRTY_ENV, "false").strip().lower()
        return CodeInfo(git_sha=override, dirty=dirty_raw in ("1", "true", "yes"))
    try:
        sha_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        status_proc = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return CodeInfo(git_sha=_UNKNOWN_SHA, dirty=False)
    sha = sha_proc.stdout.strip() or _UNKNOWN_SHA
    return CodeInfo(git_sha=sha, dirty=bool(status_proc.stdout.strip()))


def formula_registry_summary() -> FormulaRegistryInfo:
    """Count and content-hash the live formula registry (runtime-derived)."""
    entries = sorted(f"{fid}:{spec.expression}" for fid, spec in FORMULAS.items())
    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return FormulaRegistryInfo(entries=len(entries), hash=f"sha256:{digest}")


def build_meta(
    request_id: str,
    start_ns: int,
    *,
    dataset_hash: str | None = None,
    profile_id: str | None = None,
    profile_version: int | None = None,
    model_versions: dict[str, str] | None = None,
    code_sha: str | None = None,
) -> Meta:
    """Assemble the non-optional response metadata (API_CONTRACT § 1.1)."""
    if start_ns <= 0:
        start_ns = time.perf_counter_ns()
    duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
    return Meta(
        request_id=request_id,
        computed_at=utc_now_z(),
        dataset_hash=dataset_hash,
        profile_id=profile_id,
        profile_version=profile_version,
        model_versions=dict(model_versions) if model_versions else {},
        code_git_sha=code_sha if code_sha is not None else code_info().git_sha,
        duration_ms=duration_ms,
    )
