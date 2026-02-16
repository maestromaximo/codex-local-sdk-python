from __future__ import annotations

import argparse
import shutil
import sys
from importlib.resources import abc, files
from pathlib import Path


def _copy_resource_tree(src: abc.Traversable, dst: Path, overwrite: bool) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            _copy_resource_tree(child, dst / child.name, overwrite=overwrite)
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {dst}")

    with src.open("rb") as src_handle, dst.open("wb") as dst_handle:
        shutil.copyfileobj(src_handle, dst_handle)


def _copy_skill(target_root: Path, overwrite: bool) -> Path:
    source = files("codex_sdk_python").joinpath("data", "skills", "codex-local-sdk-usage")
    destination = target_root / ".agents" / "skills" / "codex-local-sdk-usage"
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {destination}")
    _copy_resource_tree(source, destination, overwrite=overwrite)
    return destination


def _copy_docs(target_root: Path, overwrite: bool) -> Path:
    source_root = files("codex_sdk_python").joinpath("data", "docs")
    destination_root = target_root / "codex-sdk-documentation"
    documentation_destination = destination_root / "documentation"
    html_destination = destination_root / "html documentation"

    if documentation_destination.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {documentation_destination}")
    if html_destination.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {html_destination}")

    _copy_resource_tree(
        source_root.joinpath("documentation"),
        documentation_destination,
        overwrite=overwrite,
    )
    _copy_resource_tree(
        source_root.joinpath("html documentation"),
        html_destination,
        overwrite=overwrite,
    )
    return destination_root


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-sdk",
        description="Utilities for codex-local-sdk-python packaged assets.",
    )
    subparsers = parser.add_subparsers(dest="command")

    skill_parser = subparsers.add_parser(
        "skill",
        help="Copy the codex-local-sdk-usage skill into .agents/skills/.",
    )
    skill_parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd(),
        help="Root directory where .agents/skills/ will be created (default: current directory).",
    )
    skill_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )

    docs_parser = subparsers.add_parser(
        "docs",
        help="Copy documentation to codex-sdk-documentation/.",
    )
    docs_parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd(),
        help="Root directory where codex-sdk-documentation/ will be created (default: current directory).",
    )
    docs_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    target_root = args.output.resolve()
    overwrite = bool(args.force)

    try:
        if args.command == "skill":
            destination = _copy_skill(target_root, overwrite=overwrite)
            print(f"Copied skill to: {destination}")
            return 0

        if args.command == "docs":
            destination = _copy_docs(target_root, overwrite=overwrite)
            print(f"Copied documentation to: {destination}")
            return 0
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        print("Re-run with --force to overwrite.", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
