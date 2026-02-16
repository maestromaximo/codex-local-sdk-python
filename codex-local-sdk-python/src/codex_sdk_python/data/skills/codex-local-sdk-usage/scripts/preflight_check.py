#!/usr/bin/env python3
"""Run quick environment checks before using codex_local_sdk in consumer scripts."""

from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


def _discover_repo_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / "codex_local_sdk").is_dir():
            return candidate
    return None


def _prepare_import_path() -> str | None:
    root = _discover_repo_root(Path(__file__).resolve().parent)
    if root is None:
        return None

    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root_str


def check_python() -> CheckResult:
    version = sys.version_info
    detail = f"{version.major}.{version.minor}.{version.micro}"
    if version >= (3, 10):
        return CheckResult("python", "PASS", detail)
    return CheckResult("python", "FAIL", f"{detail} (require >= 3.10)")


def check_sdk_import() -> CheckResult:
    repo_root = _prepare_import_path()
    try:
        module = importlib.import_module("codex_local_sdk")
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult("sdk_import", "FAIL", str(exc))

    exported = getattr(module, "__all__", ())
    detail = f"import ok; exports={len(tuple(exported))}"
    if repo_root:
        detail = f"{detail}; repo_root={repo_root}"
    return CheckResult("sdk_import", "PASS", detail)


def check_codex_cli() -> CheckResult:
    codex_path = shutil.which("codex")
    if not codex_path:
        return CheckResult("codex_cli", "WARN", "`codex` not found in PATH")

    try:
        completed = subprocess.run(
            [codex_path, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult("codex_cli", "WARN", f"found at {codex_path}; version probe failed: {exc}")

    version_text = (completed.stdout or completed.stderr or "").strip() or "unknown version"
    return CheckResult("codex_cli", "PASS", f"{codex_path}; {version_text}")


def check_auth_hint() -> CheckResult:
    if os.environ.get("CODEX_API_KEY"):
        return CheckResult("auth", "PASS", "CODEX_API_KEY is set")
    return CheckResult("auth", "WARN", "CODEX_API_KEY not set (ok if local Codex auth session is active)")


def render(results: list[CheckResult]) -> int:
    print("SDK consumer preflight")
    print("======================")
    for result in results:
        print(f"[{result.status}] {result.name}: {result.detail}")

    failed = any(r.status == "FAIL" for r in results)
    warned = any(r.status == "WARN" for r in results)

    if failed:
        print("\nResult: not ready (hard failures detected)")
        return 2
    if warned:
        print("\nResult: usable with warnings")
        return 1

    print("\nResult: ready")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local readiness for codex_local_sdk consumer scripts.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when warnings are present.",
    )
    args = parser.parse_args()

    results = [
        check_python(),
        check_sdk_import(),
        check_codex_cli(),
        check_auth_hint(),
    ]

    code = render(results)
    if code == 1 and not args.strict:
        return 0
    return code


if __name__ == "__main__":
    raise SystemExit(main())
