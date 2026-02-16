# SDK API Cheatsheet

Use this file to wire consumer code with correct classes and parameters.

## Core Imports
```python
from codex_local_sdk import (
    AsyncCodexLiveRun,
    CodexClientEvent,
    CodexExecFailedError,
    CodexExecRequest,
    CodexLocalClient,
    CodexThreadSession,
    JsonFileSessionStore,
    RetryPolicy,
    SandboxMode,
)
```

## Request Model
`CodexExecRequest` fields:
- `prompt`
- `cwd`
- `json_output`
- `model`
- `profile`
- `sandbox` (`SandboxMode.READ_ONLY`, `WORKSPACE_WRITE`, `DANGER_FULL_ACCESS`)
- `full_auto`
- `ephemeral`
- `skip_git_repo_check`
- `output_last_message_path`
- `output_schema_path`
- `images` (tuple of paths)
- `extra_args` (tuple of additional CLI args)

## Main Client Methods
- `run(request, api_key=None, timeout_seconds=None) -> CodexExecResult`
- `run_async(request, api_key=None, timeout_seconds=None) -> CodexExecResult`
- `run_live(request, api_key=None) -> CodexLiveRun`
- `run_live_async(request, api_key=None) -> AsyncCodexLiveRun`
- `run_prompt(prompt, **kwargs) -> CodexExecResult`
- `run_with_schema(prompt, schema, output_json_path=None, **kwargs) -> CodexExecResult`
- `start_thread(prompt, session_name=None, timeout_seconds=None, **request_overrides) -> (CodexThreadSession, CodexExecResult)`
- `resume(prompt, session_id=None, session_name=None, last=True, all_sessions=False, json_output=False, timeout_seconds=None) -> CodexExecResult`
- `resume_live(prompt, session_id=None, session_name=None, last=True, all_sessions=False) -> CodexLiveRun`
- `open_session(name) -> CodexThreadSession`

## Thread Session Methods
- `continue_prompt(prompt, json_output=True, timeout_seconds=None)`
- `continue_prompt_async(prompt, json_output=True, timeout_seconds=None)`
- `continue_live(prompt)`
- `continue_live_async(prompt)`
- `is_last_turn_complete`

## Result Fields
`CodexExecResult` includes:
- `ok`
- `return_code`
- `stdout`
- `stderr`
- `final_message`
- `thread_id`
- `turn_status`
- `usage`
- `events`
- `duration_seconds`
- `is_turn_completed`, `is_turn_failed`, `is_turn_terminal`

## Exception Types
- `CodexNotInstalledError`: `codex` binary not available.
- `CodexExecFailedError`: non-zero return code when `raise_on_error=True`.
- `CodexError`: base exception.
