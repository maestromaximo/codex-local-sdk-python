# Security, Sandbox, and Approval Controls

## Core control model

Codex security combines:

- Sandbox mode: technical capability boundaries
- Approval policy: when Codex must ask before actions

Source: https://developers.openai.com/codex/security/

## Important defaults

For local CLI/IDE usage, defaults emphasize:

- write scope limited to workspace
- no network access by default
- approvals when leaving safe boundaries

Source: https://developers.openai.com/codex/security/

## Common run profiles

- Safe planning/inspection:
  - `--sandbox read-only --ask-for-approval on-request`
- Standard auto workflow:
  - `--full-auto` (maps to workspace-write + on-request)
- High-risk unrestricted mode:
  - `--dangerously-bypass-approvals-and-sandbox` (`--yolo`)

Source: https://developers.openai.com/codex/security/

## Network and web search

- Workspace-write network can be enabled in config.
- Web search mode is configurable: `cached`, `live`, `disabled`.
- `cached` is OpenAI-indexed results; `live` fetches current pages.

Sources:
- https://developers.openai.com/codex/security/
- https://developers.openai.com/codex/config-basic/

## Rules for outside-sandbox command governance

Use `.rules` + `prefix_rule(...)` to `allow`, `prompt`, or `forbidden` command prefixes outside sandbox.

Source: https://developers.openai.com/codex/rules/
