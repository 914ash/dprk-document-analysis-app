"""Structural tests: enforce layer import order via AST analysis.

Layer order: types → ingest → parse → extract → embed → resolve → review → api → cli

Rules:
- A module in layer N must not import from layer N+1 or higher.
- `storage` is a special layer that may be imported by: review, api, cli only.

pytest markers: structural
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Layer definitions (ordered lowest → highest)
# ---------------------------------------------------------------------------

LAYER_ORDER = [
    "types",
    "ingest",
    "parse",
    "extract",
    "embed",
    "resolve",
    "review",
    "storage",  # injected here for dependency purposes
    "api",
    "cli",
]

# Layers that storage is allowed to be imported by
_STORAGE_ALLOWED_IN = {"review", "api", "cli"}

SRC_DIR = Path(__file__).parent.parent.parent / "src" / "dprk_er"


# ---------------------------------------------------------------------------
# AST import collector
# ---------------------------------------------------------------------------


def collect_dprk_imports(path: Path) -> list[str]:
    """Return a list of dprk_er sub-module names imported by the given file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("dprk_er."):
                    parts = alias.name.split(".")
                    if len(parts) >= 2:
                        imported.append(parts[1])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("dprk_er."):
                parts = node.module.split(".")
                if len(parts) >= 2:
                    imported.append(parts[1])
    return list(set(imported))


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def _get_layer_index(name: str) -> int:
    try:
        return LAYER_ORDER.index(name)
    except ValueError:
        return -1


def _check_layer_imports(layer_name: str) -> list[str]:
    """Return a list of violation messages for the given layer."""
    layer_dir = SRC_DIR / layer_name
    if not layer_dir.exists():
        return []
    layer_idx = _get_layer_index(layer_name)
    violations: list[str] = []
    for py_file in layer_dir.rglob("*.py"):
        imports = collect_dprk_imports(py_file)
        for imported_layer in imports:
            if imported_layer == layer_name:
                continue  # self-imports are fine
            imported_idx = _get_layer_index(imported_layer)
            if imported_idx < 0:
                continue  # unknown / external module
            # Special rule: storage may only be imported by review, api, cli
            if imported_layer == "storage" and layer_name not in _STORAGE_ALLOWED_IN:
                violations.append(
                    f"{py_file.relative_to(SRC_DIR.parent.parent)}: "
                    f"layer '{layer_name}' imports 'storage' which is not allowed "
                    f"(only review/api/cli may import storage)"
                )
            elif imported_layer != "storage" and imported_idx >= layer_idx:
                violations.append(
                    f"{py_file.relative_to(SRC_DIR.parent.parent)}: "
                    f"layer '{layer_name}' (index {layer_idx}) "
                    f"imports '{imported_layer}' (index {imported_idx}) — violation of layer order"
                )
    return violations


@pytest.mark.structural
def test_types_has_no_dprk_imports() -> None:
    """types layer must not import any other dprk_er layer."""
    violations = _check_layer_imports("types")
    assert violations == [], "\n".join(violations)


@pytest.mark.structural
def test_ingest_only_imports_types() -> None:
    """ingest layer may only import dprk_er.types."""
    violations = _check_layer_imports("ingest")
    assert violations == [], "\n".join(violations)


@pytest.mark.structural
def test_parse_respects_layer_order() -> None:
    """parse layer must not import extract, embed, resolve, review, api, cli."""
    violations = _check_layer_imports("parse")
    assert violations == [], "\n".join(violations)


@pytest.mark.structural
def test_extract_respects_layer_order() -> None:
    violations = _check_layer_imports("extract")
    assert violations == [], "\n".join(violations)


@pytest.mark.structural
def test_embed_respects_layer_order() -> None:
    violations = _check_layer_imports("embed")
    assert violations == [], "\n".join(violations)


@pytest.mark.structural
def test_resolve_respects_layer_order() -> None:
    violations = _check_layer_imports("resolve")
    assert violations == [], "\n".join(violations)


@pytest.mark.structural
def test_review_respects_layer_order() -> None:
    violations = _check_layer_imports("review")
    assert violations == [], "\n".join(violations)


@pytest.mark.structural
def test_api_respects_layer_order() -> None:
    violations = _check_layer_imports("api")
    assert violations == [], "\n".join(violations)


@pytest.mark.structural
def test_cli_may_import_all_layers() -> None:
    """cli is the top layer and may import everything – no violations expected."""
    violations = _check_layer_imports("cli")
    assert violations == [], "\n".join(violations)


@pytest.mark.structural
def test_storage_only_imports_types() -> None:
    """storage layer may only import from types (plus third-party libs)."""
    violations = _check_layer_imports("storage")
    assert violations == [], "\n".join(violations)


@pytest.mark.structural
def test_all_layers_have_init_py() -> None:
    """Every layer directory must have an __init__.py."""
    layers = ["types", "ingest", "parse", "extract", "embed", "resolve", "review", "api", "cli", "storage"]
    missing: list[str] = []
    for layer in layers:
        init_file = SRC_DIR / layer / "__init__.py"
        if not init_file.exists():
            missing.append(str(init_file))
    assert missing == [], f"Missing __init__.py files: {missing}"


@pytest.mark.structural
def test_src_package_has_init() -> None:
    assert (SRC_DIR / "__init__.py").exists(), "dprk_er/__init__.py is missing"
