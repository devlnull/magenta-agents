# ADR-0012: Verify first: checks as the definition of done, one lead, and review lenses

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | Review of the conductor (ADR-0010): "Is this approach correct? If you have a better idea, tell me." Decision: "do the best you think". |

## Context

The conductor of ADR-0010 runs a team of agents for each task. Two problems remain:

1. **The rules are text.** The constraint ledger asks each agent to keep the rules of the others, but nothing checks the result. A model can report "all tests pass" without a run, or make a test pass with a change to the test.
2. **A team is expensive and loses context.** Each handoff between agents loses detail. Reports on multi-agent systems show that most of the gain comes from more tokens and better verification, not from the number of agents. For one task, one agent with the full context makes fewer integration errors. Parallel agents help for read-only work: reviews, analysis, and competing hypotheses.

Most daily tasks (bugs, performance, refactors) have an objective test: a reproduction, a threshold, a rule. A check that a machine runs is better evidence than a review that a model writes.

## Decision

1. **Checks.** A check is a command that tests one rule. Exit code 0 means PASS. The checks are in `.magenta/checks/*.yaml`, one file for each owner: `qa.yaml` (QA), `architect.yaml` (Architect), `project.yaml` (Principal), and `human.yaml` (human). The guard lets each agent write only its own file.
2. **Human approval.** A check runs only after the human approves its exact command, folder, set, and work item. `.magenta/checks.lock` keeps a hash of each approved check. A changed or removed check fails until the human approves the change. The approval also seals the test locks: a lock that changes or disappears after the approval fails in the same way. The model cannot approve: the conductor skill does not pre-approve the `approve` command, the guard blocks it for the agents, and a protect hook blocks it, `--force`, and the state files for the main session.
3. **Verify.** `verify.py` runs the approved checks and records the result for the current code in `.magenta/verify-state.json`. A result counts only for the same code and the same approved check. The code fingerprint is a `git write-tree` of all files that git does not ignore, without `.magenta/`, plus the tests and locks in the work items. A commit of the same content does not change it. Verify saves the state after each check. If the code changes during a run, the run fails. In a linked git worktree, verify uses the checks and the approvals of the main working tree. On Windows, the checks run in Git Bash when it exists.
4. **Checks first.** Before the work starts, QA writes a check for each success criterion and a test that fails now (a reproduction, a threshold, or an acceptance test). The Architect writes the structural constraints as checks. The conductor locks the test files (`verify lock`). The human approves the checks at the checks gate. The new checks must fail before the change (red).
5. **Default mode: one lead, checks, and lenses.** One lead agent (`engineer`, `frontend`, or `qa`) does the change in one context and runs verify until all checks pass. Then one to three read-only lenses (QA, Architect, Principal) review the diff. A BLOCKER or MAJOR finding that a command can test becomes a new check.
6. **Team mode on triggers.** The playbooks of ADR-0010 stay for team mode: a PRD, a one-way-door decision, a change of a contract or a schema, money or security, more than one bounded context, a lead that failed three rounds, a tournament, or competing hypotheses. `--team` and `--lead` select the mode.
7. **Stop hook (Claude Code).** When a task of the session is active and the code changed, the Stop hook does not let the agent finish until the approved checks pass on the current code. The set `task` has these checks: the quick checks and the full checks of the work item. The hook blocks two times in one turn of the human, then it allows the stop and tells the human. While checks of the task wait for approval (the checks gate), it allows the stop and reminds the human. It does not block a session that does not own the task. The hook only compares fingerprints, so it is fast. User-level installs get the hooks with `magenta.py init` (in `.claude/settings.local.json`). The plugin has them in `hooks/hooks.json`. A hook command does nothing when its script was removed.
8. **No silent exit.** `finish` refuses to close a task that changed the code and does not pass. `start` refuses to replace such a task of the same session. Only the human can force them (`--force`).
9. **Freeze the other adapters.** The OpenCode, Codex CLI, and Gemini CLI adapters get bug fixes and the shared conductor (with the verify script), but no new features. They have no Stop hook. Claude Code is the primary tool (ADR-0002).
10. **Measure.** The evals compare three modes on the same tasks: plain (the tool without Magenta), default, and team. `magenta.py eval-summary` shows the correct rate, the rule breaks, the cost, and the time for each task type and mode.

## Consequences

- Good: "done" is a machine result, not a claim. The rules of the Architect and QA are enforced on each change. A smaller team costs less and loses less context. The human approves the definition of done one time, at the start.
- Good: findings become checks, so the same problem cannot come back silently.
- Bad: the quality of the result depends on the quality of the checks. A weak check gives a false pass. The QA lens and the human approval reduce this risk.
- Bad: the hook trusts `verify-state.json`. The main session is not a sandbox: a model that wants to cheat can write the file with a shell trick. The protect hook stops the simple cases. CI can run `verify run --set full` as the final authority.
- Bad: long checks (load tests) do not fit in one shell call of the tool. They go in the set `full`, and the conductor runs them in the background.
- Known limit: changes inside a git submodule that are not committed in the submodule do not change the fingerprint.
- Follow-up: run the three-mode evals on five real tasks. Change the team triggers when the data shows a better rule. Later, commit `.magenta/checks/` for the team and run the checks in CI.

## Alternatives

| Option | Why not |
|---|---|
| Keep the team as the default (ADR-0010) | Higher cost and more handoffs, without proof that the result is better for daily tasks. |
| An LLM judge as the definition of done | A judge is a model claim, not a measurement. Use it only where a command cannot test the rule. |
| Checks only in CI | The agent gets the result too late, after it stopped. Local checks let the lead fix the problem in the same session. |
| Let the model approve its own checks | The model could make a weak check and then pass it. The human must own the definition of done. |
