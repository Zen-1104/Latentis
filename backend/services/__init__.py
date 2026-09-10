"""Backend service package (Phase 5).

Orchestration between the numeric core, the formula registry, and
persistence. Services validate, retrieve, call authoritative
``backend.core`` functions, and map results to API schemas. They never
re-implement a scientific formula (ARCHITECTURE.md section 1).
"""

from __future__ import annotations
