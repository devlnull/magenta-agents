# ADR-0006: Adapters for OpenCode and AGENTS.md tools

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | Phase 3; ADR-0002, ADR-0004 |

## Context

Phase 3 adds other vendors (OpenAI, Gemini, Grok) and self-hosted models. Claude Code subagents select Claude models only. OpenCode selects `provider/model` for each agent and enforces ordered permission rules. Codex CLI and similar tools read AGENTS.md and Agent Skills, but have no subagents and no hooks.

## Decision

1. OpenCode adapter: the same agents, with the model from the `opencode` key of the profile. The permission rules replace the guard hook: deny all edits, then the ordered write rules of the agent; deny secret paths; deny all shell commands, then the allowlist, then the deny list.
2. AGENTS.md adapter: each role becomes a skill `magenta-role-<id>`. A marked block in AGENTS.md holds the constitution and the role list. For Codex CLI, the install writes `~/.codex/skills/` and a block in `~/.codex/AGENTS.md`.
3. AGENTS.md tools have no enforcement. Use them for the advisor roles. Use Claude Code or OpenCode for the makers.
4. Missing model IDs are not guessed. Without an `opencode` model, an OpenCode agent uses the session model.

## Consequences

- Good: the same source runs in three tools. A vendor change is a line in `models.yaml`.
- Bad: the OpenCode path patterns and permission semantics are from the documentation, not yet tested in a real session.
- Follow-up: test one advisor and one maker in OpenCode with a model of another family. Record the eval scores.
