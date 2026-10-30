# Magenta Agents

A team of six role-based AI agents for software work: Product Manager, Software Architect, Senior Principal Engineer, QA Engineer, Software Engineer, and Front-End Engineer. The agents work alone or as a team. They hand off files with fixed templates, and a human approves each important decision.

- Design: [RFC-0001](docs/rfc/RFC-0001-magenta-agents.md)
- Decisions: [docs/adr/](docs/adr/)
- Team guide: [docs/onboarding.md](docs/onboarding.md)

## Status

All phases are implemented. They wait for the first real test.

| Phase | Content |
|---|---|
| 0. Foundations | Constitution, templates, workflows, `discover-project`, Claude Code adapter, guard hook |
| 1. Advisors | `magenta-principal`, `magenta-product-manager`, `magenta-architect`, `magenta-qa` |
| 2. Makers | `magenta-engineer`, `magenta-frontend`, maker skills, acceptance-test lock |
| 3. Other tools and vendors | OpenCode and AGENTS.md (Codex CLI) adapters, model profiles for other vendors |
| 4. Runner | Headless `prd-review` and `pr-review`, budgets, logs, GitLab and GitHub CI templates |
| 5. Team rollout | Plugin and marketplace, onboarding guide, organization standards, metrics |
| 6. Conductor | `/magenta` for all daily tasks: task types, playbooks, dynamic teams, constraint ledger; entry points for Claude Code, OpenCode, Codex CLI, and Gemini CLI |

## Install

Magenta installs from this GitHub repository on macOS, Linux, and Windows.

| | macOS | Linux | Windows |
|---|---|---|---|
| Claude Code plugin | Yes | Yes | Yes (Claude Code uses Git Bash) |
| Installer script | `install.sh` | `install.sh` | `install.ps1` |
| Necessary | Python 3.9+, git | Python 3.9+, git | Python 3.9+, Git for Windows |

### Option 1: Claude Code plugin (recommended for teams)

```bash
claude plugin marketplace add devlnull/magenta-agents
claude plugin install magenta@magenta-marketplace
```

The agents are `magenta:principal`, `magenta:product-manager`, `magenta:architect`, `magenta:qa`, `magenta:engineer`, and `magenta:frontend`. Update: `claude plugin marketplace update magenta-marketplace`.

### Option 2: installer script (Claude Code user level, OpenCode, Codex CLI, or Gemini CLI)

macOS and Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/devlnull/magenta-agents/main/install.sh | sh
# other tool or version:
curl -fsSL https://raw.githubusercontent.com/devlnull/magenta-agents/main/install.sh | sh -s -- --target codex --ref v0.6.0
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/devlnull/magenta-agents/main/install.ps1 | iex
# other tool or version: set $env:MAGENTA_TARGET = "opencode" and $env:MAGENTA_REF = "v0.5.0" first
```

The script downloads the source to `~/.magenta-agents`, builds it, and installs it. The guard hook uses the Python that ran the install. Run the script again to update. Use the plugin or the script for Claude Code, not both.

### Option 3: from a clone

```bash
git clone https://github.com/devlnull/magenta-agents.git && cd magenta-agents
python3 magenta.py validate && python3 -m unittest discover -s tests
python3 magenta.py build
python3 magenta.py install                     # Claude Code, user level
python3 magenta.py install --target opencode   # optional
python3 magenta.py install --target codex      # optional: custom agents and $magenta
python3 magenta.py install --target gemini     # optional: subagents and /magenta
```

On Windows, use `py -3` or `python` in place of `python3`. The install does not replace a file that Magenta did not generate. To remove the installed files: `python3 magenta.py uninstall`.

## Prepare a product repository

```bash
python3 ~/.magenta-agents/magenta.py init /path/to/repository   # creates .magenta/ and keeps it out of git
cd /path/to/repository
claude                                        # then: /magenta <your task>
```

The first `/magenta` task asks to run discover-project. Review `.magenta/project-context.md` and confirm it.

## Use: `/magenta`

Give Magenta any daily task in your own words. The conductor analyzes the request, selects the task type and the agents, runs them together, and checks the result against the rules of all agents.

| Tool | Command |
|---|---|
| Claude Code | `/magenta <task>` (plugin: `/magenta:magenta <task>` if another `/magenta` exists) |
| OpenCode | `/magenta <task>` |
| Gemini CLI | `/magenta <task>` |
| Codex CLI | `$magenta <task>` |

Example:

```text
/magenta find the performance issues of GET /v2/addresses/default. The average is 10 ms now.
I need p95 at or below 5 ms; p99 can be 10 ms.
```

For this request, the conductor selects the task type "performance" and this team:

| Agent | Work in this task |
|---|---|
| Principal | Checks that the target is realistic, makes the latency budget, writes the plan and the constraint ledger, does the final review |
| QA | Writes the measurement plan, measures the baseline and each change, runs the functional tests |
| Engineer | Traces and profiles the code path, implements the selected option |
| Architect | Finds the structural causes, gives options with trade-offs, writes the structural constraints, does the rule check |

The result must meet the target **and** pass the constraint ledger: the ADRs and boundaries of the Architect, the tests and thresholds of QA, the readiness rules of the Principal, the project conventions, and your constraints. A faster solution that breaks a rule is rejected.

### Task types

| Task type | Example request | Core team |
|---|---|---|
| bug | "/magenta orders over 1M fail with a rounding error" | QA, Engineer, Principal |
| performance | "/magenta reduce the p99 of the search API to 50 ms" | QA, Engineer, Architect, Principal |
| improvement | "/magenta remove the duplicated price rules in checkout" | Architect, QA, Engineer, Principal |
| investigation | "/magenta why does the stock sync job run twice?" | Only the experts that the question needs |
| review | "/magenta review my branch against main" | QA, Architect, Principal |
| incident | "/magenta payments fail since the last deploy" | Principal, Engineer, QA |
| security | "/magenta fix CVE-2026-1234 in our JWT library use" | Principal, Architect, Engineer, QA |
| upgrade | "/magenta upgrade Spring Boot from 3.3 to 3.5" | Engineer, QA, Principal |
| tests | "/magenta fix the flaky OrderCancelTest" | QA, Engineer |
| design | "/magenta design the retry strategy for the shipping events" | Architect, Principal |
| feature | "/magenta implement this PRD: ..." | PM, Architect, QA, Engineer, Principal |

The routing table and the playbooks are in [`workflows/`](workflows/). The conductor uses the smallest team that covers the risks.

### Gates

You stay in control. Small, clear tasks have one gate at the end (done gate). Other tasks also have a plan gate: you approve the brief, the success criteria, the team, the plan, and the constraint ledger. Features also have the PRD gate. Magenta never pushes or merges.

### More commands

| You want | Do this |
|---|---|
| One role only | `@magenta-architect`, `@magenta-qa`, and the other agents, in any session |
| The lead agent as the main session | `claude --agent magenta-principal` |
| Lock the acceptance tests (you, after review) | `python3 magenta.py lock <repo> <work-item>` |
| Check the lock (QA, CI, pre-commit) | `python3 magenta.py check-lock <repo> <work-item>` |
| A headless PRD review | `python3 magenta.py run prd-review --repo <repo> --prd <file>` |
| A headless review panel (CI) | `python3 magenta.py run pr-review --repo <repo> --base origin/main` |
| Numbers for the retrospective | `python3 magenta.py metrics <repo> [<repo> ...]` |

Start each session in the root folder of the repository. The guard uses it as the project root.

## Enforcement

| Tool | How the rules are enforced |
|---|---|
| Claude Code (user level) | A `PreToolUse` guard hook in each agent (`~/.claude/magenta/guard.py`) |
| Claude Code (team plugin) | One plugin hook, `guard.py --auto`, that finds the agent by its name |
| OpenCode | Ordered permission rules in each agent |
| Codex CLI | Write and shell rules as instructions in each custom agent, plus the Codex sandbox and approvals |
| Gemini CLI | Write and shell rules as instructions in each subagent, plus the Gemini approvals |
| Other AGENTS.md tools | Instructions only. Use them for advisors. |

The guard blocks writes outside the files of the agent, access to secret paths, shell commands outside the allowlist, all shell operators (`;`, `|`, `>`, and more), and writes to `.magenta/policy.json`, `acceptance.lock`, `.claude/`, and `.git/`.

A repository can extend the rules in `.magenta/policy.json`. Only the human changes this file:

```json
{
  "qa":       { "writes": ["src/acceptanceTest/**"], "shell": ["./gradlew acceptanceTest*"] },
  "engineer": { "writes": ["!src/acceptanceTest/**"] }
}
```

## Models

Agents name a profile. `models.yaml` maps each profile to a model for each tool and to an engine for the runner. To use OpenAI, Gemini, Grok, or a self-hosted model, fill in the commented `opencode` and `runner` lines with model IDs that you have access to, then build again.

## Release a new version

1. Optional: copy `standards/organization.example.md` to `standards/organization.md` and write your organization standards.
2. Increase `release` in `magenta.yaml`.
3. Run `python3 magenta.py build`. It also updates the committed plugin (`plugins/magenta/`, `.claude-plugin/marketplace.json`).
4. Run `python3 magenta.py check` and the tests. Commit and push. CI tests macOS, Linux, and Windows.
5. Create a tag, for example `git tag v0.5.0 && git push origin v0.5.0`. Users can install that version with `--ref v0.5.0`.

## Repository layout

```mermaid
flowchart LR
  ROOT(["magenta-agents/"]) --> CFG["magenta.yaml, models.yaml"]
  ROOT --> AG["agents/<br/>one file for each role"]
  ROOT --> RU["rules/ and standards/<br/>the constitution"]
  ROOT --> SK["skills/<br/>Agent Skills format"]
  ROOT --> TP["templates/ and workflows/<br/>built into magenta-templates<br/>and magenta-workflow"]
  ROOT --> AD["adapters/<br/>claude_code, opencode, agents_md,<br/>plugin, guard, lock, metrics"]
  ROOT --> RN["runner/<br/>headless runner"]
  ROOT --> CI["ci/<br/>GitLab and GitHub templates"]
  ROOT --> EV["evals/ and tests/"]
  ROOT --> PL["plugins/ and .claude-plugin/<br/>generated team plugin, in git"]
  ROOT --> IN["install.sh, install.ps1"]
  ROOT --> DS["dist/<br/>generated, not in git"]
  ROOT --> DC["docs/<br/>RFC, ADRs, onboarding"]
```

## Change the agents

1. Edit the source (never `dist/`).
2. Run `python3 magenta.py validate` and `python3 -m unittest discover -s tests`.
3. Run `python3 magenta.py build` and install again.
4. Run the evals (`evals/README.md`).
