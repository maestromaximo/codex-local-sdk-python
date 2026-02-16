# AGENTS.md

## Purpose
This file helps coding agents move quickly and safely in this repository.

Repository goal:
- Provide a Python SDK-style wrapper around Codex non-interactive CLI flows (`codex exec`).
- Provide practical examples, tests, and browsable HTML docs for the SDK.

## Repo Map
- `codex_local_sdk/`: main SDK package.
- `examples/`: runnable usage samples.
- `tests/`: unit tests (default).
- `tests/integration/`: real Codex CLI integration tests (env-gated).
- `documentation/`: curated notes from official OpenAI Codex docs.
- `html documentation/`: static documentation site for this SDK.
- `.github/workflows/`: CI definitions (`unit.yml`, `integration.yml`).

## Primary Entry Points
Read these first when making behavior changes:
1. `codex_local_sdk/client.py`
2. `codex_local_sdk/models.py`
3. `codex_local_sdk/session_store.py`
4. `codex_local_sdk/telemetry.py`
5. `README.md`

## SDK Architecture Notes
- Sync methods are the core execution path; async wrappers should maintain feature parity by delegating where appropriate.
- Retry behavior is centralized in client helpers (`_should_retry`, `_compute_retry_delay`, `_is_retryable_exception`).
- Timeout behavior for sync execution flows through `subprocess.run(..., timeout=...)`.
- Live runs (`run_live*`, `resume_live*`) only retry startup failures; never retry after a live handle is returned.
- Session persistence supports:
  - legacy map format (`{name: thread_id}`),
  - schema v2 record format with metadata and bounded history.
- Observability is callback-based via `event_hook` and `CodexClientEvent`; hook failures must never break execution.

## Working Conventions
- Keep dependencies standard-library only unless explicitly requested.
- Keep backward compatibility for public call sites unless explicitly requested.
- Prefer additive changes over breaking refactors.
- If a behavior change is user-visible, update:
  - `README.md`
  - relevant page(s) in `html documentation/`
  - tests

## Test Commands
Run from repo root:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Integration tests (real CLI, opt-in):

```bash
export CODEX_INTEGRATION=1
export CODEX_API_KEY=your_key_here  # optional if local Codex auth is already active
python3 -m unittest discover -s tests/integration -p "test_*.py"
```

Quick syntax sanity:

```bash
python3 -m py_compile codex_local_sdk/*.py tests/*.py tests/integration/*.py examples/*.py
```

## Change Playbooks

### 1) SDK behavior updates
- Update implementation in `codex_local_sdk/`.
- Extend or add targeted tests under `tests/`.
- Run full unit test command.
- Update `README.md` usage/API notes if signatures or behavior changed.

### 2) Session store changes
- Preserve legacy file compatibility.
- Preserve schema v2 shape and migration behavior.
- Keep bounded turn history semantics.
- Validate with session-store-focused unit tests.

### 3) Retry/timeout/live changes
- Ensure sync + async parity where intended.
- Verify timeout retry policy behavior (`retry_on_timeouts`).
- Verify live startup retry boundaries (startup-only).
- Add tests for both success path and edge/failure path.

### 4) Documentation changes
- Source-of-truth narrative: `README.md`.
- Keep static site pages in `html documentation/` aligned with current SDK API.
- Keep examples in `examples/` runnable and consistent with docs.

## Documentation Navigation
- Official-source notes live in `documentation/`.
- Start with:
  - `documentation/README.md`
  - `documentation/codex_core_docs.md`
  - `documentation/programmatic_integration.md`
  - `documentation/mcp_and_skills.md`
- If up-to-date OpenAI product/API guidance is required, use the `openai-docs` skill and OpenAI docs MCP tools first.

## CI Expectations
- Unit CI: `.github/workflows/unit.yml` on push and PR.
- Integration CI: `.github/workflows/integration.yml` manual dispatch only, requires `CODEX_API_KEY` secret.
- Do not make integration tests run unconditionally in default CI.

## Path Gotcha
- Directory name `html documentation/` contains a space.
- Quote it in shell commands, for example: `ls -la "html documentation"`.

## Definition of Done (for non-trivial changes)
1. Implementation updated.
2. Tests added/updated and passing locally.
3. `README.md` updated for user-visible behavior changes.
4. HTML docs updated when API/usage changed.
5. No unintended breaking changes.
