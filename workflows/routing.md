## Routing: task type, team, and lane

The conductor (skill `magenta`) and the Principal use this table. First select the task type. Then select the team and the lane. Use the playbook of the task type.

### Task types

| Task type | Signals in the request | Playbook | Core team | Add these agents when |
|---|---|---|---|---|
| bug | error, exception, wrong result, "does not work", a failing test, a bug ticket | `bugfix` | `qa`, `engineer`, `principal` | `architect`: the root cause is structural or crosses a boundary. `frontend`: the bug is in client code. |
| performance | latency, p95, p99, slow, throughput, memory, CPU, cost of a query, Core Web Vitals | `performance` | `qa`, `engineer`, `architect`, `principal` | `frontend`: the target is a client metric. |
| improvement | refactor, clean up, simplify, tech debt, readability, duplication | `refactor` | `architect`, `qa`, `engineer`, `principal` | `frontend`: client code. |
| feature | a PRD, a new capability, a user story | `standard` or `full` | `product-manager`, `architect`, `qa`, `engineer`, `principal` | `frontend`: client work. |
| investigation | why, how does, explain, find out, "where is", analyze (without a change) | `investigation` | `principal` and the experts that the question needs | Add only the roles that the question needs. |
| review | review this PR, diff, design, RFC, or ADR | `pr-review` or `design-review` | `qa`, `architect`, `principal` | `product-manager`: user-facing scope. |
| incident | production is down or degraded, urgent, hotfix | `incident` | `principal`, `engineer`, `qa` | `architect`: after the mitigation, for the root cause. |
| security | vulnerability, CVE, authentication, authorization, secrets | `security` | `principal`, `architect`, `engineer`, `qa` | |
| upgrade | upgrade a library, a framework, or a runtime | `upgrade` | `engineer`, `qa`, `principal` | `architect`: a major version or a breaking change. |
| tests | add tests, coverage, flaky tests, test speed | `tests` | `qa`, `engineer` | `principal`: the change affects CI for the team. |
| design | design a solution, write an RFC or an ADR, select a technology | `design` | `architect`, `principal` | `product-manager`: scope or value questions. `qa`: testability. |

If a request has two types (for example "find out the performance issue and fix it"), use the type of the final result (performance). Use the steps of the other type inside it.

### Team rules

1. Use the smallest team that covers the risks. Each agent in the team has a reason. Write the reason in the brief.
2. QA is in the team for each change of behavior, performance, or tests.
3. The Principal plans each standard or full task and does each final review.
4. Add the Architect when the change crosses a module or service boundary, changes a data model, a schema, a cache, a public API, or an event contract, adds a dependency or a technology, or touches an area with an ADR.
5. Add the Product Manager when the change affects users, scope, or priority, or when the success metric is a product metric.
6. Use `engineer` for server code and `frontend` for client code. Use both only when the task needs both, with separate scopes.

### Lanes

| Lane | Use it when | Human gates |
|---|---|---|
| lite | One module, low risk, easy to revert, the change is obvious. | Done gate only. Ask before the work only if the request is not clear. |
| standard | One bounded context, or the solution is not obvious, or a measurable target. | Plan gate, done gate. Feature tasks also have the PRD gate. |
| full | More than one bounded context, data migration, money or security flows, a one-way-door decision. | PRD gate (features), plan and design gate, done gate, release gate. |

If more than one lane matches, use the heavier lane. Money, security, data migration, or a one-way-door decision always means the full lane.

### Gates for tasks that are not features

- **Plan gate.** The human approves the brief (with the success criteria), the team, the plan, and the constraint ledger.
- **Done gate.** The human reviews the result, the evidence, and the constraint check. Then the human merges, asks for more work, or stops.

### Constraint ledger

Each task has a constraint ledger in `04-plan.md` (lite lane: in `00-brief.md`). It lists the rules that the result must not break:

| Source | Examples |
|---|---|
| Architect | ADRs, module boundaries, dependency rules, data ownership, consistency rules, API and event contracts, fitness functions |
| QA | All tests pass. Locked acceptance tests do not change. No new flaky tests. Performance thresholds. Edge cases covered. |
| Principal | Rollback, feature flag when necessary, observability, resilience, capacity, security |
| Project | The conventions in the project context, lint, format |
| Human | The constraints in the request |

A candidate solution that breaks one constraint is rejected, even when it is faster. Only the human can waive a constraint, in writing. The final review records the result of each constraint.
