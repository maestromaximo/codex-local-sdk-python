# AGENTS.md

## Scope
Applies to files under `codex_local_sdk/`.

## Purpose
This package is the Python local SDK wrapper for Codex non-interactive CLI workflows.

## Key Modules
- `codex_local_sdk/client.py`: primary orchestration and public client APIs.
- `codex_local_sdk/models.py`: request/result/event/retry models.
- `codex_local_sdk/session_store.py`: in-memory and JSON-backed session persistence.
- `codex_local_sdk/telemetry.py`: structured event payload for observability hook.
- `codex_local_sdk/__init__.py`: public exports.

## Change Guardrails
- Preserve backward compatibility for existing public method signatures unless explicitly requested.
- Keep sync and async API behavior aligned where intended.
- Live retry behavior is startup-only; do not introduce post-handle automatic retries.
- Timeout behavior for sync execution should remain explicit via method args (`timeout_seconds`).
- Session store changes must preserve legacy JSON migration support and schema v2 behavior.
- Event hooks are best-effort only; hook failures must not break SDK execution.

## Testing Expectations
After SDK changes, run:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

If changes touch integration flows, also validate with env-gated integration tests:

```bash
export CODEX_INTEGRATION=1
python3 -m unittest discover -s tests/integration -p "test_*.py"
```

## Documentation Sync
For public behavior changes, update:
1. `README.md`
2. Relevant examples under `examples/`
3. Relevant pages under `html documentation/`

## Completion Checklist
1. Implementation updated.
2. Tests added/updated for new behavior.
3. Unit tests pass.
4. User-facing docs/examples updated if needed.
