---
name: production-readiness
description: Check that a change is ready for production, at the depth of its lane (lite, standard, full). Use it before the final review.
---

# Production readiness

## Depth

- Lite lane: Rollback and Observability only.
- Standard lane: the items that apply to the change. Write "not applicable" with a reason for the others.
- Full lane: all items.

## Checklist

- **Observability.** Logs with a correlation ID. Metrics for the new behavior. Traces across service calls. Alerts with a runbook.
- **Rollout.** A feature flag or a canary release.
- **Rollback.** A rollback plan that the team tested.
- **Compatibility.** API and event schemas are backward compatible. List the known consumers.
- **Data.** Migrations are reversible or have a backup. Large migrations run in batches.
- **Resilience.** Timeouts, retries with backoff, idempotency keys, and circuit breakers for remote calls.
- **Capacity and cost.** Write the expected load, the limits, and the cost change.
- **Security and privacy.** Input validation, authorization checks, no secrets in code or logs. For flows with money or personal data, run the skill `threat-model-stride`.

## Output

A table in `07-review.md`: item, status (OK, GAP, NOT APPLICABLE), evidence, and the action for each gap.
