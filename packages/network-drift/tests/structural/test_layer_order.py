"""Structural tests — AST-based import analysis to enforce layer ordering.

Layer order: types -> graph_build -> slice -> embed -> reduce -> score -> visualize -> cli

No layer may import from a layer to its right in this ordering.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

# Layer ordering (index = position; lower index = earlier in pipeline)
LAYER_ORDER = [
    "types",
    "graph_build",
    "slice",
    "embed",
    "reduce",
    "score",
    "visualize",
    "cli",
]

LAYER_INDEX = {layer: i for i, layer in enumerate(LAYER_ORDER)}
PACKAGE = "dprk_drift"


def _get_layer_from_path(path: Path) -> str | None:
    """Extract the layer name from a source file path."""
    parts = path.parts
    try:
        pkg_idx = parts.index("dprk_drift")
        if pkg_idx + 1 < len(parts):
            layer = parts[pkg_idx + 1]
            if layer in LAYER_INDEX:
                return layer
    except ValueError:
        pass
    return None


def _get_imports(filepath: Path) -> list[str]:
    """Extract all import module names from a Python file via AST."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _get_dprk_layers_imported(imports: list[str]) -> list[str]:
    """Filter import list to only dprk_drift layer names."""
    layers = []
    for imp in imports:
        parts = imp.split(".")
        if parts[0] == PACKAGE and len(parts) >= 2:
            layer = parts[1]
            if layer in LAYER_INDEX:
                layers.append(layer)
    return layers


def _find_src_files() -> list[Path]:
    """Find all Python source files in src/dprk_drift/."""
    project_root = Path(__file__).parent.parent.parent
    src_root = project_root / "src" / "dprk_drift"
    if not src_root.exists():
        return []
    return list(src_root.rglob("*.py"))


@pytest.mark.structural
class TestLayerOrder:
    def test_no_backward_imports(self):
        """Verify no layer imports from a later layer in the pipeline."""
        violations = []
        src_files = _find_src_files()

        for filepath in src_files:
            source_layer = _get_layer_from_path(filepath)
            if source_layer is None:
                continue

            imports = _get_imports(filepath)
            imported_layers = _get_dprk_layers_imported(imports)

            source_idx = LAYER_INDEX[source_layer]
            for imported_layer in imported_layers:
                imported_idx = LAYER_INDEX[imported_layer]
                if imported_idx > source_idx:
                    violations.append(
                        f"{filepath.name} (layer={source_layer}, idx={source_idx}) "
                        f"imports {imported_layer} (idx={imported_idx}) — BACKWARD IMPORT"
                    )

        if violations:
            raise AssertionError(
                f"Layer order violations detected:\n" + "\n".join(violations)
            )

    def test_types_layer_has_no_dprk_imports(self):
        """The types layer must not import from any other dprk_drift layer.

        __init__.py may re-export from dprk_drift.types itself — that is allowed.
        Non-__init__ files must not import from any other layer.
        """
        project_root = Path(__file__).parent.parent.parent
        types_dir = project_root / "src" / "dprk_drift" / "types"
        if not types_dir.exists():
            pytest.skip("types directory not found")

        for filepath in types_dir.rglob("*.py"):
            imports = _get_imports(filepath)
            dprk_layers = _get_dprk_layers_imported(imports)
            # Allow self-referential imports within the types layer
            disallowed = [layer for layer in dprk_layers if layer != "types"]
            assert disallowed == [], (
                f"types/{filepath.name} must not import from other dprk_drift layers, "
                f"but found: {disallowed}"
            )

    def test_cli_layer_imports_are_allowed(self):
        """CLI may import from any layer to its left (it is the last in the chain).

        __init__.py may re-export from dprk_drift.cli itself — that is allowed.
        """
        project_root = Path(__file__).parent.parent.parent
        cli_dir = project_root / "src" / "dprk_drift" / "cli"
        if not cli_dir.exists():
            pytest.skip("cli directory not found")

        cli_idx = LAYER_INDEX["cli"]
        for filepath in cli_dir.rglob("*.py"):
            imports = _get_imports(filepath)
            dprk_layers = _get_dprk_layers_imported(imports)
            for layer in dprk_layers:
                # Allow self-referential imports within the cli layer
                if layer == "cli":
                    continue
                assert LAYER_INDEX[layer] < cli_idx, (
                    f"cli/{filepath.name} imports {layer} which has index >= cli index"
                )

    def test_visualize_does_not_import_graph_build(self):
        """Visualize layer must not import graph_build (no raw graph logic in viz)."""
        project_root = Path(__file__).parent.parent.parent
        viz_dir = project_root / "src" / "dprk_drift" / "visualize"
        if not viz_dir.exists():
            pytest.skip("visualize directory not found")

        for filepath in viz_dir.rglob("*.py"):
            imports = _get_imports(filepath)
            dprk_layers = _get_dprk_layers_imported(imports)
            assert "graph_build" not in dprk_layers, (
                f"visualize/{filepath.name} must not import graph_build"
            )

    def test_all_layer_directories_exist(self):
        """All expected layer directories must exist."""
        project_root = Path(__file__).parent.parent.parent
        src_root = project_root / "src" / "dprk_drift"
        for layer in LAYER_ORDER:
            layer_dir = src_root / layer
            assert layer_dir.exists(), f"Layer directory missing: {layer_dir}"

    def test_all_layers_have_init(self):
        """Each layer directory must have an __init__.py file."""
        project_root = Path(__file__).parent.parent.parent
        src_root = project_root / "src" / "dprk_drift"
        for layer in LAYER_ORDER:
            init_file = src_root / layer / "__init__.py"
            assert init_file.exists(), f"Missing __init__.py in layer: {layer}"
