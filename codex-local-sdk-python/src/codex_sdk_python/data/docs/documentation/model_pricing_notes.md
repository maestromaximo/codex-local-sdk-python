# Models and Pricing Notes for Architecture Decisions

## Model availability

`gpt-5.3-codex` is documented as the primary recommended Codex model for ChatGPT-authenticated Codex sessions; API availability is model-dependent and can differ by model/version.

Source: https://developers.openai.com/codex/models/

## Operational implication

A reusable Codex framework should not hardcode one model; treat model as environment/profile configuration.

Sources:
- https://developers.openai.com/codex/models/
- https://developers.openai.com/codex/config-basic/

## Pricing implication

Pricing and limits vary by ChatGPT plan versus API key usage. Build your library with pluggable auth+execution strategy so teams can run either:

- ChatGPT-authenticated Codex sessions
- API-key automation paths

Source: https://developers.openai.com/codex/pricing/
