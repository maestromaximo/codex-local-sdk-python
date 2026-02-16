# SpawnCodex Python Local SDK

This repository includes a Python SDK-style wrapper for Codex **non-interactive local execution** (`codex exec`).

## What this gives you

- Reusable Python classes for Codex execution
- Support for plain output and JSONL event mode
- Live streaming mode using `subprocess.Popen`
- Async/`asyncio` API for sync and live flows
- Session/thread continuation via `codex exec resume`
- Pluggable session stores (in-memory + JSON file persistence)
- Turn completion status (`completed` / `failed` / `interrupted`)
- Schema-constrained runs (`--output-schema`)
- Built-in retry/backoff policy for sync execution
- Ready-to-run examples

Package: `codex_local_sdk`

## Install prerequisites

1. Install Codex CLI (`codex`) and authenticate it.
2. Use Python 3.10+.

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
    )
)
print(result.final_message)
```

## JSONL event mode

```python
result = client.run(
    CodexExecRequest(
        prompt="Summarize repo risks.",
        json_output=True,
    )
)
print(result.thread_id)
print(result.turn_status)
print(result.is_turn_completed)
print(result.final_message)
```

## Live mode (Popen streaming)

```python
live = client.run_live(CodexExecRequest(prompt="Analyze this repo"))
for event in live.iter_events():
    print(event.type)
result = live.wait()
print(result.final_message)
```

## Async API

```python
import asyncio
from codex_local_sdk import CodexExecRequest, CodexLocalClient


async def main() -> None:
    client = CodexLocalClient()
    result = await client.run_async(CodexExecRequest(prompt="Summarize this repo"))
    print(result.final_message)

    live = await client.run_live_async(CodexExecRequest(prompt="Stream events", json_output=True))
    async for event in live.iter_events():
        print(event.type)
    final = await live.wait()
    print(final.turn_status)


asyncio.run(main())
```

## Thread/session continuation

```python
session, first = client.start_thread("Analyze this repository.")
next_result = session.continue_prompt("Continue with step 1.")
print(session.session_id)
print(next_result.is_turn_completed)
```

## Persistent session store

```python
from codex_local_sdk import CodexLocalClient, JsonFileSessionStore

store = JsonFileSessionStore(".codex_sessions.json")
client = CodexLocalClient(session_store=store)

session, _ = client.start_thread("Start plan", session_name="plan")
result = client.resume("Continue", session_name="plan", last=False, json_output=True)
print(session.session_id, result.turn_status)
```

## Retry/backoff policy

```python
from codex_local_sdk import CodexExecRequest, CodexLocalClient, RetryPolicy

client = CodexLocalClient(
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_backoff_seconds=0.5,
        backoff_multiplier=2.0,
        max_backoff_seconds=4.0,
        # None means retry any non-zero exit code
        retry_on_exit_codes=None,
    )
)

result = client.run(CodexExecRequest(prompt="Do work"))
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

## Test

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```
