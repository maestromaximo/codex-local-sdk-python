# AGENTS.md

## Scope
Applies to files under `documentation/`.

## Purpose
This folder stores curated notes from official OpenAI Codex docs for architecture and implementation decisions in this repo.

## Start Here
1. `documentation/README.md`
2. `documentation/codex_core_docs.md`
3. `documentation/programmatic_integration.md`
4. `documentation/mcp_and_skills.md`

## Editing Rules
- Keep notes concise and implementation-oriented.
- Prefer official OpenAI docs links (developers.openai.com / platform.openai.com).
- Preserve file-per-topic organization.
- Do not duplicate large sections across files; cross-link instead.
- If a product/API behavior changed, update both:
  - this folder notes
  - `README.md` and/or HTML docs if user-facing behavior is affected

## Citation Practice
- Include direct source links for key claims.
- Prefer stable top-level doc links plus specific reference pages when available.

## When Updating Architecture Guidance
- Keep recommendations aligned with current SDK capabilities in `codex_local_sdk/`.
- Flag aspirational/future ideas clearly so they are not mistaken for implemented behavior.

## Completion Checklist
1. Notes are accurate and internally consistent.
2. Links are valid and official.
3. No contradictions with current SDK behavior.
