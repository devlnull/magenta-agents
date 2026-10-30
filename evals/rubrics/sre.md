# Rubric: Site Reliability Engineer

Score each criterion: 0 (no), 1 (partly), 2 (yes).

1. The SLIs measure what users feel, and each SLO has a number and a window.
2. Alerts use the burn rate of the error budget. Each alert has a runbook.
3. The review finds the missing timeouts, unsafe retries, and missing fallbacks that a senior SRE found in the real case.
4. The capacity estimate has numbers for the load, the use for each request, and the limits.
5. The rollout and the rollback are concrete and possible.
6. For an incident: the mitigation comes before the root cause, and the human does each production action.
7. The postmortem is blameless, and each action item has an owner and, where possible, a check.
