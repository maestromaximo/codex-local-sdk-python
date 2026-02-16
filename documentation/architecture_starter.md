# Starter Architecture: Codex Standardization Library

## Goal

Create a reusable internal library that standardizes how Codex is configured, invoked, and governed across local development and CI.

## Recommended module layout

1. `auth/`
- Auth mode resolver (`chatgpt`, `api`)
- CI key injector for non-interactive runs

2. `profiles/`
- Named `config.toml` profile templates (`strict`, `default`, `ci_autofix`, `review`)
- Helpers to render project `.codex/config.toml`

3. `permissions/`
- Sandbox + approval presets
- Rule file generator/validator (`codex execpolicy check`)

4. `skills/`
- Skill registry and installer hooks
- Skill enable/disable config management

5. `mcp/`
- MCP server catalog schema
- Config writer for `[mcp_servers.*]`
- Health checks for required servers

6. `runtime/`
- Wrapper for `codex exec`
- JSONL parser + typed events
- Output schema helpers

7. `integrations/`
- GitHub Actions helpers
- Optional app-server adapter for rich clients

## Documentation-backed constraints

- Keep project-scoped config under trusted `.codex/config.toml`
- Keep least-privilege defaults (`workspace-write` + approvals)
- Use `required = true` only for MCP dependencies that must exist
- Separate stable vs experimental features by policy

Sources:
- https://developers.openai.com/codex/config-basic/
- https://developers.openai.com/codex/config-reference/
- https://developers.openai.com/codex/security/
- https://developers.openai.com/codex/mcp/
- https://developers.openai.com/codex/feature-maturity/
