# ADR-0001: Deliver Magenta as "agents as code", in phases

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | [RFC-0001, section 9](../rfc/RFC-0001-magenta-agents.md#9-implementation-options) |

## Context

We need a way to define, run, and improve six role-based AI agents. RFC-0001 compares three options:

- A: a Markdown pack for one tool.
- B: a custom orchestrator on model APIs.
- C: a hybrid, "agents as code".

AI tools change their formats every few months. Good coding harnesses already exist.

## Decision

We use option C, in phases:

1. One tool-neutral source of truth for agents, rules, skills, templates, workflows, and model profiles.
2. Adapters generate the native files for each tool.
3. A thin headless runner comes in phase 4. It calls the existing harnesses. It does not rebuild the agent loop.
4. Evals measure each change to the rules, the prompts, or the model mapping.

## Consequences

- Good: value in days. No lock-in. Hard workflow control only where it pays.
- Bad: we maintain the adapters. There are two layers to understand.
- Follow-up: phase 0 builds the first adapter (Claude Code, see ADR-0002). The runner language is decision D7, which is still open.
