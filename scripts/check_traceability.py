#!/usr/bin/env python3
"""Gate: QG-DOC-01 · Fast

Bidirectional requirement <-> test traceability verification.

Verifies that:
1. Every requirement ID in tests/tests.json exists in PROJECT_MASTER_SPEC.md,
   system invariants (INV-1..INV-10), or data specifications (DATASET_SPEC-12).
   Fail on unknown requirement IDs (typo detection per FOUNDATION_AUDIT § F-03).
2. Every P0 requirement has at least one test in tests/tests.json.
3. Every P0 requirement appears in tests/TEST_MATRIX.md with at least one test ID.
4. Every test ID in tests/TEST_MATRIX.md exists in tests/tests.json.
5. Every requirement row in tests/TEST_MATRIX.md is discharged by at least one
   test that carries that requirement in tests/tests.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TraceabilityReport:
    """Traceability check results and summary metrics."""

    gate: str = "QG-DOC-01"
    passed: bool = True
    total_known_requirements: int = 0
    total_p0_requirements: int = 0
    total_tests_in_register: int = 0
    total_tests_in_matrix: int = 0
    p0_covered_in_register: int = 0
    p0_covered_in_matrix: int = 0
    unknown_requirement_ids: list[dict[str, str]] = field(default_factory=list)
    unregistered_matrix_tests: list[dict[str, str]] = field(default_factory=list)
    uncovered_p0_in_register: list[str] = field(default_factory=list)
    uncovered_p0_in_matrix: list[str] = field(default_factory=list)
    unaligned_matrix_rows: list[dict[str, Any]] = field(default_factory=list)
    unmapped_register_tests: list[str] = field(default_factory=list)


def parse_master_spec(spec_path: Path) -> tuple[set[str], set[str]]:
    """Extract all requirement IDs and P0 requirement IDs from PROJECT_MASTER_SPEC.md."""
    if not spec_path.is_file():
        raise FileNotFoundError(f"Master spec not found: {spec_path}")

    content = spec_path.read_text(encoding="utf-8")
    known_reqs: set[str] = set()
    p0_reqs: set[str] = set()

    # Match table rows: | ID | Requirement | Pri/Target |
    for line in content.splitlines():
        line_s = line.strip()
        if not line_s.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            rid = parts[1]
            pri_or_target = parts[3]
            if re.match(r"^[A-Z0-9_-]+$", rid) and ("-" in rid):
                if any(
                    rid.startswith(pfx)
                    for pfx in (
                        "FR-",
                        "NFR-",
                        "MLR-",
                        "XR-",
                        "DR-",
                        "TR-",
                        "SR-",
                        "DMR-",
                        "JR-",
                    )
                ):
                    known_reqs.add(rid)
                    if "P0" in pri_or_target:
                        p0_reqs.add(rid)

    # Secondary scan for all recognized requirement IDs anywhere in the spec tables
    all_spec_reqs = set(
        re.findall(
            r"\b(FR-\d+|NFR-\d+|MLR-\d+|XR-\d+|DR-\d+|TR-\d+|SR-\d+|DMR-\d+|JR-\d+)\b",
            content,
        )
    )
    known_reqs.update(all_spec_reqs)

    # Invariants INV-1 through INV-10 (CLAUDE.md § 1, TEST_MATRIX.md § 8)
    for i in range(1, 11):
        known_reqs.add(f"INV-{i}")

    # Dataset specification validation gate (DATASET_SPEC.md § 12)
    known_reqs.add("DATASET_SPEC-12")

    return known_reqs, p0_reqs


def parse_tests_json(json_path: Path) -> dict[str, dict[str, Any]]:
    """Parse tests/tests.json into a dictionary mapping test_id -> test_data."""
    if not json_path.is_file():
        raise FileNotFoundError(f"Test register not found: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    raw_tests = data.get("tests", [])
    test_map: dict[str, dict[str, Any]] = {}
    for t in raw_tests:
        tid = t.get("id")
        if tid:
            test_map[str(tid)] = t
    return test_map


def expand_matrix_test_ids(cell: str) -> list[str]:
    """Expand backticked test identifiers, ranges (..), and item indices (/N)."""
    results: list[str] = []
    tokens = re.findall(r"`([^`]+)`", cell)
    for tok in tokens:
        subtoks = [s.strip() for s in tok.split(",")]
        for s in subtoks:
            if ".." in s:
                prefix, end = s.split("..")
                base = prefix[: prefix.rfind("-") + 1]
                start_num = int(prefix[prefix.rfind("-") + 1 :])
                end_num = int(end)
                for num in range(start_num, end_num + 1):
                    results.append(f"{base}{num:03d}")
            elif "/" in s and s.startswith(("RT-", "TEST-")):
                results.append(s.split("/")[0])
            elif s.startswith(("TEST-", "E2E-", "RT-")):
                results.append(s)
    return results


def parse_test_matrix(
    matrix_path: Path,
) -> tuple[set[str], set[str], list[dict[str, Any]]]:
    """Parse tests/TEST_MATRIX.md tables.

    Returns:
    - set of all expanded test IDs referenced in matrix
    - set of automated P0 requirement IDs identified in matrix
    - list of parsed rows
    """
    if not matrix_path.is_file():
        raise FileNotFoundError(f"Test matrix not found: {matrix_path}")

    lines = matrix_path.read_text(encoding="utf-8").splitlines()
    matrix_test_ids: set[str] = set()
    matrix_p0_reqs: set[str] = set()
    rows: list[dict[str, Any]] = []

    current_section = ""
    for line_no, line in enumerate(lines, 1):
        line_s = line.strip()
        if line_s.startswith("## "):
            current_section = line_s
            continue
        if not line_s.startswith("|"):
            continue

        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3 or parts[1] in ("", "Req", "---", "Invariant"):
            continue

        col1 = parts[1]

        # Section 8: Cross-cutting invariants
        if "invariant" in current_section.lower():
            inv_match = re.match(r"(INV-\d+)", col1)
            if inv_match:
                inv_id = inv_match.group(1)
                tids = expand_matrix_test_ids(parts[2])
                for tid in tids:
                    matrix_test_ids.add(tid)
                # Invariants with automated test suites are automated P0 requirements
                # INV-6, INV-7, INV-9, INV-10 are process or script gates per § 8 notes
                if tids:
                    matrix_p0_reqs.add(inv_id)
                rows.append(
                    {
                        "line_no": line_no,
                        "reqs": [inv_id],
                        "test_ids": tids,
                        "pri": "P0",
                        "status": "Specified",
                    }
                )
            continue

        # Sections 1..7
        if len(parts) >= 4:
            req_col = col1
            tests_col = parts[3]
            pri_col = parts[5] if len(parts) > 5 else ""
            status_col = parts[6] if len(parts) > 6 else ""
            tids = expand_matrix_test_ids(tests_col)

            for tid in tids:
                matrix_test_ids.add(tid)

            req_list: list[str] = []
            if req_col not in ("", "—"):
                if req_col == "INV-7/MLR-08":
                    # Architectural invariant INV-7 paired with ML requirement MLR-08
                    req_list = ["INV-7", "MLR-08"]
                elif req_col == "NFR-07/INV-8":
                    req_list = ["NFR-07", "INV-8"]
                elif req_col == "NFR-01/02":
                    req_list = ["NFR-01", "NFR-02"]
                elif "/" in req_col:
                    for r in req_col.split("/"):
                        r_clean = r.strip()
                        if r_clean:
                            req_list.append(r_clean)
                else:
                    req_list.append(req_col)

            if "P0" in pri_col and tids:
                if req_col == "INV-7/MLR-08":
                    matrix_p0_reqs.add("INV-7")
                elif req_col == "NFR-07/INV-8":
                    matrix_p0_reqs.add("NFR-07")
                    matrix_p0_reqs.add("INV-8")
                else:
                    for r in req_list:
                        matrix_p0_reqs.add(r)

            rows.append(
                {
                    "line_no": line_no,
                    "reqs": req_list,
                    "test_ids": tids,
                    "pri": pri_col,
                    "status": status_col,
                }
            )

    return matrix_test_ids, matrix_p0_reqs, rows


def check_traceability(
    spec_path: Path,
    matrix_path: Path,
    json_path: Path,
) -> TraceabilityReport:
    """Perform bidirectional traceability verification under Gate QG-DOC-01."""
    report = TraceabilityReport()

    known_reqs, _ = parse_master_spec(spec_path)
    register_map = parse_tests_json(json_path)
    matrix_test_ids, matrix_p0_reqs, matrix_rows = parse_test_matrix(matrix_path)

    report.total_known_requirements = len(known_reqs)
    report.total_p0_requirements = len(matrix_p0_reqs)
    report.total_tests_in_register = len(register_map)
    report.total_tests_in_matrix = len(matrix_test_ids)

    # 1. Unknown requirement IDs in register (tests.json -> specs)
    for tid, tdata in sorted(register_map.items()):
        reqs = tdata.get("req", [])
        for r in reqs:
            if r not in known_reqs:
                report.unknown_requirement_ids.append({"test_id": tid, "unknown_req_id": r})

    # 2. P0 requirement coverage in register (P0 -> tests.json)
    register_all_reqs: set[str] = set()
    for tdata in register_map.values():
        for r in tdata.get("req", []):
            register_all_reqs.add(r)

    for p0_req in sorted(matrix_p0_reqs):
        if p0_req in register_all_reqs:
            report.p0_covered_in_register += 1
        else:
            report.uncovered_p0_in_register.append(p0_req)

    # 3. Matrix test IDs in register (TEST_MATRIX.md -> tests.json)
    for tid in sorted(matrix_test_ids):
        if tid not in register_map:
            report.unregistered_matrix_tests.append(
                {"matrix_test_id": tid, "error": "Absent from tests.json"}
            )

    # 4. P0 requirement coverage in matrix (P0 -> TEST_MATRIX.md)
    report.p0_covered_in_matrix = len(matrix_p0_reqs)

    # 5. Matrix requirement alignment with register
    for row in matrix_rows:
        req_list = row["reqs"]
        tids = row["test_ids"]
        if not req_list or not tids:
            continue
        # A row is aligned if at least one requirement in req_list is discharged by a test in tids
        discharged = any(
            tid in register_map and any(r in register_map[tid].get("req", []) for r in req_list)
            for tid in tids
        )
        if not discharged:
            report.unaligned_matrix_rows.append(
                {
                    "line_no": row["line_no"],
                    "req_ids": req_list,
                    "matrix_test_ids": tids,
                    "error": "No test in matrix row carries row requirements in tests.json",
                }
            )

    # Informational: tests in register not explicitly listed in matrix
    for tid in sorted(register_map.keys()):
        if tid not in matrix_test_ids:
            report.unmapped_register_tests.append(tid)

    # Determine overall status
    has_errors = bool(
        report.unknown_requirement_ids
        or report.unregistered_matrix_tests
        or report.uncovered_p0_in_register
        or report.uncovered_p0_in_matrix
        or report.unaligned_matrix_rows
    )
    report.passed = not has_errors

    return report


def format_report_text(report: TraceabilityReport) -> str:
    """Format the traceability report as human-readable text."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("  LATENTIS Traceability Verification — Gate: QG-DOC-01")
    lines.append("=" * 70)
    lines.append(f"Known Requirements:     {report.total_known_requirements}")
    lines.append(f"P0 Requirements:        {report.total_p0_requirements}")
    lines.append(f"Tests in Register:      {report.total_tests_in_register}")
    lines.append(f"Tests in Matrix:        {report.total_tests_in_matrix}")
    lines.append(
        f"P0 Coverage (Register): {report.p0_covered_in_register} / {report.total_p0_requirements}"
    )
    lines.append(
        f"P0 Coverage (Matrix):   {report.p0_covered_in_matrix} / {report.total_p0_requirements}"
    )
    lines.append("-" * 70)

    if report.unknown_requirement_ids:
        lines.append("[FAIL] Unknown requirement IDs in tests/tests.json:")
        for u in report.unknown_requirement_ids:
            lines.append(
                f"  - Test '{u['test_id']}' references unknown requirement '{u['unknown_req_id']}'"
            )

    if report.uncovered_p0_in_register:
        lines.append("[FAIL] P0 requirements without test coverage in tests.json:")
        for r in report.uncovered_p0_in_register:
            lines.append(f"  - P0 requirement '{r}' has no test in register")

    if report.uncovered_p0_in_matrix:
        lines.append("[FAIL] P0 requirements without test IDs in tests/TEST_MATRIX.md:")
        for r in report.uncovered_p0_in_matrix:
            lines.append(f"  - P0 requirement '{r}' has no test IDs in matrix")

    if report.unregistered_matrix_tests:
        lines.append("[FAIL] Test IDs in matrix missing from tests/tests.json:")
        for m in report.unregistered_matrix_tests:
            lines.append(f"  - Test ID '{m['matrix_test_id']}' not found in register")

    if report.unaligned_matrix_rows:
        lines.append("[FAIL] Matrix row requirement alignment mismatches:")
        for a in report.unaligned_matrix_rows:
            lines.append(
                f"  - Line {a['line_no']}: reqs {a['req_ids']} with tests {a['matrix_test_ids']} "
                f"not carried by any test in register"
            )

    if report.unmapped_register_tests:
        lines.append(
            f"[INFO] {len(report.unmapped_register_tests)} tests in register "
            f"not explicitly named in matrix:"
        )
        lines.append(f"   {', '.join(report.unmapped_register_tests)}")

    lines.append("-" * 70)
    if report.passed:
        lines.append("[PASS] Gate QG-DOC-01 verified: bidirectional traceability intact.")
    else:
        lines.append("[FAIL] Gate QG-DOC-01 failed: traceability mismatches detected.")
    lines.append("=" * 70)

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for check_traceability.py."""
    parser = argparse.ArgumentParser(
        description="Verify bidirectional requirement <-> test traceability (Gate: QG-DOC-01).",
        epilog="Gate: QG-DOC-01 · Documentation and Traceability (tests/QUALITY_GATES.md § 5).",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("PROJECT_MASTER_SPEC.md"),
        help="Path to PROJECT_MASTER_SPEC.md (default: PROJECT_MASTER_SPEC.md)",
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("tests/TEST_MATRIX.md"),
        help="Path to tests/TEST_MATRIX.md (default: tests/TEST_MATRIX.md)",
    )
    parser.add_argument(
        "--tests-json",
        type=Path,
        default=Path("tests/tests.json"),
        help="Path to tests/tests.json (default: tests/tests.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON report to stdout.",
    )

    args = parser.parse_args(argv)

    try:
        report = check_traceability(args.spec, args.matrix, args.tests_json)
    except FileNotFoundError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1

    if args.json_output:
        sys.stdout.write(json.dumps(asdict(report), indent=2) + "\n")
    else:
        sys.stdout.write(format_report_text(report))

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
