# ADR-0005: Design of the Claude Code adapter and the guard hook

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | Phase 0 implementation; RFC-0001, sections 6.6 and 9.3 |

## Context

Phase 0 needs a working path from the canonical source to Claude Code. The `magenta:` block alone enforces nothing. Plugin agents ignore agent-level hooks. Teammates in agent teams ignore the `skills` field.

## Decision

1. The build puts the constitution (`rules/*.md`) and a team roster into the body of each generated agent.
2. The build makes two skills from the source: `magenta-workflow` (from `workflows/`) and `magenta-templates` (from `templates/`).
3. All generated agents and skills have the name prefix `magenta-`, to prevent collisions with other agents and skills.
4. The install copies the files into `~/.claude/` (user level), not as a plugin, so the agent-level hooks work.
5. A `PreToolUse` hook (`guard.py`) in each agent enforces file ownership, secret paths, and a shell allowlist. It fails closed if its policy is missing.
6. A repository can extend the writes and the shell allowlist of an agent in `.magenta/policy.json`. Only the human writes this file.
7. The tools use only the Python standard library, with a small YAML subset parser.
8. The constitution has seven files: `00-tenets.md` to `60-conflicts.md`. RFC-0001 listed six; the tenets got their own file.

## Consequences

- Good: the rules work without a plugin system and without extra packages. The tests check the parser against PyYAML.
- Bad: the guard blocks shell operators, so agents cannot use pipes. The guard uses the session folder as the project root.
- Follow-up: phase 3 adds adapters for other tools, with the same policies.
