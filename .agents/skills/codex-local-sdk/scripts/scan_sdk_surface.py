#!/usr/bin/env python3
"""Print a concise SDK surface summary for docs and regression checks."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


def resolve_repo_root(explicit_root: str | None) -> Path:
    if explicit_root:
        return Path(explicit_root).resolve()

    # Expected location: <repo>/.agents/skills/codex-local-sdk/scripts/scan_sdk_surface.py
    return Path(__file__).resolve().parents[4]


def read_python_ast(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def extract_all_exports(init_py: Path) -> list[str]:
    tree = read_python_ast(init_py)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        values: list[str] = []
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                values.append(elt.value)
                        return values
    return []


def extract_class_methods(py_file: Path, class_name: str) -> list[str]:
    tree = read_python_ast(py_file)
    methods: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    if not child.name.startswith("_"):
                        methods.append(child.name)
    return methods


def build_surface(repo_root: Path) -> dict[str, Any]:
    pkg_root = repo_root / "codex_local_sdk"
    init_py = pkg_root / "__init__.py"
    client_py = pkg_root / "client.py"

    data = {
        "exports": extract_all_exports(init_py),
        "classes": {
            "CodexLocalClient": extract_class_methods(client_py, "CodexLocalClient"),
            "CodexThreadSession": extract_class_methods(client_py, "CodexThreadSession"),
            "CodexLiveRun": extract_class_methods(client_py, "CodexLiveRun"),
            "AsyncCodexLiveRun": extract_class_methods(client_py, "AsyncCodexLiveRun"),
        },
    }
    return data


def print_markdown(surface: dict[str, Any]) -> None:
    print("# SDK Surface Snapshot")
    print()
    print("## Public Exports")
    for name in surface["exports"]:
        print(f"- `{name}`")

    print()
    print("## Public Methods")
    for cls, methods in surface["classes"].items():
        print(f"### `{cls}`")
        if not methods:
            print("- (none found)")
            continue
        for method in methods:
            print(f"- `{method}`")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan SDK public surface.")
    parser.add_argument("--repo-root", help="Explicit repository root path.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    surface = build_surface(repo_root)

    if args.format == "json":
        print(json.dumps(surface, indent=2, sort_keys=True))
    else:
        print_markdown(surface)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
