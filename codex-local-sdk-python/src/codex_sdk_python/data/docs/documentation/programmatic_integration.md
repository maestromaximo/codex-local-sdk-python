# Programmatic Integration Options

## 1) Codex SDK (simplest app integration)

Use SDK threads (`startThread`, `run`, `resumeThread`) for programmatic workflows.

Source: https://developers.openai.com/codex/sdk/

## 2) Codex App Server (deep integration)

Use app-server when you need:

- JSON-RPC over JSONL stdio protocol
- explicit thread/turn/item lifecycle control
- fine-grained event streaming
- approvals and tool event handling in your own client

Source: https://developers.openai.com/codex/app-server/

## 3) Codex as MCP server (agent orchestration)

`codex mcp-server` exposes tools (`codex`, `codex-reply`) so other MCP clients/agent frameworks can orchestrate Codex.

Source: https://developers.openai.com/codex/guides/agents-sdk/

## Integration selection

- Need simple scripted runs: use `codex exec`
- Need app-native conversational control: use app-server
- Need multi-agent orchestration: use Codex MCP server with Agents SDK
