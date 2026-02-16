# MCP and Skills Patterns

## MCP as tool bus

Codex MCP supports:

- local STDIO servers
- streamable HTTP servers
- optional OAuth / bearer auth for supported HTTP servers

Source: https://developers.openai.com/codex/mcp/

## Recommended MCP standardization fields

Per server:

- transport (`command`+`args` or `url`)
- auth (`bearer_token_env_var` / OAuth login flow)
- `enabled`, `required`, `startup_timeout_sec`, `tool_timeout_sec`
- `enabled_tools` and `disabled_tools`

Source: https://developers.openai.com/codex/mcp/

## Skills as reusable behavior units

Skill package structure:

- required: `SKILL.md`
- optional: `scripts/`, `references/`, `assets/`, `agents/openai.yaml`

Skills can be explicitly invoked or implicitly triggered by description.

Source: https://developers.openai.com/codex/skills/

## AGENTS.md layering for instruction policy

Codex resolves instruction chain across global + project scope with ordered precedence and byte limits.

Source: https://developers.openai.com/codex/guides/agents-md/
