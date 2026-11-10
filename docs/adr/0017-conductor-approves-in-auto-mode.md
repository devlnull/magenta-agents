# ADR-0017: The conductor approves the checks in auto mode

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-11-11 |
| Decider | AMQ |
| Source | Request: "the verify for each run or agent or any task even in auto mode is painful, I prefer to bypass it completely when auto mode is on ... orchestrator can verify based on what it think is the best choice" |
| Changes | ADR-0015, decision 1 ("`approve` and `--force` always ask") |

## Context

In one `--auto` task on go-address, Claude Code showed the approval dialog 52 times for `verify approve` and 23 times for `--force`. The human had to stay at the computer. ADR-0015 kept these two commands as decisions of the human, also in auto mode. The human wants a task that runs for hours without a dialog.

## Decision

1. In a task that the human started with `--auto`, `protect.evaluate` answers `auto` (allow without a prompt) for `approve` and `--force` from the conductor. The conductor is the main session of the task: the same session ID, and no `agent_type`.
2. Other subagents still get the dialog. The Magenta agents are still blocked (`decide`).
3. The Stop hook does not tell the human that checks wait. It sends the conductor back to work with the approve command.
4. The skill tells the conductor to read each check before it approves it, to write each approval and each `--force` in the brief, and to list them in the final report.

The other guardrails stay: the state files, the deletion of `.magenta/`, the locked tests, and the rules of the agents.

## Alternatives

- **An allow rule in the settings for `verify.py approve`.** Claude Code applies it in every task, also without `--auto`. Rejected: it removes the gate for all tasks.
- **No change, but one batched approval for each task.** The conductor did not batch well, and `--force` still asked. Rejected by the human.

## Consequences

- An `--auto` task can run to the end without the human.
- The human gate on the checks is gone in auto mode. The conductor can approve a weak check. The brief and the final report are the evidence for the human, after the task.
- Claude Code applies settings `ask` rules before hook decisions. In a repository where `magenta.py init` added the ask rules, the dialog still shows. Remove these rules from `.claude/settings.local.json` to get no dialog there.
- The release benchmark uses `--auto`, so its results can change.

## Examine again when

- A task in auto mode ships a change that a weak check approved.
- Claude Code lets a hook decision skip an `ask` rule.
