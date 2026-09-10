"""LATENTIS HTTP API layer (Phase 5, T-501).

FastAPI adapters around the authoritative numeric core. This package owns
the transport boundary only: envelopes, error shapes, and Pydantic mirrors
of core provenance types. It performs no decision arithmetic of its own —
every decision-bearing number is produced by ``backend.core`` and merely
carried here (ARCHITECTURE § 1, one computation path).
"""
