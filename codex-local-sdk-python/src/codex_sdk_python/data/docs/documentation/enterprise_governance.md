# Enterprise and Governance Notes

## Team Config standardization

Docs recommend using shared team configuration layers for:

- defaults (`config.toml`)
- command governance (`rules/`)
- shared skill catalog (`skills/`)

Source: https://developers.openai.com/codex/enterprise/admin-setup/

## Local vs cloud control planes

Admin setup distinguishes local and cloud access controls; configure each separately via workspace settings and roles.

Source: https://developers.openai.com/codex/enterprise/admin-setup/

## Enforcement layer

`requirements.toml` can enforce allowed ranges for approval/sandbox/search and approved MCP server identities.

Source: https://developers.openai.com/codex/security/

## Maturity labels for policy

Use maturity labels to gate adoption:

- Stable for production defaults
- Beta for controlled pilots
- Experimental only with explicit risk acceptance

Source: https://developers.openai.com/codex/feature-maturity/
