# ADR-0007: Headless runner in Python, with harnesses as workers

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | Phase 4; RFC-0001 9.3; decision D7 |

## Context

RFC-0001 recommended a Java runner, based on an existing Java API client. That client is not in this repository. The other Magenta tools use Python with the standard library only.

## Decision

1. The runner is Python, standard library only, in `runner/runner.py`. One language for all Magenta tools.
2. The runner calls existing harnesses as workers. The command templates are in `models.yaml` (`engines`). A new CLI needs a template, not code.
3. Headless workflows: `prd-review` and `pr-review`. Workflows with human gates stay interactive.
4. The runner keeps a JSONL log (`.magenta/runs/runs.jsonl`), the output of each step, and a cost budget.
5. CI templates for GitLab and GitHub run the review panel in advisory mode.

## Consequences

- Good: no build tool. The same tests run everywhere.
- Bad: no reuse of the Java CLI. The cost data depends on the JSON output of each harness.
- Follow-up: if a Java runner is still wanted (decision D7), port `runner.py`. Its interface is small: engines, steps, log, budget.
