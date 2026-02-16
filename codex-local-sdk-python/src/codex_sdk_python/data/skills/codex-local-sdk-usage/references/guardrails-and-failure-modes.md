# Guardrails and Failure Modes

Use this file when generated consumer code fails or behaves unexpectedly.

## Handle Non-Zero Exits Explicitly
`CodexLocalClient` defaults to `raise_on_error=True`.

```python
from codex_local_sdk import CodexExecFailedError

try:
    result = client.run(request, timeout_seconds=90)
except CodexExecFailedError as exc:
    print(exc.result.return_code)
    print(exc.result.stderr)
```

Set `raise_on_error=False` only when caller logic intentionally handles failed results directly.

## Understand Timeout Behavior
- Sync command execution uses `subprocess.run(..., timeout=timeout_seconds)`.
- Timeout results are represented with return code `124`.
- Retries on timeout follow `RetryPolicy.retry_on_timeouts`.

## Tune Retries Pragmatically
`RetryPolicy` applies to sync command execution (`run`, `resume`, `run_with_schema`, etc.):
- `max_attempts`
- `initial_backoff_seconds`
- `backoff_multiplier`
- `max_backoff_seconds`
- `retry_on_exit_codes` (`None` means any non-zero)
- `jitter_ratio`
- `max_total_retry_seconds`
- `retry_on_timeouts`

Live methods only retry startup failures; they do not auto-retry after a live handle is returned.

## Keep Session Calls Valid
- Do not pass both `session_id` and `session_name`.
- For named persistence, configure `JsonFileSessionStore` at client construction.
- Use `last=False` when you want explicit session targeting instead of "last session" behavior.

## Use Structured Output Deliberately
- Set `json_output=True` when code depends on `events`, `thread_id`, or `turn_status`.
- Use `run_with_schema` for machine-parseable outputs instead of fragile free-text parsing.

## Observe Without Breaking Execution
`event_hook` failures are swallowed by the SDK. Keep hooks lightweight and side-effect-safe.

## Fast Triage Checklist
1. Confirm `codex` exists in `PATH`.
2. Confirm auth is available (`CODEX_API_KEY` or active local Codex auth).
3. Print `result.stderr` and `result.return_code`.
4. For event-dependent logic, verify `json_output=True`.
5. For resume flows, verify stored `session_name` and session store file path.
