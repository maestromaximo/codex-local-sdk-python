---
name: codex-local-sdk
description: Use when working on this repository to build, extend, test, or document the Python Codex Local SDK (`codex_local_sdk`). Trigger for tasks involving client APIs, retries/backoff, timeouts, live streaming, thread/session persistence, telemetry hooks, examples, HTML docs, and CI/integration test workflows around `codex exec`.
---

# Codex Local SDK

## Overview
Use this skill to implement high-confidence changes in this repository with consistent API behavior, test coverage, and documentation updates.

## Quick Routing
Load only the references that match the task:

- API or behavior change: read `references/sdk-behavior-contracts.md`.
- File navigation or impact analysis: read `references/repo-navigation.md`.
- Implementation strategy: read `references/workflow-playbooks.md`.
- Testing and CI updates: read `references/testing-and-ci.md`.
- Official OpenAI links and citation policy: read `references/openai-codex-links.md`.

## Standard Workflow
1. Classify the request as one of: API behavior, retry/timeout/live, session persistence, observability, docs-only, or CI/testing.
2. Inspect only the minimum files needed for that request.
3. Implement changes in `codex_local_sdk/` and keep backward compatibility unless explicitly asked to break it.
4. Add or update tests under `tests/` to cover normal path and failure/edge path.
5. Run validation commands before finishing.
6. Update user-facing docs (`README.md`, `html documentation/`, examples) for any behavior/signature change.

## Non-Negotiable Invariants
- Keep sync and async APIs aligned where parity is intended.
- Keep live retries limited to startup failures; do not auto-retry after a live handle is returned.
- Preserve timeout semantics and error signaling for sync execution methods.
- Preserve session-store compatibility with legacy JSON mapping and schema v2 record format.
- Keep event hooks best-effort; hook exceptions must not break client execution.
- Do not introduce third-party dependencies unless explicitly requested.

## Use Bundled Scripts
- `scripts/quality_check.py`: run unit tests, syntax compile checks, and optional integration tests from repo root.
- `scripts/scan_sdk_surface.py`: print current public SDK surface and key client methods to help with docs and regressions.

## Use Bundled Assets
- `assets/new_example_template.py`: starter template for a new `examples/run_*.py` sample.
- `assets/new_test_template.py`: starter template for a new `tests/test_*.py` module.
- `assets/html_doc_page_template.html`: starter template for pages under `html documentation/`.

## Completion Checklist
1. Behavior implemented.
2. Tests added/updated and passing locally.
3. `README.md` and HTML docs synced if public behavior changed.
4. Any new or changed command examples verified.

## Escalation Rule
If a requested change conflicts with these invariants, call out the conflict explicitly and propose the narrowest safe alternative.
