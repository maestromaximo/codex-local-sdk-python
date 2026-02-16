# Repo Navigation

## Core Layout
- `codex_local_sdk/`: Python package for SDK logic.
- `examples/`: runnable examples that should match current public APIs.
- `tests/`: unit tests.
- `tests/integration/`: real CLI tests (`CODEX_INTEGRATION=1`).
- `documentation/`: curated OpenAI Codex notes.
- `html documentation/`: static docs site for this SDK.
- `.github/workflows/`: CI workflows.

## Primary Code Hotspots
- `codex_local_sdk/client.py`
  - Request-to-command construction.
  - Sync execution and retry engine.
  - Live process handling (sync + async).
  - Thread/session continuation APIs.
  - Telemetry event emission.
- `codex_local_sdk/models.py`
  - Core request/result/event data models.
  - Retry policy contract.
- `codex_local_sdk/session_store.py`
  - In-memory and JSON file session stores.
  - Legacy migration and record schema behavior.
  - Cross-process lock behavior.
- `codex_local_sdk/telemetry.py`
  - `CodexClientEvent` schema.
- `codex_local_sdk/__init__.py`
  - Public exports.

## Tests by Concern
- `tests/test_codex_local_sdk.py`: base behavior.
- `tests/test_client_sync_extended.py`: sync execution details.
- `tests/test_client_live_extended.py`: live process/event behavior.
- `tests/test_async_retry_and_session_store.py`: async parity and store behavior.
- `tests/test_v2_hardening.py`: retry/timeout/session metadata/telemetry hardening.
- `tests/integration/test_codex_cli_integration.py`: real CLI integration.

## Docs to Keep in Sync
- `README.md`: source-of-truth usage and API notes.
- `html documentation/api-reference.html`: API surface reference.
- `html documentation/getting-started.html`: quick setup and first run.
- `html documentation/live-threads.html`: live and thread workflows.
- `html documentation/testing-and-quality.html`: test and CI guidance.

## Fast Change Mapping
- API signature change:
  - Update implementation, tests, README, API reference HTML, examples.
- Retry/timeout change:
  - Update client retry logic tests and hardening tests.
- Session store change:
  - Validate legacy migration and record APIs.
- CI workflow change:
  - Keep README and HTML testing docs aligned.
