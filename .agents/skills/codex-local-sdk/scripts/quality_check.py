#!/usr/bin/env python3
"""Run repository quality checks for the Codex Local SDK project."""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_PY_COMPILE_TARGETS = [
    "codex_local_sdk/*.py",
    "tests/*.py",
    "tests/integration/*.py",
    "examples/*.py",
]


def run_command(cmd: list[str], cwd: Path) -> int:
    print(f"[run] {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(cwd), check=False)
    return completed.returncode


def expand_file_patterns(repo_root: Path, patterns: list[str]) -> list[str]:
    files: list[str] = []
    for pattern in patterns:
        for match in sorted(glob.glob(str(repo_root / pattern))):
            if os.path.isfile(match):
                files.append(os.path.relpath(match, str(repo_root)))
    return files


def resolve_repo_root(explicit_root: str | None) -> Path:
    if explicit_root:
        return Path(explicit_root).resolve()

    # Expected location: <repo>/.agents/skills/codex-local-sdk/scripts/quality_check.py
    return Path(__file__).resolve().parents[4]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SDK quality checks.")
    parser.add_argument("--repo-root", help="Explicit repository root path.")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use (default: current interpreter).",
    )
    parser.add_argument("--skip-unit", action="store_true", help="Skip unit tests.")
    parser.add_argument("--skip-compile", action="store_true", help="Skip py_compile checks.")
    parser.add_argument(
        "--include-integration",
        action="store_true",
        help="Run integration tests (requires CODEX_INTEGRATION=1 and Codex auth).",
    )
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    if not repo_root.exists():
        print(f"[error] Repo root not found: {repo_root}")
        return 2

    exit_code = 0

    if not args.skip_unit:
        unit_cmd = [
            args.python,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ]
        rc = run_command(unit_cmd, repo_root)
        if rc != 0:
            exit_code = rc

    if not args.skip_compile:
        compile_targets = expand_file_patterns(repo_root, DEFAULT_PY_COMPILE_TARGETS)
        if not compile_targets:
            print("[warn] No Python files matched compile patterns; skipping py_compile.")
            compile_cmd = []
        else:
            compile_cmd = [args.python, "-m", "py_compile", *compile_targets]
        if compile_cmd:
            rc = run_command(compile_cmd, repo_root)
            if rc != 0:
                exit_code = rc

    if args.include_integration:
        if os.getenv("CODEX_INTEGRATION") != "1":
            print("[warn] CODEX_INTEGRATION is not set to '1'. Integration tests may skip.")

        integration_cmd = [
            args.python,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests/integration",
            "-p",
            "test_*.py",
        ]
        rc = run_command(integration_cmd, repo_root)
        if rc != 0:
            exit_code = rc

    if exit_code == 0:
        print("[ok] Quality checks passed.")
    else:
        print(f"[error] Quality checks failed with exit code {exit_code}.")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
