# SpawnCodex Python Local SDK

[![PyPI Version](https://img.shields.io/pypi/v/codex-local-sdk-python.svg)](https://pypi.org/project/codex-local-sdk-python/)
[![Python Versions](https://img.shields.io/pypi/pyversions/codex-local-sdk-python.svg)](https://pypi.org/project/codex-local-sdk-python/)
[![Unit Tests](https://img.shields.io/github/actions/workflow/status/maestromaximo/codex-local-sdk-python/unit.yml?label=unit%20tests)](https://github.com/maestromaximo/codex-local-sdk-python/actions/workflows/unit.yml)
[![License](https://img.shields.io/github/license/maestromaximo/codex-local-sdk-python)](LICENSE)

This repository provides a Python SDK-style wrapper for Codex **non-interactive local execution** (`codex exec`).

## Project Policies

- Contributing guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Security policy: [`SECURITY.md`](SECURITY.md)
- License: [`LICENSE`](LICENSE) (MIT)

## What this gives you

- Sync and async APIs for Codex execution
- JSONL event parsing and live stream handles (sync + async)
- Resumable sessions (`codex exec resume`) with named session persistence
- Retry/backoff engine with jitter and timeout-aware retry controls
- Sync timeout controls on run/resume/start methods
- Structured observability hooks (`CodexClientEvent`)
- Schema-constrained output support (`--output-schema`)
- Unit tests plus real CLI integration test scaffolding

Package: `codex_local_sdk`

Published distribution: `codex-local-sdk-python`

## Install from PyPI

```bash
pip install codex-local-sdk-python
```

The Python import package remains:

```python
from codex_local_sdk import CodexLocalClient
```

## Packaged CLI utilities

After install, the package also includes:

- `codex-sdk skill` to copy `.agents/skills/codex-local-sdk-usage`
- `codex-sdk docs` to copy `codex-sdk-documentation/`

```bash
codex-sdk --help
codex-sdk skill
codex-sdk docs
```

## Prerequisites

1. Python 3.10+
2. Codex CLI installed (`codex`) and authenticated (or pass `CODEX_API_KEY` per call)

Official docs:
- Non-interactive mode: https://developers.openai.com/codex/noninteractive/
- CLI reference (`codex exec`): https://developers.openai.com/codex/cli/reference/#codex-exec

## Quick usage

```python
from codex_local_sdk import CodexExecRequest, CodexLocalClient, SandboxMode

client = CodexLocalClient()
result = client.run(
    CodexExecRequest(
        prompt="Summarize this repo in 5 bullets.",
        sandbox=SandboxMode.READ_ONLY,
    ),
    timeout_seconds=120,
)
print(result.final_message)
```

## Async API

```python
import asyncio
from codex_local_sdk import CodexExecRequest, CodexLocalClient


async def main() -> None:
    client = CodexLocalClient()

    result = await client.run_async(
        CodexExecRequest(prompt="Summarize this repository."),
        timeout_seconds=120,
    )
    print(result.final_message)

    live = await client.run_live_async(
        CodexExecRequest(prompt="Stream event types", json_output=True)
    )
    async for event in live.iter_events():
        print(event.type)
    final = await live.wait()
    print(final.turn_status)


asyncio.run(main())
```

## Retry/backoff policy (jitter + timeout behavior)

```python
from codex_local_sdk import CodexExecRequest, CodexLocalClient, RetryPolicy

client = CodexLocalClient(
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_backoff_seconds=0.5,
        backoff_multiplier=2.0,
        max_backoff_seconds=4.0,
        retry_on_exit_codes=None,      # retry any non-zero exit code
        jitter_ratio=0.2,              # +/-20% jitter
        max_total_retry_seconds=10.0,  # cap total retry window
        retry_on_timeouts=True,
    )
)

result = client.run(CodexExecRequest(prompt="Do work"), timeout_seconds=30)
```

## Persistent session store + metadata records

```python
from codex_local_sdk import CodexLocalClient, JsonFileSessionStore

store = JsonFileSessionStore(".codex_sessions.json")
client = CodexLocalClient(session_store=store)

session, _ = client.start_thread(
    "Create an initial plan",
    session_name="repo-plan",
    timeout_seconds=120,
)

result = client.resume(
    "Continue with concrete tasks",
    session_name="repo-plan",
    last=False,
    json_output=True,
    timeout_seconds=120,
)

record = client.get_session_record("repo-plan")
print(session.session_id, result.turn_status, record.turn_count if record else None)
```

## Observability hook

```python
from codex_local_sdk import CodexClientEvent, CodexExecRequest, CodexLocalClient


def on_event(event: CodexClientEvent) -> None:
    print(event.type, event.operation, event.attempt, event.return_code)


client = CodexLocalClient(event_hook=on_event)
client.run(CodexExecRequest(prompt="Analyze repo"), timeout_seconds=60)
```

## Schema-constrained output

```python
schema = {
    "type": "object",
    "properties": {"project_name": {"type": "string"}},
    "required": ["project_name"],
    "additionalProperties": False,
}

result = client.run_with_schema(
    prompt="Extract project metadata.",
    schema=schema,
    output_json_path="project_metadata.json",
    timeout_seconds=120,
)
```

## Examples

- `examples/run_simple.py`
- `examples/run_json_events.py`
- `examples/run_live_stream.py`
- `examples/run_thread_session.py`
- `examples/run_with_schema.py`
- `examples/run_async.py`
- `examples/run_persistent_session_store.py`

## Unit tests

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

## Integration tests (real Codex CLI)

```bash
export CODEX_INTEGRATION=1
export CODEX_API_KEY=your_key_here  # optional if local Codex auth session already exists
python3 -m unittest discover -s tests/integration -p "test_*.py"
```

CI workflows:
- `.github/workflows/unit.yml` runs on push/PR
- `.github/workflows/integration.yml` is manual (`workflow_dispatch`) and secret-gated

## Release Process

This repository supports PyPI publishing via GitHub Actions trusted publishing (`.github/workflows/publish-pypi.yml`).

1. Update version in:
   - `codex-local-sdk-python/pyproject.toml`
   - `codex-local-sdk-python/src/codex_sdk_python/__init__.py`
2. Commit and push to `main`.
3. Create and push a version tag:

```bash
git tag v0.1.2
git push origin v0.1.2
```

4. GitHub Actions builds and publishes automatically to PyPI.

If trusted publishing is not configured yet, set it in PyPI project settings:

- Owner: `maestromaximo`
- Repository: `codex-local-sdk-python`
- Workflow: `publish-pypi.yml`
- Environment: `pypi`
