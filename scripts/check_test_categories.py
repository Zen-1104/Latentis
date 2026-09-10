#!/usr/bin/env python3
"""Gate: QG-CORE-01 · Fast

Test categories and oracle verification.

Verifies that:
1. Every entry in tests/tests.json declares one of the legitimate oracles
   (known-answer, property, behavioural, differential, adversarial, contract, measured).
2. No entry's oracle string is empty or contains "current output", "existing behaviour",
   "as implemented", or a snapshot reference for a numeric assertion.
3. The declared path resolves to a real test once tests exist (for Implemented,
   Verified, or Measured tests, or when --require-all-paths is passed).
4. Every public function in backend/core/** is named by at least one test whose
   category is known-answer, property, or differential (Gate QG-CORE-01).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Allowed categories per TEST_STRATEGY § 1 and tests.json schema
LEGITIMATE_CATEGORIES = frozenset(
    {
        "known-answer",
        "property",
        "behavioural",
        "differential",
        "adversarial",
        "contract",
        "measured",
    }
)

# Numeric categories where snapshot assertions are prohibited
NUMERIC_CATEGORIES = frozenset(
    {
        "known-answer",
        "property",
        "differential",
    }
)

# Banned phrases in oracle descriptions that indicate self-referential or invalid testing
BANNED_ORACLE_PHRASES = (
    "current output",
    "existing behaviour",
    "existing behavior",
    "as implemented",
)


@dataclass
class TestCategoriesReport:
    """Check results and metrics for test categories and oracles."""

    gate: str = "QG-CORE-01"
    passed: bool = True
    total_tests: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)
    status_counts: dict[str, int] = field(default_factory=dict)
    core_functions_found: int = 0
    core_functions_covered: int = 0
    invalid_categories: list[dict[str, str]] = field(default_factory=list)
    dishonest_oracles: list[dict[str, str]] = field(default_factory=list)
    unresolvable_paths: list[dict[str, str]] = field(default_factory=list)
    uncovered_core_functions: list[dict[str, str]] = field(default_factory=list)


def parse_register(json_path: Path) -> list[dict[str, Any]]:
    """Parse tests/tests.json and return the list of test entries."""
    if not json_path.is_file():
        raise FileNotFoundError(f"Test register not found: {json_path}")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    tests = data.get("tests", [])
    if not isinstance(tests, list):
        raise ValueError("Field 'tests' in tests.json must be a list")
    return tests


def extract_core_public_functions(core_dir: Path) -> list[dict[str, str]]:
    """Inspect backend/core/** Python files and extract all public function names."""
    if not core_dir.is_dir():
        return []

    functions: list[dict[str, str]] = []
    for py_file in sorted(core_dir.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    functions.append(
                        {
                            "name": node.name,
                            "file": str(py_file),
                            "line": str(node.lineno),
                        }
                    )
    return functions


def verify_test_categories(
    json_path: Path,
    core_dir: Path,
    root_dir: Path,
    require_all_paths: bool = False,
) -> TestCategoriesReport:
    """Execute all category, oracle honesty, path, and core coverage checks."""
    report = TestCategoriesReport()
    tests = parse_register(json_path)
    report.total_tests = len(tests)

    # Initialize counts
    for cat in sorted(LEGITIMATE_CATEGORIES):
        report.category_counts[cat] = 0

    numeric_tests: list[dict[str, Any]] = []

    for t in tests:
        tid = str(t.get("id", "UNKNOWN"))
        cat = str(t.get("cat", ""))
        oracle = str(t.get("oracle", ""))
        status = str(t.get("status", "Specified"))
        raw_path = str(t.get("path", ""))

        # Track status counts
        report.status_counts[status] = report.status_counts.get(status, 0) + 1

        # 1. Category validation
        if cat in LEGITIMATE_CATEGORIES:
            report.category_counts[cat] = report.category_counts.get(cat, 0) + 1
            if cat in NUMERIC_CATEGORIES:
                numeric_tests.append(t)
        else:
            report.invalid_categories.append(
                {
                    "test_id": tid,
                    "declared_category": cat,
                    "error": (
                        f"Invalid category '{cat}'; must be one of {sorted(LEGITIMATE_CATEGORIES)}"
                    ),
                }
            )

        # 2. Oracle honesty check
        oracle_stripped = oracle.strip()
        if not oracle_stripped:
            report.dishonest_oracles.append(
                {
                    "test_id": tid,
                    "error": "Oracle string is empty or whitespace only",
                }
            )
        else:
            oracle_lower = oracle_stripped.lower()
            for phrase in BANNED_ORACLE_PHRASES:
                if phrase in oracle_lower:
                    report.dishonest_oracles.append(
                        {
                            "test_id": tid,
                            "error": f"Oracle contains banned phrase: '{phrase}'",
                        }
                    )
                    break

            if "snapshot" in oracle_lower and cat in NUMERIC_CATEGORIES:
                report.dishonest_oracles.append(
                    {
                        "test_id": tid,
                        "error": f"Snapshot reference in numeric oracle ({cat}); banned by policy",
                    }
                )

        # 3. Path resolution check
        if not raw_path.strip():
            report.unresolvable_paths.append(
                {
                    "test_id": tid,
                    "path": raw_path,
                    "error": "Test path is empty",
                }
            )
        else:
            file_part = raw_path.split("::")[0]
            resolved_file = (root_dir / file_part).resolve()

            # Resolution is required for implemented tests or when --require-all-paths is set
            needs_resolution = require_all_paths or (
                status in ("Implemented", "Verified", "Measured")
            )

            if needs_resolution:
                if not resolved_file.is_file():
                    report.unresolvable_paths.append(
                        {
                            "test_id": tid,
                            "path": raw_path,
                            "error": f"Test file not found: {file_part} (status={status})",
                        }
                    )
                elif "::" in raw_path and resolved_file.suffix == ".py":
                    func_name = raw_path.split("::")[1]
                    file_content = resolved_file.read_text(encoding="utf-8")
                    if not re.search(rf"\bdef\s+{re.escape(func_name)}\b", file_content):
                        report.unresolvable_paths.append(
                            {
                                "test_id": tid,
                                "path": raw_path,
                                "error": f"Test function '{func_name}' not defined in {file_part}",
                            }
                        )

    # 4. QG-CORE-01: verify every public function in backend/core/** is named by a numeric test
    core_funcs = extract_core_public_functions(core_dir)
    report.core_functions_found = len(core_funcs)

    for func_info in core_funcs:
        fname = func_info["name"]
        # Look for function name in test path, id, or oracle of numeric tests
        matched = False
        for nt in numeric_tests:
            nt_path = str(nt.get("path", ""))
            nt_oracle = str(nt.get("oracle", ""))
            nt_id = str(nt.get("id", ""))
            if fname in nt_path or fname in nt_oracle or fname in nt_id:
                matched = True
                break
        if matched:
            report.core_functions_covered += 1
        else:
            report.uncovered_core_functions.append(
                {
                    "function": fname,
                    "file": func_info["file"],
                    "line": func_info["line"],
                    "error": (
                        "Public function in core not named by any "
                        "known-answer/property/differential test"
                    ),
                }
            )

    has_errors = bool(
        report.invalid_categories
        or report.dishonest_oracles
        or report.unresolvable_paths
        or report.uncovered_core_functions
    )
    report.passed = not has_errors
    return report


def format_report_text(report: TestCategoriesReport) -> str:
    """Format check report into a clear human-readable console string."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("  LATENTIS Test Categories & Oracles — Gate: QG-CORE-01")
    lines.append("=" * 70)
    lines.append(f"Total Tests in Register: {report.total_tests}")
    lines.append("Status Breakdown:")
    for status, count in sorted(report.status_counts.items()):
        lines.append(f"  - {status:12s}: {count:3d}")
    lines.append("Category Breakdown:")
    for cat, count in sorted(report.category_counts.items()):
        lines.append(f"  - {cat:14s}: {count:3d}")
    lines.append("-" * 70)
    lines.append(f"Core Functions Found (backend/core/**): {report.core_functions_found}")
    lines.append(
        "Core Functions Covered by Numeric Test: "
        f"{report.core_functions_covered} / {report.core_functions_found}"
    )
    lines.append("-" * 70)

    if report.invalid_categories:
        lines.append("[FAIL] Invalid test categories declared:")
        for inv in report.invalid_categories:
            lines.append(f"  - Test '{inv['test_id']}': {inv['error']}")

    if report.dishonest_oracles:
        lines.append("[FAIL] Invalid or dishonest oracle declarations:")
        for dis in report.dishonest_oracles:
            lines.append(f"  - Test '{dis['test_id']}': {dis['error']}")

    if report.unresolvable_paths:
        lines.append("[FAIL] Unresolvable test paths:")
        for unres in report.unresolvable_paths:
            lines.append(f"  - Test '{unres['test_id']}': {unres['error']}")

    if report.uncovered_core_functions:
        lines.append("[FAIL] Uncovered public core functions (Gate: QG-CORE-01):")
        for unc in report.uncovered_core_functions:
            lines.append(
                f"  - {unc['file']}:{unc['line']} function '{unc['function']}' "
                f"has no known-answer/property/differential test"
            )

    lines.append("-" * 70)
    if report.passed:
        lines.append(
            "[PASS] Gate QG-CORE-01 verified: all categories, oracles, and paths are valid."
        )
    else:
        lines.append("[FAIL] Gate QG-CORE-01 failed: violations detected.")
    lines.append("=" * 70)

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for check_test_categories.py."""
    parser = argparse.ArgumentParser(
        description="Verify test categories, oracles, and core coverage (Gate: QG-CORE-01).",
        epilog="Gate: QG-CORE-01 · Numerical Core Oracle Gate (tests/QUALITY_GATES.md § 4).",
    )
    parser.add_argument(
        "--tests-json",
        type=Path,
        default=Path("tests/tests.json"),
        help="Path to tests/tests.json (default: tests/tests.json)",
    )
    parser.add_argument(
        "--core-dir",
        type=Path,
        default=Path("backend/core"),
        help="Path to backend/core directory (default: backend/core)",
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path("."),
        help="Root repository path for path resolution (default: .)",
    )
    parser.add_argument(
        "--require-all-paths",
        action="store_true",
        help="Require all test paths to resolve on disk, even if status is Specified.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON report to stdout.",
    )

    args = parser.parse_args(argv)

    try:
        report = verify_test_categories(
            args.tests_json,
            args.core_dir,
            args.root_dir,
            require_all_paths=args.require_all_paths,
        )
    except (FileNotFoundError, ValueError) as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1

    if args.json_output:
        sys.stdout.write(json.dumps(asdict(report), indent=2) + "\n")
    else:
        sys.stdout.write(format_report_text(report))

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
