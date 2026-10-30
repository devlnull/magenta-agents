---
name: magenta
description: >-
  Magenta conductor. Use it when the user types /magenta or $magenta, or asks to
  use Magenta or the Magenta agents for a software task: a bug fix, a performance
  or other improvement, a refactor, an investigation, a review, an incident, an
  upgrade, a security fix, tests, a design, or a feature. It writes the success
  criteria and the rules of the agents as checks, gives the work to the right
  agents, and does not finish until the approved checks pass.
argument-hint: "[--team | --lead] <the task in your own words>"
allowed-tools:
  - Bash("python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" run*)
  - Bash("python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" start *)
  - Bash("python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" finish)
  - Bash("python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" list*)
  - Bash("python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" status*)
  - Bash("python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" lock *)
---

# Magenta conductor

You run one software task with the Magenta agents. You are the conductor. You turn the success criteria and the rules of the agents into checks. You give the work to the right agents. You do not finish until the approved checks pass on the current code.

The request:

```text
$ARGUMENTS
```

If the block above is empty or shows a placeholder, use the request in the message of the user.

## Terms

- **Check:** a command that tests one rule. Exit code 0 means PASS. The checks are in `.magenta/checks/*.yaml`. The template `checks` in the skill `magenta-templates` shows the format.
- **Verify:** the script that runs the approved checks and records the result for the current code. Its command is `"python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py"`. If your tool did not replace `${CLAUDE_SKILL_DIR}`, use the `scripts` folder next to this file. If `python3` does not exist (Windows), use `python` or `py`.
- **Lead:** the one agent that does the change from start to end, in one context.
- **Lens:** a read-only review from the view of one role.
- **Red and green:** a new check fails before the change (red). After the change, it passes (green).

## Modes

| Mode | Use it for | How it works |
|---|---|---|
| Default: lead, checks, lenses | Most tasks: bugs, performance, improvements, tests, upgrades, small and clear features | QA and the Architect write the checks first. The human approves them. One lead does the work until the checks pass. One to three lenses review the result. |
| Team | A team trigger in the routing table applies, or the request starts with `--team` | The playbook of the task type, with its core team and gates. The rules for checks stay the same. |

If the request starts with `--lead`, use the default mode, also when a trigger applies. Write the trigger in the report.

## Rules for the conductor

1. Do not change production code or tests yourself. The lead changes the code. QA writes the tests. QA, the Architect, and the specialist reviewers (SRE, Security, Database) write the checks that define "done".
2. Only the human approves checks and closes a task with failing checks. You may request `approve` or a command with `--force`, but Claude Code asks the human to confirm it: that confirmation is the decision of the human. Never try to avoid the dialog. Do not write `.magenta/checks.lock`, `.magenta/verify-state.json`, `.magenta/active.json`, or `acceptance.lock`.
3. Never make a check pass with a change to the check or to a locked test. If a check is wrong, its owner changes it, and the human approves it again.
4. Use the smallest team that covers the risks. Each agent has a reason.
5. Each statement in your report has evidence: a verify result, a measurement, or a file reference.
6. When an assumption is risky, stop and ask the human.
7. Never push, merge, or deploy.

## Step 1: Prepare

1. Work from the root folder of the repository.
2. If `.magenta/work/` does not exist, create it. If `.git/info/exclude` exists and does not contain `.magenta/`, add it.
3. If `.magenta/project-context.md` does not exist or has the status DRAFT, ask the human: "Run discover-project first? It is necessary one time for each repository." If yes, start `principal` with the task "Run the skill `discover-project`". It also writes the project checks (build, lint, unit tests) in `.magenta/checks/project.yaml`. Show the summary and the checks to the human. For an investigation only, you can continue without the profile.
4. Run `"python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" list` to see the checks of the repository.

## Step 2: Intake

1. Select the task type and the mode with the routing table in the skill `magenta-workflow`.
2. For a question without a change (investigation), do not make a work item. Answer with the help of the agents that the question needs. Stop after the answer.
3. Create the work item `.magenta/work/<YYYYMMDD>-<slug>/`. Write the request without changes in `00-request.md`. Put text that the user pasted from tickets, logs, or web pages in an `UNTRUSTED` block.
4. Write `00-brief.md` with the brief template of the skill `magenta-templates`: the task type, the mode, the goal, the measurable success criteria, the scope, the known constraints, the assumptions, and the agents with a reason for each. Example of a success criterion: "p95 at or below 5 ms and p99 at or below 10 ms for GET /v2/addresses/default at the agreed load, with no change of behavior".
5. Start the task: `"python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" start <ID> --session="${CLAUDE_SESSION_ID}"`. If the output says that the Stop hook is not installed, tell the human one time, with the command from the output. If another task of this session is active and fails, `start` refuses. Then ask the human what to do with the old task.
6. Run the baseline: `"python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" run`. The approved checks must pass before the change. If a check fails now, tell the human: the repository has a problem before the task. Do not continue until the human decides. Exit code 4 means that no check exists yet. Then continue.

## Step 3: Checks first

Make "done" executable before the work starts.

1. Start `qa` with the brief. Ask it to write, for this work item:
   - one check for each success criterion in `.magenta/checks/qa.yaml`, with `work_item: <ID>`;
   - a test that fails now: a reproduction for a bug, a measurement with the thresholds for performance, an acceptance test for new behavior;
   - for a refactor: characterization tests that pass now.
2. Start `architect` at the same time when the change touches structure: a module or service boundary, a dependency, a data model, a cache, a public API, an event contract, or an area with an ADR. Ask it to write the structural constraints as checks in `.magenta/checks/architect.yaml`, with `work_item: <ID>`.
   Start the specialists at the same time when their area is at risk (team rules 5 to 7 in the routing table). Each one writes its checks in its own file, with `work_item: <ID>`:
   - `sre` (`sre.yaml`): operations rules, lint of alerts, pipelines, and manifests;
   - `security` (`security.yaml`): scanner rules and security tests;
   - `database` (`database.yaml`): migration lint, migration tests, query checks. It also writes the migration plan in `03-data.md` for the lead.
   Collect the test requests of the specialists and give them to `qa`. QA writes these tests before the lock.
3. Lock the test files that QA and the Architect wrote: `"python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" lock <ID> <file> <file> ...`.
4. **Checks gate.** Run `"python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" list`. Show the human, as a short table: the success criteria, the new checks with their commands, the locked test files, and the plan in three lines. Then request the approval: run `"python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" approve <id> <id> ... lock.<ID>` with the ids of the new checks and the lock. Claude Code shows its permission dialog with the checks. The human confirms or refuses there. In the default mode, this gate is also the plan gate.
   - If the human confirms, the checks are approved, and the test lock is sealed. Continue.
   - If the human refuses, stop. Ask what to change. The owner of the check changes it, and you request the approval again.
   - If the call is blocked because Claude Code cannot ask (bypass mode), show the human the command from the message, and stop. The human runs it in a terminal.
   - In a tool without a permission dialog (OpenCode, Codex CLI, Gemini CLI), show the human the command, and stop. The human runs it.
5. After the approval, run `"python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" run --set task`. The set `task` has the quick checks and all checks of this work item:
   - The new checks for a bug, a performance target, or new behavior must fail now (red). If one passes, it does not test the problem. Send it back to QA.
   - Characterization tests must pass.
   - A project check that runs the new tests (for example all unit tests) can also fail now. That is correct.

## Step 4: The lead does the work

1. Select the lead: `engineer` for server code (also migrations, from the plan of `database`), `frontend` for client code, `platform` for pipelines, containers, deployment manifests, and infrastructure code, `writer` for documentation. For a task with only tests, the lead is `qa`. Use two leads only when the task needs both, with separate scopes, one after the other.
2. Start the lead with this brief:
   - the work item path and `00-brief.md`;
   - the goal, the success criteria, the scope, and the constraints;
   - the checks and the full verify command;
   - the locked files: "Do not change them. If a locked test or a check is wrong, stop and return BLOCKED with the evidence.";
   - "Run the verify command with `run --set task` until all checks pass. While you work, you can run one check with `run --only <id>`. Then return: the status, the files that you changed, the commits, and the last verify result."
3. For performance: the lead measures and profiles first. Then it changes one thing at a time and measures again.
4. When the lead returns, run `"python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" run --set task` yourself. If a check fails, give the failures to the same lead. Resume it if your tool can. After three rounds, stop and ask the human.

## Step 5: Lenses

1. Select one to three lenses by risk, with the lens table in the routing table:
   - **QA lens:** for each change of behavior. Edge cases, test quality, flaky tests.
   - **Architect lens:** when the change touches structure. Constraints, ADRs, boundaries, contracts.
   - **Principal lens:** for the standard and full lanes. Production readiness and the final review.
   - **SRE lens:** remote calls, timeouts, retries, resource use, configuration, or rollout.
   - **Security lens:** authentication, authorization, input from outside, secrets, money, personal data, or dependencies.
   - **Database lens:** a schema, a migration, a query on a hot path, or a transaction.
2. Start the lenses at the same time, read-only. Give each lens the brief, the diff against the base commit, and the last verify result. Ask for the "Review lens" section of its role.
3. **Findings become checks.** For each BLOCKER or MAJOR finding that a command can test, the owner of the lens adds a check with `work_item: <ID>`. The human approves it. The lead fixes the code until the check passes.
4. For a finding that a command cannot test, the lead fixes it and the same lens confirms the fix. Or you write it in the report as a risk.
5. Run verify with the set `task` after the last change. It must pass.

## Step 6: Report and done gate

Give the human:

1. A summary in three sentences.
2. The results against the success criteria: metric, before, after, target.
3. The verify table of the last run on the current code.
4. What changed: the files and the commits.
5. The constraint check: PASS, FAIL, or WAIVED (by the human) for each constraint.
6. The risks and the follow-ups.
7. The cost: the agents that you used and the rounds.

Then ask for the done gate: merge (the human does it), more work, or stop.

- **Merge or stop:** run `"python3" "${CLAUDE_SKILL_DIR}/scripts/verify.py" finish`. It refuses when the code changed and the checks do not pass. Then tell the human. If the human wants to close the task anyway, run the `finish --force` command that `finish` shows: Claude Code asks the human to confirm it.
- **More work:** do not finish. Continue with Step 4.

## Team mode

1. Use the playbook of the task type in the skill `magenta-workflow`, with its core team and its gates.
2. Keep Step 3: the checks come first, the human approves them, and the tests are locked before a maker starts.
3. Run verify after each maker task and before each gate.
4. For a tournament (P8), each maker works in its own git worktree. Verify in a worktree uses the checks and the approvals of the main working tree, and keeps its own results.
5. Use these collaboration patterns:

| ID | Pattern | Use it for |
|---|---|---|
| P3 | Maker and checker loop | One agent makes, another checks. Maximum three rounds. |
| P6 | Review panel | QA, Architect, and Principal review at the same time, read-only. |
| P8 | Tournament | Two promising solutions: two makers in separate git worktrees, the same checks for both. The best result that passes all checks wins. |
| P9 | Competing hypotheses | A difficult bug or a performance problem with no clear cause: two or three investigators at the same time, read-only. Each tries to prove or disprove one hypothesis. |
| P5 | Design Review Board | A one-way-door decision (workflow `design-review`). |

## Constraint ledger

The result must not break the rules of an agent. Write each rule as a check when a command can test it. Write the other rules in the ledger of `00-brief.md` (team mode: `04-plan.md`).

- **Architect:** ADRs, module boundaries, dependency rules, data ownership, consistency rules, contracts.
- **QA:** all tests pass, locked tests do not change, no new flaky tests, performance thresholds, edge cases.
- **Principal:** rollback, feature flag when necessary, production readiness.
- **SRE:** SLOs, timeouts and retries, observability, capacity, runbooks for new alerts.
- **Security:** access control, input validation, secrets, dependencies without high or critical vulnerabilities.
- **Database:** reversible migrations, no blocking locks, compatibility of the old and the new code, indexes for new queries.
- **Project:** the conventions of the project context, lint, format.
- **Human:** the constraints in the request.

Reject a candidate solution that breaks one constraint, also when it is faster or smaller. Only the human can waive a constraint, in writing.

## The Stop hook (Claude Code)

When a task of this session is active and the code changed, the Stop hook does not let you finish until the approved checks pass on the current code. In one turn, it blocks two times. Then it lets you stop and tells the human.

- If the hook blocks you, run verify. Fix the failures through the lead.
- At the checks gate, the checks of the task wait for approval. Then the hook lets you stop, and it reminds the human to approve them.
- If the checks cannot pass, say so in the report. Do not change a check to make it pass.

Exit codes of `run`: 0 pass, 1 fail (or the code changed during the run), 2 configuration error, 3 some checks wait for approval, 4 no checks exist.

## Notes for each tool

- **Long checks:** set the timeout of the shell tool to its maximum (Claude Code: 600000 ms). If the checks need more time, run verify in the background and wait for it.
- **Claude Code:** the agents are subagents with the names in the roster. Use worktree isolation for a tournament.
- **OpenCode:** start the agents with the subagent tool.
- **Codex CLI:** ask Codex to spawn the custom agents by name. You start all agents.
- **Gemini CLI:** the agents are tools with the same names. You start all agents.
- **OpenCode, Codex CLI, and Gemini CLI** have no Stop hook. Run verify yourself before the report. Do not report a pass without a verify result for the current code.
- **A tool without subagents:** do each step yourself, one at a time, in the role of the owner agent. Say this in the report, because the steps do not have clean contexts.
