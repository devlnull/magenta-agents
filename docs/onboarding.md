# Team guide

This guide is for an engineer in a team that uses Magenta. Read it in 15 minutes.

## 1. What Magenta is

AI agents with fixed roles: product, architecture, engineering, QA, reliability, platform, security, database, and documentation ([the team](team.md)). The success criteria and the rules of the agents become checks: commands that a machine runs. You approve the checks. A task is done only when they pass. The design is in [RFC-0001](rfc/RFC-0001-magenta-agents.md) and [ADR-0012](adr/0012-verify-first.md).

## 2. Install (one time)

```bash
claude plugin marketplace add devlnull/magenta-agents
claude plugin install magenta@magenta-marketplace
```

The plugin gives the agents `magenta:principal`, `magenta:product-manager`, `magenta:architect`, `magenta:qa`, `magenta:engineer`, `magenta:frontend`, `magenta:sre`, `magenta:platform`, `magenta:security`, `magenta:database`, and `magenta:writer`. Do not also install the user-level files (`python3 magenta.py install`). Use one of the two.

## 3. Prepare your repository (one time)

```bash
git clone https://github.com/devlnull/magenta-agents.git ~/.magenta-agents   # once, for the CLI
python3 ~/.magenta-agents/magenta.py init . --no-hook   # the plugin has the hooks
claude
```

Type `/magenta` with your first task. Magenta asks to run discover-project. Read `.magenta/project-context.md`. Correct it. Confirm it. Then approve the project checks (build, lint, unit tests) that it proposes.

## 4. Daily use

For most work, give Magenta the task in your own words:

```text
/magenta fix the rounding error in the order total for amounts over 1M
/magenta the p99 of GET /v2/addresses/default must be at or below 10 ms
/magenta review my branch against main
```

The conductor asks QA (and the Architect, when the structure is at risk) to write the checks first. You approve them at the checks gate. One lead agent does the work until all checks pass. Then one to three reviewers look at the diff. The report shows the verify table and the constraint check. For a large or risky task, Magenta uses team mode: start the request with `--team` to ask for it. You can also call one role directly:

| You want | Do this |
|---|---|
| A PRD review | `@magenta:product-manager review this PRD: <link or text>` |
| A design for a change | `@magenta:architect design <change> for the stories in <file>` |
| Edge cases and acceptance tests | `@magenta:qa find the edge cases of <story>` |
| A complete feature with gates | `claude --agent magenta:principal`, then "New work item: <request>" |
| A review of your branch | In a Principal session: "Run the PR review panel against main." |

## 5. Your duties as the human

- Approve or reject each gate. Only you can approve a gate.
- Read the checks that the agents propose, then approve them. Only you can approve a check. In Claude Code, Magenta requests the approval, and Claude Code shows a permission dialog: select **Yes** or **No**. In a terminal: `python3 ~/.magenta-agents/magenta.py verify approve`. Approve only commands that you trust: a check runs on your computer.
- Read the final review before you merge. The agents do not push or merge.
- Report wrong behavior: add a line to `.magenta/lessons.md` or open an issue in the magenta-agents repository.

## 6. Rules that the guard enforces

- Each agent writes only its own files. Makers do not change the checks or the locked tests.
- No agent reads `.env` files, keys, or `secrets/`.
- Shell commands: only the allowlist of each agent, without pipes or `;`.
- No model approves checks or writes the verify state.
- While a task is active and the code changed, the Stop hook does not let the agent finish until the approved checks pass. After two tries in one turn, it lets the agent stop and tells you.

If the guard blocks an agent, the agent reports it. Do not turn off the guard. If a rule is wrong for your repository, ask the owner of the repository to add it to `.magenta/policy.json`.

## 7. Feedback and metrics

Each month, the team lead runs `python3 magenta.py metrics <repos>` and reviews the costs, the gate results, and the lessons with the team.
