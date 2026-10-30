## Playbook: reliability

Use it for SLOs, alerts, dashboards, observability, resilience (timeouts, retries, circuit breakers), capacity, and postmortem actions.

1. Conductor: write the brief: the user journey, the current SLI values and their source, and the target.
2. `sre`: write `03-reliability.md` with the skills `slo-observability` and `resilience-review`. Write the checks: lint of the alert rules, code rules as `git grep` checks. `qa`: write tests for the failure behavior (for example "the dependency times out, and the service returns the fallback").
3. Checks gate.
4. The lead makes the change: `engineer` for code (timeouts, retries, fallbacks, metrics), `platform` for alert rules, dashboards, and manifests. Run verify until the checks pass.
5. `sre` lens, and `qa` lens for changed behavior.
6. Done gate: the SLO effect, the alerts and their runbooks, and the rollback.
