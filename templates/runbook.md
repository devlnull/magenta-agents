# Runbook: <alert or failure>

| Field | Value |
|---|---|
| Service | |
| Alert | <name and link> |
| SLO affected | |
| Owner | <team> |
| Last review | <date> |

## What it means
<the symptom that users feel, in one or two sentences>

## Check first
1. <dashboard link>: <what to look at>
2. <recent deployments or feature flags>
3. <the status of the dependencies>

## Mitigate
| Cause | Action | Who can do it |
|---|---|---|
| A recent deployment | Roll back: <steps> | On-call engineer |
| A dependency is slow | <turn off the feature flag, or use the fallback> | |

## Escalate
- When: <for example: no mitigation after 30 minutes>
- To: <team or person>

## After the incident
Write a postmortem with the template `postmortem`.
