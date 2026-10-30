## Routing: task type, mode, team, and lane

The conductor (skill `magenta`) and the Principal use these tables. First select the task type. Then select the mode: the default mode (lead, checks, lenses) or team mode. In team mode, select the team and the lane, and use the playbook of the task type.

### Task types

| Task type | Signals in the request | Playbook | Core team | Add these agents when |
|---|---|---|---|---|
| bug | error, exception, wrong result, "does not work", a failing test, a bug ticket | `bugfix` | `qa`, `engineer`, `principal` | `architect`: the root cause is structural or crosses a boundary. `frontend`: the bug is in client code. |
| performance | latency, p95, p99, slow, throughput, memory, CPU, cost of a query, Core Web Vitals | `performance` | `qa`, `engineer`, `architect`, `principal` | `frontend`: the target is a client metric. `database`: a slow query or an index. `sre`: production capacity or resource limits. |
| improvement | refactor, clean up, simplify, tech debt, readability, duplication | `refactor` | `architect`, `qa`, `engineer`, `principal` | `frontend`: client code. |
| feature | a PRD, a new capability, a user story | `standard` or `full` | `product-manager`, `architect`, `qa`, `engineer`, `principal` | `frontend`: client work. `database`: a schema change. `security`: authentication, money, or personal data. `sre`: a new endpoint, remote call, or rollout risk. `writer`: user documentation. |
| investigation | why, how does, explain, find out, "where is", analyze (without a change) | `investigation` | `principal` and the experts that the question needs | Add only the roles that the question needs. |
| review | review this PR, diff, design, RFC, or ADR | `pr-review` or `design-review` | `qa`, `architect`, `principal` | `product-manager`: user-facing scope. `sre`, `security`, `database`: by the lens table. |
| incident | production is down or degraded, urgent, hotfix | `incident` | `sre`, `principal`, `engineer`, `qa` | `architect`: after the mitigation, for the root cause. `platform`: a deployment or infrastructure cause. |
| security | vulnerability, CVE, authentication, authorization, secrets | `security-fix` | `security`, `principal`, `engineer`, `qa` | `architect`: a structural fix. `platform`: a pipeline, image, or infrastructure fix. |
| upgrade | upgrade a library, a framework, or a runtime | `upgrade` | `engineer`, `qa`, `principal` | `architect`: a major version or a breaking change. `security`: the upgrade fixes a CVE. `platform`: a runtime or base image upgrade. |
| infrastructure | CI, CD, pipeline, Docker, Kubernetes, Helm, Terraform, deployment, build speed | `infrastructure` | `platform`, `sre` | `security`: secrets, permissions, or network exposure. |
| reliability | SLO, alert, dashboard, observability, timeout, retry, circuit breaker, capacity, postmortem action | `reliability` | `sre`, `engineer` or `platform`, `qa` | `principal`: a change of the SLOs of the team. |
| data | schema change, migration, backfill, index, data cleanup | `standard` or `full` | `database`, `architect`, `engineer`, `qa` | `sre`: a long backfill or a large table. |
| docs | documentation, README, guide, release notes, changelog | `docs` | `writer` | The owner of the subject reviews (for example `architect` for a design guide). |
| tests | add tests, coverage, flaky tests, test speed | `tests` | `qa`, `engineer` | `principal`: the change affects CI for the team. |
| design | design a solution, write an RFC or an ADR, select a technology | `design` | `architect`, `principal` | `product-manager`: scope or value questions. `qa`: testability. |

If a request has two types (for example "find out the performance issue and fix it"), use the type of the final result (performance). Use the steps of the other type inside it.

### Modes

Use the default mode for most tasks. Use team mode only when a team trigger applies. The request can select the mode: `--team` or `--lead`.

| Task type | Lead (default mode) | Checks first | Lenses |
|---|---|---|---|
| bug | `engineer` or `frontend` | QA: a test that reproduces the bug (red). | QA. Architect, when the cause is structural. |
| performance | `engineer` or `frontend` | QA: a measurement with the thresholds (red). Architect: the structural constraints (consistency, staleness, boundaries). | QA, Architect, Principal |
| improvement | `engineer` or `frontend` | QA: characterization tests (green). Architect: the target structure as rules (red). | Architect, QA |
| tests | `qa` | The project checks. | Principal, when the change affects CI for the team. |
| upgrade | `engineer` | The project checks. QA: smoke tests for the changed behavior. | QA, Principal |
| incident | `engineer` | QA: a test for the failure mode, when there is time. | SRE, Principal |
| feature (small and clear) | `engineer` or `frontend` | QA: acceptance tests (red). Architect: the contracts. | QA, Architect, Principal |
| investigation | None. The conductor or `principal` answers, read-only. | None. | None. |
| review | None. | None. | The review panel: QA, Architect, Principal. SRE, Security, and Database by the lens table. |
| design | `architect` | None. | Principal |
| infrastructure | `platform` | SRE: the lint and validate commands of the changed files (red when they find the problem). | SRE. Security, for secrets, permissions, or exposure. |
| reliability | `engineer` (code) or `platform` (alerts, dashboards, manifests) | SRE: the rule as a check. QA: a test for the failure behavior. | SRE, QA |
| docs | `writer` | The project checks (Markdown lint, link check), when they exist. | The owner of the subject. |
| security | Team mode. | | |
| data | Team mode (a schema change is a team trigger). | | |

### Team triggers

Use team mode when one of these applies. Write the trigger in the brief.

1. The request starts with `--team`.
2. A feature with a PRD, or a change of user-facing scope or priority. Add the Product Manager.
3. A one-way-door decision, a new technology, or a change of a public API, an event contract, a schema, or data ownership.
4. Money, security, personal data, or a data migration. These always use the full lane.
5. The change crosses more than one bounded context.
6. The lead did not pass the checks after three rounds in the default mode.
7. Two or more promising solutions need a measurement (tournament, P8), or a difficult bug needs competing hypotheses (P9).

The playbooks and the lanes below describe team mode. In the default mode, the agents use the same skills (for example `performance-investigation`, `root-cause-analysis`, and `safe-refactoring`) inside the steps of the conductor.

### Lenses

A lens is a read-only review from the view of one role. Each role describes its lens in the section "Review lens". Select one to three lenses by risk:

| Lens | Use it when the change |
|---|---|
| QA | changes behavior |
| Architect | touches structure: boundaries, dependencies, contracts, data model, areas with an ADR |
| Principal | is in the standard or full lane (production readiness and final review) |
| SRE | adds or changes remote calls, timeouts, retries, resource use, configuration, or rollout |
| Security | touches authentication, authorization, input from outside, secrets, money, personal data, or dependencies |
| Database | changes a schema, a migration, a query on a hot path, or a transaction |

### Team rules

1. Use the smallest team that covers the risks. Each agent in the team has a reason. Write the reason in the brief.
2. QA is in the team for each change of behavior, performance, or tests.
3. The Principal plans each standard or full task and does each final review.
4. Add the Architect when the change crosses a module or service boundary, changes a data model, a schema, a cache, a public API, or an event contract, adds a dependency or a technology, or touches an area with an ADR.
5. Add the SRE when the change affects production behavior: new or changed endpoints, remote calls, timeouts, retries, resource use, configuration, or rollout.
6. Add the Security Engineer when the change touches authentication, authorization, input from outside, secrets, money, personal data, or adds a dependency.
7. Add the Database Engineer when the change touches a schema, a migration, a backfill, an index, or a slow query. The Engineer writes the migration code from its plan.
8. Use the Platform Engineer for CI/CD pipelines, container files, deployment manifests, and infrastructure code. Other makers do not change these files.
9. Add the Technical Writer when user documentation or release notes are part of "done".
10. Add the Product Manager when the change affects users, scope, or priority, or when the success metric is a product metric.
11. Use `engineer` for server code and `frontend` for client code. Use both only when the task needs both, with separate scopes.

### Lanes

| Lane | Use it when | Human gates |
|---|---|---|
| lite | One module, low risk, easy to revert, the change is obvious. | Checks gate (only when there are new checks), done gate. |
| standard | One bounded context, or the solution is not obvious, or a measurable target. | Checks gate or plan gate, done gate. Feature tasks also have the PRD gate. |
| full | More than one bounded context, data migration, money or security flows, a one-way-door decision. | PRD gate (features), plan and design gate, done gate, release gate. |

If more than one lane matches, use the heavier lane. Money, security, data migration, or a one-way-door decision always means the full lane.

### Gates for tasks that are not features

- **Checks gate.** The human approves the new checks: the success criteria and the rules as commands. In the default mode, the human also approves the brief and the short plan at this gate.
- **Plan gate (team mode).** The human approves the brief (with the success criteria), the team, the plan, and the constraint ledger.
- **Done gate.** The human reviews the result, the verify table, and the constraint check. Then the human merges, asks for more work, or stops.

### Constraint ledger

Each task has a constraint ledger in `00-brief.md` (team mode: `04-plan.md`). It lists the rules that the result must not break. Write each constraint as a check when a command can test it:

| Source | Examples |
|---|---|
| Architect | ADRs, module boundaries, dependency rules, data ownership, consistency rules, API and event contracts, fitness functions |
| QA | All tests pass. Locked acceptance tests do not change. No new flaky tests. Performance thresholds. Edge cases covered. |
| Principal | Rollback, feature flag when necessary, observability, resilience, capacity, security |
| SRE | SLOs, timeouts and retries, observability, capacity, runbooks for new alerts |
| Security | Access control, input validation, secrets, dependencies without high or critical vulnerabilities |
| Database | Reversible migrations, no blocking locks, compatibility of the old and the new code, indexes for new queries |
| Project | The conventions in the project context, lint, format |
| Human | The constraints in the request |

A candidate solution that breaks one constraint is rejected, even when it is faster. Only the human can waive a constraint, in writing. The final review records the result of each constraint.
