# Setup and Authentication Notes

## Setup surfaces

Codex supports four primary surfaces for setup and usage:

- App (macOS)
- IDE extension
- CLI
- Cloud (chatgpt.com/codex)

Source: https://developers.openai.com/codex/quickstart/

## Auth modes

OpenAI docs specify two login modes for local Codex clients:

- ChatGPT login (subscription-based)
- API key login (usage-based)

Codex cloud requires ChatGPT login.

Source: https://developers.openai.com/codex/auth/

## Credential handling

- Cached credentials can be in `~/.codex/auth.json` or OS credential store.
- `cli_auth_credentials_store` controls storage mode (`file`, `keyring`, `auto`).
- In CI/non-interactive mode, `CODEX_API_KEY` can be provided for `codex exec`.

Sources:
- https://developers.openai.com/codex/auth/
- https://developers.openai.com/codex/noninteractive/

## Admin-enforced auth constraints

Managed environments can enforce:

- `forced_login_method = "chatgpt" | "api"`
- `forced_chatgpt_workspace_id = "..."`

Source: https://developers.openai.com/codex/auth/
