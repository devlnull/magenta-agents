# ADR-0002: Claude Code is the primary tool

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | [RFC-0001, sections 9.3, 9.5, and 14](../rfc/RFC-0001-magenta-agents.md#14-open-decisions) |

## Context

AMQ uses Claude Code every day, and also models from OpenAI, Google (Gemini), and xAI (Grok). Phases 1 and 2 need one primary tool, so that the first adapter stays small.

## Decision

- Phases 1 and 2 target Claude Code only.
- The canonical agent format is the Claude Code subagent format plus a `magenta:` block (RFC-0001, 9.3).
- In phase 3, add a path for the other vendors:
  - Their models: through model profiles, in OpenCode or in the runner (ADR-0004).
  - Their CLIs (for example Codex CLI or Gemini CLI), if AMQ uses them: through AGENTS.md and Agent Skills.

## Consequences

- Good: a rich feature set first (subagents, skills, hooks). The first adapter is small. VS Code also reads this agent format.
- Bad: Claude Code subagents select Claude models. A different vendor for each agent waits for phase 3.
- Follow-up: confirm how AMQ uses OpenAI, Gemini, and Grok: in their apps, in their CLIs, or through their APIs.
