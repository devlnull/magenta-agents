# ADR-0003: Personal use first

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | [RFC-0001, section 14](../rfc/RFC-0001-magenta-agents.md#14-open-decisions) |

## Context

The agents and the rules are new. They will change often at the start. A team rollout needs distribution, onboarding, and agreement.

## Decision

- AMQ is the only user in phases 1 to 4.
- A pilot team comes in phase 5.

## Consequences

- Install the generated agents at user level (`~/.claude/agents/` and `~/.claude/skills/`), not as a plugin. Plugin agents ignore agent-level hooks and permission modes. User-level agents keep them, so the file-ownership hooks work.
- In shared team repositories, keep `.magenta/` out of the team history until the pilot. There are two ways:
  - Add `.magenta/` to `.git/info/exclude` in the local clone.
  - Keep the work items in a personal workspace repository.
  This is decision D5, which is still open.
- A plugin or a marketplace comes in phase 5.
