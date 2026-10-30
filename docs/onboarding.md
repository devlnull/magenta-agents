# Magenta onboarding (pilot team, phase 5)

This guide is for an engineer who joins the Magenta pilot. Read it in 15 minutes.

## 1. What Magenta is

Six AI agents with fixed roles: Product Manager, Software Architect, Senior Principal Engineer, QA Engineer, Software Engineer, and Front-End Engineer. They hand off files with templates. You approve each gate. The design is in [RFC-0001](rfc/RFC-0001-magenta-agents.md).

## 2. Install (one time)

```bash
claude plugin marketplace add devlnull/magenta-agents
claude plugin install magenta@magenta-marketplace
```

The plugin gives the agents `magenta:principal`, `magenta:product-manager`, `magenta:architect`, `magenta:qa`, `magenta:engineer`, and `magenta:frontend`. Do not also install the user-level files (`python3 magenta.py install`). Use one of the two.

## 3. Prepare your repository (one time)

```bash
git clone https://github.com/devlnull/magenta-agents.git ~/.magenta-agents   # once, for the CLI
python3 ~/.magenta-agents/magenta.py init .
claude --agent magenta:principal
```

Ask: "Run discover-project." Read `.magenta/project-context.md`. Correct it. Confirm it.

## 4. Daily use

| You want | Do this |
|---|---|
| A PRD review | `@magenta:product-manager review this PRD: <link or text>` |
| A design for a change | `@magenta:architect design <change> for the stories in <file>` |
| Edge cases and acceptance tests | `@magenta:qa find the edge cases of <story>` |
| A complete feature with gates | `claude --agent magenta:principal`, then "New work item: <request>" |
| A review of your branch | In a Principal session: "Run the PR review panel against main." |

## 5. Your duties as the human

- Approve or reject each gate. Only you can approve a gate.
- Review the acceptance tests, then lock them: `python3 ~/.magenta-agents/magenta.py lock . <ID>`.
- Read the final review before you merge. The agents do not push or merge.
- Report wrong behavior: add a line to `.magenta/lessons.md` or open an issue in the magenta-agents repository.

## 6. Rules that the guard enforces

- Each agent writes only its own files. Makers do not change the acceptance tests.
- No agent reads `.env` files, keys, or `secrets/`.
- Shell commands: only the allowlist of each agent, without pipes or `;`.

If the guard blocks an agent, the agent reports it. Do not turn off the guard. If a rule is wrong for your repository, ask the maintainer to add it to `.magenta/policy.json`.

## 7. Feedback and metrics

Each month, the maintainer runs `python3 magenta.py metrics <repos>` and reviews the costs, the gate results, and the lessons with the team.
