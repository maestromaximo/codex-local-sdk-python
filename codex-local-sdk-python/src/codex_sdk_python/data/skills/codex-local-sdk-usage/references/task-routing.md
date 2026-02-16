# Task Routing

Map user intent to the right SDK entry point before writing code.

## Decision Table
| User intent | Use these methods | Suggested template | Key setting |
| --- | --- | --- | --- |
| One-shot prompt and final text | `CodexLocalClient.run` or `run_prompt` | `template_sync_run.py` | `timeout_seconds` |
| Require structured events and turn metadata | `run` with `CodexExecRequest(json_output=True)` | `template_sync_run.py` | `json_output=True` |
| Stream live events as they happen | `run_live` | `template_live_stream.py` | Iterate `live.iter_events()` then `live.wait()` |
| Continue multi-turn flow in one process | `start_thread` + `CodexThreadSession.continue_prompt` | `template_thread_session.py` | `start_thread` enforces JSON output |
| Resume thread later by logical name | `JsonFileSessionStore` + `resume(session_name=..., last=False)` | `template_resume_named_session.py` | Reuse stable `session_name` |
| Enforce JSON schema in assistant output | `run_with_schema` | `template_schema_output.py` | Provide strict schema and output path |
| Use asyncio end-to-end | `run_async`, `run_live_async`, `continue_prompt_async` | `template_async_run.py` | `asyncio.run(main())` |
| Add observability + retry policy | `CodexLocalClient(event_hook=..., retry_policy=...)` | `template_telemetry_and_retry.py` | Tune `RetryPolicy` |

## Session Strategy
- Use `session_id` for short-lived, in-memory flows.
- Use `session_name` with `JsonFileSessionStore` for cross-process continuation.
- Use `open_session(name)` when a session already exists and you want a `CodexThreadSession` handle.

## Fallback Rules
- If user needs only final text, avoid live mode.
- If user needs incremental progress or event-level control, choose live mode.
- If user requests "continue previous work" and no ID is provided, use named sessions.
- If user needs machine-readable output, prefer schema flow over post-hoc parsing.
