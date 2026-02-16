# SDK Behavior Contracts

Use these contracts to avoid regressions.

## Execution Surface
- Sync calls are the canonical execution path.
- Async wrappers should preserve behavior parity for retries and timeout forwarding where implemented.
- `run_prompt*`, `run_with_schema*`, `start_thread*`, and `resume*` should remain convenience wrappers over the core run/resume logic.

## Retry Engine
- Respect `RetryPolicy` fields in `models.py`.
- Jitter is bounded by `jitter_ratio` and applied around computed delay.
- `max_total_retry_seconds` caps cumulative retry waiting window.
- Timeout retries follow `retry_on_timeouts`.
- Retry filtering by exit code follows `retry_on_exit_codes` when provided.

## Timeout Contract
- Sync execution timeout is passed via method args (`timeout_seconds`).
- Timeout failures should be represented consistently in `CodexExecResult`.
- Error behavior must remain compatible with `raise_on_error` semantics.

## Live Startup Retry Contract
- Retry startup failures only:
  - process launch exceptions,
  - immediate startup exit during probe window.
- Do not auto-retry after returning a live handle.

## Session Store Contract
- Keep legacy support for map-shaped JSON (`{"name": "thread-id"}`).
- Persist schema v2 records with metadata and bounded history.
- Keep cross-process file locking behavior for JSON-backed store.
- Maintain compatibility of store interface methods (`get/set/delete/all` + record APIs).

## Telemetry Contract
- Emit structured events through `event_hook`.
- Hook invocation must be best-effort; exceptions from hook must be swallowed.
- Event payload should include operation context and lightweight run metadata.

## Public Export Contract
- Preserve expected exports in `codex_local_sdk/__init__.py`.
- If adding public symbols, update docs and examples accordingly.
