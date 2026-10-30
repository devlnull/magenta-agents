# ADR-0011: Custom agents in Codex CLI and Gemini CLI

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | Supersedes the Codex part of ADR-0006 |

## Context

ADR-0006 used role skills for Codex CLI, because Codex had no subagents. Codex CLI and Gemini CLI now support custom subagents. Codex removed custom prompts; skills are invoked with `$name`. Gemini CLI has TOML custom commands. Both read skills from `~/.agents/skills`.

## Decision

1. Codex CLI target: one custom agent for each role in `~/.codex/agents/magenta-<id>.toml` (`name`, `description`, `developer_instructions`, optional `model` and `model_reasoning_effort`), the skills in `~/.agents/skills/`, and a short block in `~/.codex/AGENTS.md`. Entry point: `$magenta <task>`.
2. Gemini CLI target: one subagent for each role in `~/.gemini/agents/magenta-<id>.md`, the command `~/.gemini/commands/magenta.toml` (`/magenta <task>`), and the skills in `~/.agents/skills/`.
3. Both tools have no Magenta guard. Each agent gets its write and shell rules as text. The sandbox and approval settings of the tool still apply.
4. In both tools, subagents cannot start subagents by default. The conductor starts all agents.
5. The role skills (`magenta-role-<id>`) stay in `dist/agents-md/` for tools without subagents.

## Consequences

- Good: real multi-agent collaboration in four tools with one source.
- Bad: the agent names use hyphens (`magenta-qa`); the Codex examples use underscores. If Codex rejects hyphens, the adapter must change the names.
- Follow-up: test `$magenta` in Codex and `/magenta` in Gemini CLI with one bug fix and one performance task.
