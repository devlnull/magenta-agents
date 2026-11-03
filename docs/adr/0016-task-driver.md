# ADR-0016: A driver role for each task

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-11-03 |
| Decider | AMQ |
| Source | Request: "change the orchestrator to another agent, for example QA for a test-heavy task, the Architect for a design task" |

## Context

The conductor ran the process and also made the domain decisions of each task: the plan, what "done" means, "is it enough?", and which option. For a test task or a design task, QA or the Architect knows these answers better.

A specialist cannot be the orchestrator. In Claude Code, a subagent cannot start other subagents, so only the main session can orchestrate. A specialist as orchestrator would also judge its own work, and would weight its own domain too much.

## Decision

The conductor stays the only orchestrator and keeps the process: the scope, the lane, the rounds, the gates, the checks, the lenses, and the cost. A **driver** role owns the domain decisions of each task, and a different role, the **checker**, reviews the work of the driver. The driver table in `workflows/routing.md` maps each task type to a driver. The conductor selects the driver from the request; `--driver <role>` or `--driver none` selects it by hand.

The rules come from an evaluation (`evals/driver/`): one main domain; the lead is the driver in the lite lane; the conductor keeps the process; evidence can change the driver one time; the driver keeps the owners of the checks and files; an incident is mitigated first; the checker is a lens, with a plan review only in the full lane; a design is done by review, not by checks; no plan document when the driver is also the lead.

## Evidence

26 scenarios, 3 runs each, blind comparison of the plans of 0.12.0 and 0.13.0 by a judge model: 0.13.0 wins 42, 0.12.0 wins 27, 9 ties. The average score is 7.31 against 6.72. The right role owns the domain decisions in 75 of 78 runs, against 58. The human gets fewer questions (2.99 against 3.92). Details: `evals/driver/results.md`.

## Consequences

- Better plans in most task types, with fewer questions.
- One weak point stays: a major framework upgrade (s21) is better with an Architect review of the plan. It is a candidate rule for a later version.
- The evaluation tests the plan, not the full result. Full runs on real repositories are the next step.
