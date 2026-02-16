#!/usr/bin/env python3
"""Copy a codex_local_sdk usage template from assets/ into a target path."""

from __future__ import annotations

import argparse
from pathlib import Path


def template_map(assets_dir: Path) -> dict[str, Path]:
    return {
        "sync": assets_dir / "template_sync_run.py",
        "live": assets_dir / "template_live_stream.py",
        "thread": assets_dir / "template_thread_session.py",
        "resume": assets_dir / "template_resume_named_session.py",
        "async": assets_dir / "template_async_run.py",
        "schema": assets_dir / "template_schema_output.py",
        "telemetry": assets_dir / "template_telemetry_and_retry.py",
    }


def list_templates(templates: dict[str, Path]) -> None:
    print("Available templates:")
    for key in sorted(templates):
        print(f"- {key}: {templates[key].name}")


def copy_template(source: Path, output: Path, force: bool) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Template not found: {source}")

    if output.exists() and not force:
        raise FileExistsError(f"Output already exists: {output}. Pass --force to overwrite.")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    assets_dir = script_dir.parent / "assets"
    templates = template_map(assets_dir)

    parser = argparse.ArgumentParser(description="Create a new consumer script from a usage template.")
    parser.add_argument("--list", action="store_true", help="List template keys and exit.")
    parser.add_argument("--template", choices=sorted(templates), help="Template key to copy.")
    parser.add_argument("--output", help="Destination file path.")
    parser.add_argument("--force", action="store_true", help="Overwrite output if it already exists.")
    args = parser.parse_args()

    if args.list:
        list_templates(templates)
        return 0

    if not args.template or not args.output:
        parser.error("--template and --output are required unless --list is used.")

    source = templates[args.template]
    destination = Path(args.output).expanduser().resolve()
    copy_template(source, destination, force=args.force)
    print(f"Wrote {destination} from {source.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
