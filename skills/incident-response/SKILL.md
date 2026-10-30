---
name: incident-response
description: Handle a production incident - mitigate first, find the cause, and write a blameless postmortem. Use it for the incident playbook.
---

# Incident response

## During the incident

1. Write the impact: who is affected, since when, and how much.
2. Mitigate first. Prefer the fastest safe action: roll back the last change, turn off a feature flag, scale, or limit the traffic. The human runs it.
3. Keep a timeline with times and actions.
4. Keep the evidence: logs, metrics, traces, and the versions that ran.

## After the mitigation

1. Find the root cause with the skill `root-cause-analysis`.
2. Fix it with the bugfix playbook.

## Postmortem (blameless)

| Section | Content |
|---|---|
| Summary | What happened, the impact, and the duration |
| Timeline | Detection, mitigation, resolution, with times |
| Root cause | The cause and the evidence |
| What worked | Detection, tools, and actions that helped |
| What did not work | Gaps in alerts, tests, runbooks, or process |
| Actions | Each action with an owner and a date |
