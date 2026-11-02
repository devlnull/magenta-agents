# ADR-0015: Auto mode and task-level results

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-11-02 |
| Decider | AMQ |
| Source | Request: "always locking by permission of user for agents, I prefer to have a flag ... -auto ... just important parts should be confirm by user", and "the user only care about final result by agents, not those internal state changes" |

## Context

After two days of real use:

- Claude Code asked the human to confirm many tool calls of the agents. The human had to stay at the computer for the whole task.
- The human saw internal work: test locks, verify runs, hook messages ("Stop hook error", "PreToolUse hook error"), and the reports of each agent. The human wants the result of the task.

## Decision

1. **Auto mode.** `/magenta --auto <task>` gives one permission for the whole task. `verify.py start --auto` records it in the active task. While the task is active, the PreToolUse hooks of Magenta answer `allow` for each call of that session that passes the rules. The human decides only at the checks gate (one approval), at a blocker, and at the done gate. `approve` and `--force` always ask.
2. **Quiet hooks.** Blocks are JSON decisions: `deny` for the guard, `decision: block` for the Stop and SubagentStop hooks. The reason goes to the model. The human sees a note only when the human must act, one time for each state.
3. **A result contract.** Each agent ends with one Result block: status, summary, changes, evidence, findings, and (only for NEEDS-HUMAN) the question. The conductor reads only this block. It talks to the human only for questions, the checks to approve, and the final report.

## Consequences

- A task can run to the end without the human, except for the approval of the checks.
- Auto mode never allows a call that the rules block, and never removes a decision of the human.
- The tool calls stay visible in the transcript of Claude Code, but the messages of Magenta and of the conductor are about the task.
