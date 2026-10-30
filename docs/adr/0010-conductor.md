# ADR-0010: The /magenta conductor for all daily tasks

| Field | Value |
|---|---|
| Status | Proposed. ADR-0012 changes the default mode (verify first); the playbooks of this ADR are team mode. |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | Request: one command for all daily tasks (improvements, optimizations, bug fixes, features), with dynamic agent selection and results that keep the rules of all agents |

## Context

Most daily work is not a new feature. It is a bug fix, an optimization, a refactor, an investigation, or a review. The lanes of RFC-0001 describe features well, but not these tasks. The user wants one entry point, `/magenta <task>`, that selects the agents and makes them collaborate.

## Decision

1. A conductor skill `magenta` is the entry point. It runs in the main session of the tool, so it can keep the human gates. It delegates all specialist work to the agents and does not change production code.
2. A routing table (`workflows/routing.md`) maps task types to playbooks, core teams, and the conditions to add agents. Task types: bug, performance, improvement, feature, investigation, review, incident, security, upgrade, tests, design.
3. Each task type has a playbook (`workflows/<type>.md`).
4. Each task has a constraint ledger: the rules of the Architect, QA, the Principal, the project, and the human. Each candidate solution must pass all constraints. A faster or smaller solution that breaks one is rejected. Only the human can waive a constraint.
5. Two new collaboration patterns: P8 tournament (competing implementations in separate worktrees, one measurement) and P9 competing hypotheses (parallel read-only investigators).
6. Gates for tasks that are not features: a plan gate (not for clear lite tasks) and a done gate.
7. The Principal has two modes: lead mode (main session) and conductor mode (a subagent that does only the step that the conductor asks for).
8. New skills: `performance-investigation`, `root-cause-analysis`, `safe-refactoring`, `incident-response`.

## Consequences

- Good: one command for all daily work. The team size follows the risk. The result keeps all rules, with evidence.
- Bad: the conductor runs in the main session, so the guard does not restrict the conductor itself. The rules of the skill and the permission prompts of the tool apply to it.
- Follow-up: measure the conductor with golden tasks for each task type (evals).
