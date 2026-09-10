"""Architectural boundary tests (TEST-ARCH-001, INV-7, DR-10).

Verifies the static import graph:
  - backend/core imports no datagen, no app, and no I/O module
  - datagen imports no backend.core model code
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

FORBIDDEN_CORE_IMPORTS = {
    "datagen",
    "backend.app",
    "app",
    "socket",
    "urllib",
    "requests",
    "httpx",
    "aiohttp",
    "sqlite3",
    "psycopg",
    "psycopg2",
    "sqlalchemy",
    "flask",
    "fastapi",
    "starlette",
}


def _extract_imported_modules(py_path: Path) -> set[str]:
    """Extract top-level and imported module names from a Python source file using AST."""
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)

    return modules


def _is_type_checking_guard(test: ast.AST) -> bool:
    """Detect `if TYPE_CHECKING:` / `if typing.TYPE_CHECKING:` guards."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _runtime_imported_modules(py_path: Path) -> set[str]:
    """Imports minus anything nested under a TYPE_CHECKING guard.

    The layering test reasons about runtime dependencies: an import nested
    under a TYPE_CHECKING guard creates no runtime edge and must not count
    as one (e.g. formulas.py annotates with TracedValue this way).
    """
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    modules: set[str] = set()

    def _visit(node: ast.AST, in_type_checking: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and _is_type_checking_guard(child.test):
                for sub in child.body:
                    _visit(sub, True)
                for sub in child.orelse:
                    _visit(sub, in_type_checking)
                continue
            if isinstance(child, ast.Import) and not in_type_checking:
                for alias in child.names:
                    modules.add(alias.name)
            elif isinstance(child, ast.ImportFrom) and not in_type_checking:
                if child.module:
                    modules.add(child.module)
            _visit(child, in_type_checking)

    _visit(tree, False)
    return modules


@pytest.mark.fast
def test_core_boundary_and_generator_isolation() -> None:
    """Static import graph: backend/core imports no datagen, no app, and no I/O module;

    datagen imports no backend.core model code (TEST-ARCH-001).
    """
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    core_dir = repo_root / "backend" / "core"
    datagen_dir = repo_root / "datagen"

    assert core_dir.is_dir(), f"Core directory not found at {core_dir}"
    assert datagen_dir.is_dir(), f"Datagen directory not found at {datagen_dir}"

    # 1. Inspect backend/core imports
    for py_file in core_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        imports = _extract_imported_modules(py_file)
        for imp in imports:
            # Check forbidden prefixes or exact matches
            for forbidden in FORBIDDEN_CORE_IMPORTS:
                assert not (imp == forbidden or imp.startswith(f"{forbidden}.")), (
                    f"Forbidden import '{imp}' found in backend/core file: {py_file.name}. "
                    f"Core must not import {forbidden}."
                )

    # 2. Inspect datagen imports (generator isolation)
    for py_file in datagen_dir.rglob("*.py"):
        imports = _extract_imported_modules(py_file)
        for imp in imports:
            assert not (imp == "backend.core" or imp.startswith("backend.core.")), (
                f"Forbidden import '{imp}' found in datagen file: {py_file.name}. "
                "Datagen must not import backend.core model code."
            )


EXTENDED_FORBIDDEN_CORE_IMPORTS = {
    "pydantic",
    "pydantic_settings",
    "pandas",
    "polars",
    "duckdb",
    "joblib",
    "jinja2",
    "uvicorn",
    "celery",
    "redis",
    "kafka",
    "boto3",
    "openai",
    "torch",
    "tensorflow",
    "jax",
    "matplotlib",
    "plotly",
}

ALLOWED_THIRD_PARTY_ROOTS = {"numpy", "scipy", "sklearn"}


def _import_roots(py_path: Path) -> set[str]:
    """Top-level root of every import in a file (first dotted component)."""
    return {mod.split(".")[0] for mod in _extract_imported_modules(py_path)}


@pytest.mark.fast
def test_core_forbids_frameworks_and_heavy_dependencies() -> None:
    """T-315: core imports no framework, validation, store, or ML-heavy module."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    core_dir = repo_root / "backend" / "core"
    checked = 0
    for py_file in sorted(core_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        checked += 1
        for imp in _extract_imported_modules(py_file):
            for forbidden in EXTENDED_FORBIDDEN_CORE_IMPORTS:
                assert not (
                    imp == forbidden or imp.startswith(f"{forbidden}.")
                ), f"Forbidden import '{imp}' in backend/core file: {py_file.name}."
    assert checked > 0, "No core modules found to check"


@pytest.mark.fast
def test_core_imports_allowlisted_roots_only() -> None:
    """T-315: every core import root is stdlib, numpy/scipy/sklearn, or core."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    core_dir = repo_root / "backend" / "core"
    allowed = set(sys.stdlib_module_names) | ALLOWED_THIRD_PARTY_ROOTS | {"backend", "__future__"}
    offenders: list[str] = []
    for py_file in sorted(core_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        for root in _import_roots(py_file):
            if root not in allowed:
                offenders.append(f"{py_file.name}: {root}")
    assert not offenders, "Non-allowlisted import roots in backend/core:\n" + "\n".join(offenders)


VERIFIED_T301_T310 = {
    "constants",
    "robust",
    "dpat",
    "multivariate",
    "attribution",
    "shape",
    "forecast",
    "conformal",
    "guard",
    "safety",
}

NEW_T311_T314 = {"risk", "recommend", "explain", "formulas", "traced"}

ALLOWED_INTRA_CORE: dict[str, set[str]] = {
    "constants": set(),
    "robust": {"constants"},
    "dpat": {"constants", "robust"},
    "multivariate": {"constants"},
    "attribution": {"constants", "robust", "dpat", "multivariate"},
    "shape": {"constants", "robust"},
    "forecast": {"constants"},
    "conformal": {"constants"},
    "cusum": {"constants"},
    "condition": {"constants"},
    "quality": {"constants", "robust"},
    "guard": {"constants", "robust"},
    "safety": {"constants"},
    "formulas": {"constants", "robust", "shape", "conformal", "multivariate"},
    "traced": {"constants", "formulas"},
    "risk": {"constants", "formulas", "safety", "attribution"},
    "recommend": {"constants", "safety", "attribution"},
    "explain": {"constants", "formulas", "traced"},
}


def _intra_core_edges(core_dir: Path) -> dict[str, set[str]]:
    """Map each core module to the sibling core modules it imports at runtime."""
    edges: dict[str, set[str]] = {}
    for py_file in sorted(core_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        module = py_file.stem
        deps: set[str] = set()
        for imp in _runtime_imported_modules(py_file):
            if imp == "backend.core":
                continue
            if imp.startswith("backend.core."):
                deps.add(imp.split(".")[2])
        edges[module] = deps
    return edges


@pytest.mark.fast
def test_core_internal_graph_acyclic_and_layered() -> None:
    """T-315: intra-core imports are acyclic and respect the layering table."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    core_dir = repo_root / "backend" / "core"
    edges = _intra_core_edges(core_dir)
    assert set(edges) == set(ALLOWED_INTRA_CORE), (
        "Layering table drifted from backend/core contents: "
        f"graph={sorted(edges)}, table={sorted(ALLOWED_INTRA_CORE)}"
    )
    for module, deps in edges.items():
        assert deps <= ALLOWED_INTRA_CORE[module], (
            f"backend/core/{module}.py imports {sorted(deps - ALLOWED_INTRA_CORE[module])} "
            "outside its allowed layer"
        )
        assert module not in deps, f"backend/core/{module}.py imports itself"
    for module in VERIFIED_T301_T310:
        assert edges[module] & NEW_T311_T314 == set(), (
            f"Verified module backend/core/{module}.py reaches new layers "
            f"{sorted(edges[module] & NEW_T311_T314)}; new code must not leak upstream"
        )
    visiting: set[str] = set()
    visited: set[str] = set()

    def _visit(node: str, stack: tuple[str, ...]) -> None:
        if node in visited:
            return
        if node in visiting:
            cycle = " -> ".join((*stack, node))
            raise AssertionError(f"Circular intra-core import: {cycle}")
        visiting.add(node)
        for dep in sorted(edges.get(node, set())):
            _visit(dep, (*stack, node))
        visiting.discard(node)
        visited.add(node)

    for module in sorted(edges):
        _visit(module, ())
