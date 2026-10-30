# ADR-0008: Team distribution as a Claude Code plugin and marketplace

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | Phase 5; ADR-0003 |

## Context

A team needs one install and updates. Plugin agents ignore agent-level hooks and permission modes. Plugin hooks run also inside subagents, and the hook input gives the agent name (`agent_type`).

## Decision

1. `python3 magenta.py build` also makes a marketplace with one plugin, `magenta`, in the repository root (`.claude-plugin/marketplace.json`, `plugins/magenta/`). These generated files are in git, so GitHub can serve them (ADR-0009).
2. The plugin agents and skills have short names; Claude Code shows them as `magenta:<name>`.
3. One plugin hook runs `guard.sh --auto`, a launcher that finds Python and runs `guard.py`. It finds the agent from `agent_type`. It enforces the policy of Magenta agents and passes all other sessions.
4. Members install with `claude plugin marketplace add devlnull/magenta-agents` and `claude plugin install magenta@magenta-marketplace`.
5. A member uses the plugin or the user-level install, not both.

## Consequences

- Good: one install command and versioned releases (`release` in `magenta.yaml`).
- Bad: the plugin path is not yet tested in a real session (agent names in `agent_type`, preloaded plugin skills).
- Follow-up: run `claude plugin validate .` and one test session before the pilot.
