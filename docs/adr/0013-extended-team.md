# ADR-0013: Extend the team with SRE, Platform, Security, Database, and Technical Writer roles

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | Request: "make new agents we might need, for example an SRE role, a DevOps role, or other roles. Make the team better." |

## Context

The first six roles cover product, architecture, planning, QA, and server and client code. Daily work also has risks that these roles do not own:

- Production behavior: SLOs, timeouts, retries, capacity, incidents. The Principal did this as one item of the readiness review.
- Pipelines, containers, and infrastructure code. The Engineer could change them, also the CI pipeline that tests its own work.
- Security: the Principal made threat models, but nobody owned the scanner rules, and a maker could add an ignore entry to make a scanner pass.
- Schema changes and slow queries, which can lose data or block a table.
- Documentation, which often does not agree with the code after a change.

ADR-0012 makes "done" a set of approved checks. A role is useful when it owns a kind of risk and can turn it into checks, or when it owns a kind of file that needs special care.

## Decision

Add five roles. Each one owns one kind of risk and its files.

| Agent | Type | Owns | Checks file |
|---|---|---|---|
| `sre` | reviewer | SLOs, resilience, operational readiness, incidents, runbooks, postmortems | `sre.yaml` |
| `platform` | maker | CI/CD pipelines, containers, Kubernetes and Helm, Terraform, alert rules | (none: makers do not write checks) |
| `security` | reviewer | threat models, secure code review, CVE triage, scanner rules and ignore files | `security.yaml` |
| `database` | advisor | migration plans, query and index recommendations | `database.yaml` |
| `writer` | maker | user documentation, READMEs, changelog, release notes | (none) |

Rules:

1. **Maker and checker stay separate.** The Database Engineer plans the migration and writes its checks. The Engineer writes the migration code. The SRE writes the operations checks. The Platform Engineer changes the files.
2. **Ownership by the guard.** The Engineer and the Front-End Engineer can no longer write CI pipelines, container and deployment files, infrastructure code, alert rules, scanner configuration, runbooks, or postmortems. A repository can change this in `.magenta/policy.json`.
3. **No live systems.** The Platform Engineer cannot run `terraform plan` or `apply`, `kubectl`, `helm install` or `upgrade`, or `docker push`. No agent reads `.tfvars` files or Terraform state.
4. **Routing.** New task types: `infrastructure`, `reliability`, `data`, and `docs`. The SRE leads incidents. The Security Engineer leads security tasks. Three new lenses: SRE, Security, and Database. A task still uses the smallest team that covers its risks.
5. **Not added now:** Performance Engineer, Release Manager, UX Designer, Mobile Engineer, Data or Product Analyst, FinOps. [docs/team.md](../team.md) gives the reasons. The Data or Product Analyst is the first candidate for the next step.

## Consequences

- Good: each important risk has an owner who writes it as checks. Makers cannot weaken the pipeline or the scanners that judge their work.
- Good: the default mode does not get heavier. The specialists join only when their area is at risk.
- Bad: more roles mean more routing decisions. A wrong selection can miss a risk or add cost. The evals of ADR-0012 measure this.
- Bad: in a small repository, the strict file ownership can block a simple change (for example a Dockerfile line in a feature). The conductor then adds the Platform Engineer, or the human changes `.magenta/policy.json`.
