## Playbook: incident

Use it when production is down or degraded. Speed and safety come first.

1. `sre`: lead the response with the skill `incident-response`. Return the impact and a short timeline in the final message. The conductor writes them in `00-brief.md`.
2. Mitigate first: `sre` proposes the fastest safe mitigation (rollback, feature flag off, scale, rate limit, traffic shift). The human approves and runs it. Agents do not have production access.
3. `engineer` and `qa` in parallel, read-only: find the cause from the evidence that the human gives (logs, metrics, traces in `UNTRUSTED` blocks) with the skill `root-cause-analysis`. Add `platform` when a deployment or the infrastructure can be the cause.
4. Continue with the `bugfix` playbook for the permanent fix (lite lane is not permitted for an incident fix). The `principal` does the final review.
5. `sre`: write a blameless postmortem with the template `postmortem` in `docs/postmortems/`. Each action item has an owner, and a check when a command can test it. Update or write the runbook.
