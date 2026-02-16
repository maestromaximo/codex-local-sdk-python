# Contributing

Thanks for contributing to `codex-local-sdk-python`.

## Development Setup

1. Fork and clone the repository.
2. Use Python 3.10+.
3. Ensure the `codex` CLI is installed if you plan to run integration tests.

## Local Validation

Run from repository root:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
python3 -m py_compile codex_local_sdk/*.py tests/*.py tests/integration/*.py examples/*.py
```

Integration tests are optional and require explicit opt-in:

```bash
export CODEX_INTEGRATION=1
export CODEX_API_KEY=your_key_here  # optional if local Codex auth is active
python3 -m unittest discover -s tests/integration -p "test_*.py"
```

## Pull Request Guidelines

1. Keep backward compatibility for public SDK call sites unless a breaking change is explicitly planned.
2. Keep sync and async behavior aligned where parity is intended.
3. Add or update tests for behavior changes.
4. Update documentation when user-visible behavior changes:
   - `README.md`
   - `html documentation/`
   - examples in `examples/` when relevant
5. Keep dependencies standard-library only unless explicitly discussed.

## Reporting Bugs

Please open an issue with:

- environment details (`python --version`, OS, Codex CLI version)
- minimal reproduction
- expected behavior
- actual behavior and traceback/log output
