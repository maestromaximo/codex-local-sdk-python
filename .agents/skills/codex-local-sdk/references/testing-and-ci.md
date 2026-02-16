# Testing and CI

## Local Commands
Unit suite:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Integration suite (real Codex CLI):

```bash
export CODEX_INTEGRATION=1
export CODEX_API_KEY=your_key_here  # optional if local auth session exists
python3 -m unittest discover -s tests/integration -p "test_*.py"
```

Syntax compile sanity:

```bash
python3 -m py_compile codex_local_sdk/*.py tests/*.py tests/integration/*.py examples/*.py
```

## Bundled Script
Use:

```bash
python3 .agents/skills/codex-local-sdk/scripts/quality_check.py
```

Optional integration run:

```bash
python3 .agents/skills/codex-local-sdk/scripts/quality_check.py --include-integration
```

## CI Workflows
- `.github/workflows/unit.yml`
  - runs on `push` and `pull_request`.
  - executes full unit discovery.
- `.github/workflows/integration.yml`
  - runs only on `workflow_dispatch`.
  - requires `CODEX_API_KEY` secret.
  - installs Codex CLI and runs integration tests.

## Test Authoring Guidance
- Prefer behavior-oriented assertions over implementation details.
- Include both positive and failure/edge cases for new features.
- For retry behavior, keep jitter deterministic in tests (`jitter_ratio=0.0` or patched RNG).
- For live behavior, explicitly test startup retry boundary vs post-handle behavior.
