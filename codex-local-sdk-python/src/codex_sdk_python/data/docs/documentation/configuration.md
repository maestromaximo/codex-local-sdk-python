# Configuration Standardization (`config.toml`)

## Precedence order (high to low)

1. CLI flags / `--config`
2. `--profile` values
3. project `.codex/config.toml` (closest directory wins)
4. user `~/.codex/config.toml`
5. system config
6. built-in defaults

Source: https://developers.openai.com/codex/config-basic/

## Standard keys for a reusable framework

- Model selection: `model`, `model_provider`
- Safety: `approval_policy`, `sandbox_mode`
- Network behavior: `sandbox_workspace_write.network_access`
- Search policy: `web_search`
- Project trust and doc loading behavior
- Tool environment policy: `[shell_environment_policy]`
- MCP definitions: `[mcp_servers.<id>]`
- Skill enablement overrides: `[[skills.config]]`

Sources:
- https://developers.openai.com/codex/config-basic/
- https://developers.openai.com/codex/config-reference/

## Advanced patterns

- Use profiles for named operating modes (`strict`, `ci-autofix`, `review`).
- Use `--config` for one-off overrides in scripts.
- Keep repo-specific behavior in `.codex/config.toml` for portability.

Source: https://developers.openai.com/codex/config-advanced/
