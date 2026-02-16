# Automation and CI/CD

## `codex exec` for non-interactive automation

Best for CI pipelines and scripted workflows.

Key capabilities:

- plain final output to stdout
- JSONL event stream with `--json`
- schema-constrained final output via `--output-schema`
- resumable runs via `codex exec resume`

Source: https://developers.openai.com/codex/noninteractive/

## Safety in automation

Set least privilege explicitly:

- read-only for analysis-only jobs
- workspace-write for controlled fixes
- danger-full-access only in hardened isolated runners

Source: https://developers.openai.com/codex/noninteractive/

## GitHub Action

`openai/codex-action@v1` wraps Codex execution in Actions and supports:

- prompt file or inline prompt
- sandbox and args tuning
- output capture (`final-message`, output file)
- safety strategy options (`drop-sudo`, unprivileged modes)

Source: https://developers.openai.com/codex/github-action/
