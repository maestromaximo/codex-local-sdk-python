# Workflow Playbooks

## Playbook A: Add or Update Public Client API
1. Locate target methods in `codex_local_sdk/client.py`.
2. Confirm related wrappers (sync + async) and convenience entry points.
3. Implement behavior and keep existing call sites working unless explicitly asked otherwise.
4. Add/adjust tests for both success and failure paths.
5. Update `README.md` and HTML API docs.

## Playbook B: Retry, Timeout, or Live Execution Changes
1. Update retry/timeout/live logic in `client.py`.
2. Validate behavior against `references/sdk-behavior-contracts.md`.
3. Add tests in `tests/test_v2_hardening.py` and related sync/live test files.
4. Verify no retry occurs after live handle return.
5. Update usage docs where behavior changed.

## Playbook C: Session Persistence and Metadata
1. Edit `session_store.py` and any session-record update paths in `client.py`.
2. Preserve migration compatibility and bounded history behavior.
3. Test legacy-read and concurrent-write scenarios.
4. Update docs for record shape or persistence behavior changes.

## Playbook D: Observability and Telemetry
1. Add/modify event emission points in `client.py`.
2. Keep `CodexClientEvent` payload coherent and minimal.
3. Ensure hook exceptions are swallowed.
4. Add event-sequence assertions in tests.

## Playbook E: Docs-Only Work
1. Update `README.md` first.
2. Sync corresponding HTML docs pages.
3. Confirm example snippets still match real signatures/behavior.
4. Prefer concise changes over broad rewrites.

## Playbook F: New Example Script
1. Copy `assets/new_example_template.py` to `examples/run_<topic>.py`.
2. Replace placeholders with actual request and options.
3. Run the example if credentials/environment are available.
4. Reference the new example in `README.md` and relevant HTML page.
