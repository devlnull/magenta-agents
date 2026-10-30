# User guide

This guide shows how to install Magenta and use it in daily work. For all commands and configuration files, see the [reference](reference.md).

## Install

Magenta installs from GitHub on macOS, Linux, and Windows.

| | macOS | Linux | Windows |
|---|---|---|---|
| Claude Code plugin | Yes | Yes | Yes (Claude Code uses Git Bash) |
| Installer script | `install.sh` | `install.sh` | `install.ps1` |
| Necessary | Python 3.9+, git | Python 3.9+, git | Python 3.9+, Git for Windows |

Use the plugin or the installer for Claude Code, not both.

### Option 1: Claude Code plugin

```bash
claude plugin marketplace add devlnull/magenta-agents
claude plugin install magenta@magenta-marketplace
```

The agents are `magenta:principal`, `magenta:product-manager`, `magenta:architect`, `magenta:qa`, `magenta:engineer`, and `magenta:frontend`. To update: `claude plugin marketplace update magenta-marketplace`.

### Option 2: installer script

The installer supports Claude Code (user level), OpenCode, Codex CLI, and Gemini CLI.

macOS and Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/devlnull/magenta-agents/main/install.sh | sh
# another tool or version:
curl -fsSL https://raw.githubusercontent.com/devlnull/magenta-agents/main/install.sh | sh -s -- --target codex --ref v0.7.1
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/devlnull/magenta-agents/main/install.ps1 | iex
# another tool or version: first set $env:MAGENTA_TARGET = "opencode" and $env:MAGENTA_REF = "v0.7.1"
```

The script downloads the source to `~/.magenta-agents`, builds it, and installs it. The hooks use the Python that ran the install. To update, run the script again.

### Option 3: from a release or a clone

Download `magenta-agents-<version>.zip` from the [releases](https://github.com/devlnull/magenta-agents/releases) (it installs without network), or clone the repository:

```bash
git clone https://github.com/devlnull/magenta-agents.git && cd magenta-agents
python3 magenta.py build
python3 magenta.py install                     # Claude Code, user level
python3 magenta.py install --target opencode   # or codex, or gemini
```

On Windows, use `py -3` or `python` in place of `python3`. The install does not replace a file that Magenta did not generate. To remove the installed files: `python3 magenta.py uninstall`.

## Prepare a repository

```bash
python3 ~/.magenta-agents/magenta.py init /path/to/repository
```

`init` makes the folder `.magenta/` and keeps it out of git. For a user-level Claude Code install, it also adds two hooks to `.claude/settings.local.json`: the Stop hook that enforces the checks, and a hook that protects the verify state. The plugin has these hooks already, so use `init --no-hook` with the plugin. To remove the hooks: `magenta.py unhook <repo>`.

The first `/magenta` task asks to run discover-project. It writes `.magenta/project-context.md` (the conventions of your repository) and proposes the project checks (build, lint, unit tests). Read the profile, correct it, and confirm it. Then approve the checks.

## Run a task

Give Magenta any task in your own words. Start the session in the root folder of the repository.

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

| Step | Who | What happens |
|---|---|---|
| 1. Checks first | QA | Writes a load test with the thresholds (for example k6 with `p(95)<5` and `p(99)<10`) and a regression test, as checks of the task. They fail now. |
| | Architect | Writes the structural rules as checks, for example "the cache stays inside the address module". |
| 2. Checks gate | You | Read the checks and approve them. |
| 3. Work | Engineer (the lead) | Profiles the code path, changes one thing at a time, and runs verify until all checks pass. |
| 4. Review | QA, Architect, Principal | Read the diff. A serious finding becomes a new check. |
| 5. Done gate | You | Read the report with the verify table. You merge, ask for more work, or stop. |

The result must meet the target **and** keep the rules of all roles. A faster solution that breaks a check is rejected.

## Modes

| Mode | When | How |
|---|---|---|
| Default: lead, checks, lenses | Most tasks | QA and the Architect write the checks. One lead does the work. One to three reviewers ("lenses") read the result. |
| Team | A PRD, a one-way-door decision, a change of a contract or a schema, money or security, more than one bounded context, or a lead that failed three rounds | The playbook of the task type, with its core team and gates |

To select the mode yourself, start the request with `--team` or `--lead`.

## Task types

| Task type | Example request | Default mode | Team mode |
|---|---|---|---|
| bug | "orders over 1M fail with a rounding error" | QA: a test that reproduces the bug. Lead: Engineer. | QA, Engineer, Principal |
| performance | "reduce the p99 of the search API to 50 ms" | QA: thresholds. Architect: rules. Lead: Engineer. | QA, Engineer, Architect, Principal |
| improvement | "remove the duplicated price rules in checkout" | QA: characterization tests. Architect: target rules. Lead: Engineer. | Architect, QA, Engineer, Principal |
| investigation | "why does the stock sync job run twice?" | No checks. The experts answer. | The experts that the question needs |
| review | "review my branch against main" | The review panel. | QA, Architect, Principal |
| incident | "payments fail since the last deploy" | Lead: Engineer. A check for the failure, when there is time. | Principal, Engineer, QA |
| security | "fix CVE-2026-1234 in our JWT library use" | Always team mode. | Principal, Architect, Engineer, QA |
| upgrade | "upgrade Spring Boot from 3.3 to 3.5" | Project checks and smoke tests. Lead: Engineer. | Engineer, QA, Principal |
| tests | "fix the flaky OrderCancelTest" | Project checks. Lead: QA. | QA, Engineer |
| design | "design the retry strategy for the shipping events" | Lead: Architect. | Architect, Principal |
| feature | "implement this PRD: ..." | Small and clear: QA acceptance tests. Lead: Engineer or Front-End. | PM, Architect, QA, Engineer, Principal |

The routing table and the playbooks are in [`workflows/`](../workflows/).

## Gates

You stay in control. The default mode has two gates: the **checks gate** (you approve the checks and a short plan) and the **done gate**. Team mode adds a plan gate, and features add a PRD gate. Magenta never pushes, merges, or deploys.

## Checks

A check is a command that tests one rule. Exit code 0 means PASS. Each owner has one file in `.magenta/checks/`:

| File | Owner |
|---|---|
| `project.yaml` | Principal: build, lint, unit tests |
| `qa.yaml` | QA: tests, thresholds, regression tests |
| `architect.yaml` | Architect: structural rules |
| `human.yaml` | You |

Example:

```yaml
checks:
  - id: qa.addresses-default-latency
    name: "GET /v2/addresses/default: p95 at or below 5 ms, p99 at or below 10 ms"
    command: k6 run --quiet perf/addresses-default.js
    set: full                      # quick | full | manual
    work_item: 20261030-addresses-latency
    why: "Success criteria of the task"
```

| Set | Runs with |
|---|---|
| `quick` | each verify run |
| `full` | `run --set full`, or `run --set task` when the check belongs to the active task |
| `manual` | `run --set all` only |

A check runs only after you approve its exact command, set, and work item. If an agent changes an approved check, the check fails until you approve the change. Your approval also seals the locked tests of the task. Approve when Magenta asks: in Claude Code, type the command that Magenta shows after `!`, or run:

```bash
python3 ~/.magenta-agents/magenta.py verify approve --repo .
```

Approve only commands that you trust. A check runs on your computer.

## Use one role

You can call one agent directly, in any session:

| You want | Do this |
|---|---|
| A PRD review | `@magenta-product-manager review this PRD: <link or text>` |
| A design | `@magenta-architect design <change>` |
| Edge cases and acceptance tests | `@magenta-qa find the edge cases of <story>` |
| The lead agent as the main session | `claude --agent magenta-principal` |

With the plugin, the names are `magenta:<role>`, for example `@magenta:qa`.
