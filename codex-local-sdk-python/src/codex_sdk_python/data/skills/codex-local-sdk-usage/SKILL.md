---
name: codex-local-sdk-usage
description: Use when Codex needs to write, wire, or troubleshoot Python code that consumes this repository's `codex_local_sdk` package (not modify SDK internals). Trigger for requests to call `CodexLocalClient`, run or resume threads, stream JSON events, configure retries and timeouts, use schema-constrained output, or persist named sessions.
---

# Codex Local SDK Usage

## Route Quickly
Load only the reference file needed for the task:

- Select an execution path: `references/task-routing.md`
- Check methods, request flags, and result fields: `references/sdk-api-cheatsheet.md`
- Debug failures, retries, and session issues: `references/guardrails-and-failure-modes.md`

## Execute Workflow
1. Run `scripts/preflight_check.py` to verify Python, package import, and `codex` CLI presence.
2. Run `scripts/scaffold_usage_template.py --list` and choose the closest template.
3. Run the scaffold command with `--template` and `--output`.
4. Replace placeholders (`prompt`, schema, paths, session names, retries) and keep signatures aligned with the API cheat sheet.
5. Run the generated script and inspect `CodexExecResult` (`return_code`, `turn_status`, `stderr`, `final_message`).
6. If execution fails, apply the guardrails reference and retry.

## Use Bundled Scripts
- `scripts/preflight_check.py`: print readiness checks with optional strict mode.
- `scripts/scaffold_usage_template.py`: copy a starter script from `assets/`.

## Use Bundled Templates
- `assets/template_sync_run.py`
- `assets/template_live_stream.py`
- `assets/template_thread_session.py`
- `assets/template_resume_named_session.py`
- `assets/template_async_run.py`
- `assets/template_schema_output.py`
- `assets/template_telemetry_and_retry.py`

## Keep Consumer Guardrails
- Set `timeout_seconds` for `run*` and `resume*` unless intentionally unbounded.
- Set `json_output=True` whenever you need structured events, `thread_id`, or `turn_status`.
- Catch `CodexExecFailedError` when `raise_on_error=True`; inspect `exc.result`.
- Pass `session_id` or `session_name`, never both.
- Treat live methods (`run_live*`, `resume_live*`) as startup-retry only; once a handle is returned, caller code owns interruption/retry logic.
- On Windows, if you hit `CodexError: ... [WinError 2]`, initialize with `CodexLocalClient(codex_bin="codex.cmd")`.