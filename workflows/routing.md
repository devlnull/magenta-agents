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
| infrastructure | CI, CD, pipeline, Docker, Kubernetes, Helm, Terraform, deployment, build speed | `infrastructure` | `platform`, `sre` | `security`: secrets, permissions, or network exposure. `qa`: the pipeline runs or gates tests (QA owns the thresholds). |
| reliability | SLO, alert, dashboard, observability, timeout, retry, circuit breaker, capacity, postmortem action | `reliability` | `sre`, `engineer` or `platform`, `qa` | `principal`: a change of the SLOs of the team. |
| data | schema change, migration, backfill, index, data cleanup | `standard` or `full` | `database`, `architect`, `engineer`, `qa` | `sre`: a long backfill or a large table. |
| docs | documentation, README, guide, release notes, changelog | `docs` | `writer` | The owner of the subject reviews (for example `architect` for a design guide). |
| tests | add tests, coverage, flaky tests, test speed | `tests` | `qa`, `engineer` | `principal`: the change affects CI for the team. |
| design | design a solution, write an RFC or an ADR, select a technology | `design` | `architect`, `principal` | `product-manager`: scope or value questions. `qa`: testability. |

If a request has two types (for example "find out the performance issue and fix it"), use the type of the final result (performance). Use the steps of the other type inside it. These signals win over the others:

- a CVE or a vulnerability, also in an upgrade: **security**;
- a slow query whose fix is an index, a schema change, or a backfill: **data**;
- production is down or degraded now: **incident**;
- a change of a CI/CD pipeline, also for tests: **infrastructure**.

### Driver

The conductor runs the process. The **driver** owns the domain decisions of the task: it writes the plan (`04-plan.md`), says what "done" means as checks, answers the domain questions of the other agents, and gives the domain verdict at the end. A different role, the **checker**, reviews the work of the driver.

| Task type | Driver | Checker of the driver |
|---|---|---|
| tests | `qa` | `principal`; `sre` for a load test |
| design | `architect` | `principal`, and the specialists of the main risks as lenses on the draft |
| incident, reliability | `sre` | `principal` |
| security | `security` | `principal` |
| data | `database` | `architect` |
| infrastructure | `platform` | `sre` |
| docs | `writer` | the owner of the subject |
| bug, performance, improvement, feature, upgrade, review, investigation | `principal` | the selected lenses; in the full lane, also `architect` for the plan |

Rules for the driver:

1. **One domain.** A specialist drives when the task type is its domain. The Principal drives instead only when the task also has the main risk of another domain (team rules 5 to 7: SRE, Security, Database) or crosses more than one bounded context. Example: a new endpoint with a schema change, authentication, and a UI has the Principal as driver. The Architect always drives a design task, and the SRE always drives an incident.
2. **Small tasks have no plan step.** In the lite lane, the lead is the driver: the conductor writes the short plan in the brief, the lead makes the domain decisions (for example QA decides when the tests are enough), and the lens checks the result. No checker reviews a plan.
3. **The conductor keeps the process.** The scope of the brief, the lane, the maximum of three rounds, the gates, the checks, the lenses, and the cost belong to the conductor. The driver decides the domain questions inside the brief. If the plan of the driver goes outside the brief, the conductor asks the human. In auto mode, the brief wins: the conductor sends the plan back one time with the limit.
4. **Evidence can change the driver.** After the first evidence (for example the red checks or the root cause), the conductor checks the driver again. If the evidence points to another domain, it changes the driver one time and writes the reason. Example: a flaky test that fails only in CI goes from QA to Platform.
5. **The human can select.** `--driver <role>` selects the driver. `--driver none` uses no driver.
6. **The driver keeps the owners.** The team of the driver has the owner of each check that "done" needs, and the owner of each kind of file that the plan changes. Examples: QA defines a threshold for test quality (coverage, mutation score), also when Platform drives. Platform changes the CI files, also when QA drives.
7. **An incident is mitigated first.** The SRE drives the mitigation (rollback or flag) at once. The plan comes after the mitigation.
8. **The checker is another role, without extra steps.** The checker is one of the lenses at the end. Only in the full lane, it also reviews the plan before the checks gate. The driver never reviews its own plan, checks, or design.
9. **A design is done by review, not by checks.** For a design, an RFC, or an ADR, "done" is the review of the lenses on the draft and the decision of the human. Do not add a checks-first step.
10. **No plan document when the driver is the lead.** When the driver also does the work (for example QA writes a load test, Platform makes the build faster), it writes the short plan in the brief. A separate `04-plan.md` is for the full lane, or when the driver and the lead are different roles.

### Modes

Use the default mode for most tasks. Use team mode only when a team trigger applies. The request can select the mode: `--team` or `--lead`.

| Task type | Lead (default mode) | Checks first | Lenses |
|---|---|---|---|
| bug | `engineer` or `frontend` | The lead: a test that reproduces the bug (red). QA writes it when the QA rule applies. | QA, when the QA rule applies. Architect, when the cause is structural. |
| performance | `engineer` or `frontend` | QA: a measurement with the thresholds (red). Architect: the structural constraints (consistency, staleness, boundaries). | QA, Architect, Principal |
| improvement | `engineer` or `frontend` | The existing tests, or characterization tests by the lead (green). Architect: the target structure as rules (red). | Architect. QA, when the QA rule applies. |
| tests | `qa` | The project checks. | Principal, when the change affects CI for the team. |
| upgrade | `engineer` | The project checks. QA: smoke tests, when the QA rule applies. | Principal. QA, when the QA rule applies. |
| incident | `engineer` | The lead: a test for the failure mode, when there is time. | SRE, Principal |
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

### Collaboration patterns (team mode)

| ID | Pattern | Use it for |
|---|---|---|
| P3 | Maker and checker loop | One agent makes, another checks. Three rounds at most. |
| P6 | Review panel | QA, Architect, and Principal review at the same time, read-only. |
| P8 | Tournament | Two promising solutions: two makers in separate git worktrees, the same checks for both. Verify in a worktree uses the approvals of the main working tree. |
| P9 | Competing hypotheses | A difficult bug or a performance problem with no clear cause: two or three investigators, read-only. |
| P5 | Design Review Board | A one-way-door decision (workflow `design-review`). |

### Lenses

A lens is a read-only review from the view of one role. Each role describes its lens in the section "Review lens". Select one to three lenses by risk:

| Lens | Use it when the change |
|---|---|
| QA | changes behavior that users or other systems see, or the QA rule applies |
| Architect | touches structure: boundaries, dependencies, contracts, data model, areas with an ADR |
| Principal | is in the standard or full lane (production readiness and final review) |
| SRE | adds or changes remote calls, timeouts, retries, resource use, configuration, or rollout |
| Security | touches authentication, authorization, input from outside, secrets, money, personal data, or dependencies |
| Database | changes a schema, a migration, a query on a hot path, or a transaction |

### Team rules

1. Use the smallest team that covers the risks. Each agent in the team has a reason. Write the reason in the brief.
2. **The QA rule.** Add QA only when one of these applies: (a) the task type is tests; (b) a feature, or a change of behavior that users or other systems see; (c) money, security, personal data, or a data migration; (d) a performance target (QA measures it); (e) the existing tests do not cover the changed code, and the change is not trivial. Else the lead writes the tests of its change before the change, and the human approves them with the checks. The project checks and the lenses judge the result.
3. The driver plans each standard or full task (see Driver). The Principal does each final review.
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

The test budget of a lane: lite, three new tests at most; standard, ten at most; full, as the plan says. Each test proves one success criterion or one risk.

If more than one lane matches, use the heavier lane. Money, security, data migration, or a one-way-door decision always means the full lane. A task that only writes a design, an RFC, or an ADR uses the standard lane: the one-way-door decision is a decision of the human in it, not the change itself.

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
