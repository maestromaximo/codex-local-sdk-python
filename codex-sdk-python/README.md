# codex-sdk-python

`codex-sdk-python` packages this repository's local `codex_local_sdk` module as an installable
PyPI distribution and adds a companion CLI:

- `codex-sdk skill` copies the bundled `codex-local-sdk-usage` skill to `.agents/skills/`.
- `codex-sdk docs` copies bundled documentation to `codex-sdk-documentation/`.

## Install

```bash
pip install codex-sdk-python
```

## CLI

```bash
codex-sdk --help
codex-sdk skill
codex-sdk docs
```

Use `--force` to overwrite existing files and `--output` to select a target directory.
