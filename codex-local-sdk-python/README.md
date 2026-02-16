# codex-local-sdk-python

[![PyPI Version](https://img.shields.io/pypi/v/codex-local-sdk-python.svg)](https://pypi.org/project/codex-local-sdk-python/)
[![Python Versions](https://img.shields.io/pypi/pyversions/codex-local-sdk-python.svg)](https://pypi.org/project/codex-local-sdk-python/)
[![Unit Tests](https://img.shields.io/github/actions/workflow/status/maestromaximo/codex-local-sdk-python/unit.yml?label=unit%20tests)](https://github.com/maestromaximo/codex-local-sdk-python/actions/workflows/unit.yml)

`codex-local-sdk-python` packages this repository's local `codex_local_sdk` module as an installable
PyPI distribution and adds a companion CLI:

- `codex-sdk skill` copies the bundled `codex-local-sdk-usage` skill to `.agents/skills/`.
- `codex-sdk docs` copies bundled documentation to `codex-sdk-documentation/`.

## Install

```bash
pip install codex-local-sdk-python
```

## Python usage

```python
from codex_local_sdk import CodexExecRequest, CodexLocalClient

client = CodexLocalClient()
result = client.run(CodexExecRequest(prompt="Summarize this repo"), timeout_seconds=120)
print(result.final_message)
```

## CLI

```bash
codex-sdk --help
codex-sdk skill
codex-sdk docs
```

Command details:

- `codex-sdk skill` copies `codex-local-sdk-usage` to `.agents/skills/`
- `codex-sdk docs` copies docs to `codex-sdk-documentation/`
- use `--output <dir>` to choose destination root
- use `--force` to overwrite existing files

Examples:

```bash
codex-sdk skill --output .
codex-sdk docs --output .
codex-sdk skill --output /path/to/project --force
```
