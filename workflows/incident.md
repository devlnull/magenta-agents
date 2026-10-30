## Playbook: incident

Use it when production is down or degraded. Speed and safety come first.

1. `principal`: lead. Write a short timeline in `00-brief.md` (conductor) and the impact.
2. Mitigate first: `principal` proposes the fastest safe mitigation (rollback, feature flag off, scale, rate limit). The human approves and runs it. Agents do not have production access.
3. `engineer` and `qa` in parallel, read-only: find the cause from the evidence that the human gives (logs, metrics, traces in `UNTRUSTED` blocks) with the skill `root-cause-analysis`.
4. Continue with the `bugfix` playbook for the permanent fix (lite lane is not permitted for an incident fix).
5. `principal`: write a blameless postmortem with the skill `incident-response`: timeline, root cause, what worked, what did not, and actions with owners.
