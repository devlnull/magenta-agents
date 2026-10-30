# Reference

## Commands

All commands run with `python3 magenta.py <command>` from the Magenta folder (for example `~/.magenta-agents`). On Windows, use `py -3` or `python`.

### Install and build

| Command | Effect |
|---|---|
| `validate` | Check the canonical source. |
| `build` | Generate the files for all tools in `dist/`, and the committed plugin. |
| `check` | Fail if the committed plugin is not current. |
| `install [--target claude-code\|opencode\|codex\|gemini] [--force]` | Install for one tool, at user level. |
| `uninstall` | Remove the installed files and the hooks that `init` added. |
| `package [--out DIR]` | Build the release assets: `magenta-agents-<version>.zip`, `magenta-plugin-<version>.zip`, and `SHA256SUMS`. |

### Repositories and checks

| Command | Effect |
|---|---|
| `init <repo> [--no-hook]` | Make `.magenta/`, keep it out of git, and add the Claude Code hooks. |
| `unhook <repo>` | Remove the Claude Code hooks of Magenta. |
| `verify list --repo <repo>` | Show the checks, the test locks, and their approval. |
| `verify approve [ID ...] --repo <repo>` | Approve new and changed checks, and seal the test locks. Only the human runs it. |
| `verify run [--set quick\|task\|full\|all] [--only ID,ID] --repo <repo>` | Run the approved checks and record the result. |
| `verify status --repo <repo>` | Show the active task and the result for the current code. |
| `lock <repo> <work-item> [--files FILE ...]` | Lock the tests of a work item. |
| `check-lock <repo> <work-item>` | Fail if the locked tests changed. |

Exit codes of `verify run`: 0 pass, 1 fail (or the code changed during the run), 2 configuration error, 3 some checks wait for approval, 4 no checks exist.

### Headless and metrics

| Command | Effect |
|---|---|
| `run prd-review --repo <repo> --prd <file>` | Review a PRD without a session. |
| `run pr-review --repo <repo> --base origin/main [--fail-on-blocker]` | Run the review panel on a branch, for example in CI. See [`runner/`](../runner/) and [`ci/`](../ci/). |
| `metrics <repo> [<repo> ...]` | Report the work items and the costs. |
| `eval-summary` | Compare the eval runs of the modes plain, default, and team. See [`evals/`](../evals/). |

## Files in a product repository

```text
.magenta/                      kept out of git by `init`
  project-context.md           the conventions of the repository (Principal)
  product-context.md           strategy and metrics (you)
  lessons.md                   lessons from retrospectives (Principal)
  checks/*.yaml                the checks, one file for each owner
  checks.lock                  your approvals (verify script only)
  policy.json                  extra rules for the agents (you only)
  work/<YYYYMMDD>-<slug>/      one folder for each task: brief, plan, reports, locked tests
.claude/settings.local.json    the Claude Code hooks (from `init`)
```

### `.magenta/policy.json`

A repository can extend the rules of an agent. Only you change this file. A pattern that starts with `!` denies. The last matching pattern wins.

```json
{
  "qa":       { "writes": ["src/acceptanceTest/**"], "shell": ["./gradlew acceptanceTest*"] },
  "engineer": { "writes": ["!src/acceptanceTest/**"] }
}
```

## Enforcement

| Tool | Rules of the agents | Checks |
|---|---|---|
| Claude Code (user level) | A guard hook in each agent | The verify script, and the Stop and protect hooks from `init` |
| Claude Code (plugin) | One plugin guard hook for all sessions | The verify script, and the Stop hook of the plugin |
| OpenCode | Ordered permission rules in each agent | The verify script, run by the conductor |
| Codex CLI | Rules as instructions, plus the Codex sandbox and approvals | The verify script, run by the conductor |
| Gemini CLI | Rules as instructions, plus the Gemini approvals | The verify script, run by the conductor |

The guard blocks:

- writes outside the files of the agent,
- access to secret paths (`.env`, keys, `secrets/`),
- shell commands outside the allowlist of the agent, and all shell operators (`;`, `|`, `>`, and more),
- the approve command and `--force`,
- writes to `.magenta/policy.json`, `.magenta/checks.lock`, `.magenta/verify-state.json`, `.magenta/active.json`, `acceptance.lock`, `.claude/`, and `.git/`.

The guard and the hooks are guardrails against mistakes. They are not a sandbox. The OpenCode, Codex CLI, and Gemini CLI adapters get bug fixes, but no new features ([ADR-0012](adr/0012-verify-first.md)).

## Configuration of Magenta

| File | Content |
|---|---|
| `magenta.yaml` | The enabled agents, the lanes, the release version |
| `models.yaml` | The model profiles and the runner engines |
| `standards/organization.md` | Optional organization standards for all agents. Copy `standards/organization.example.md`. |

### Models

Each agent names a profile, for example `reasoning-high` or `coding`. `models.yaml` maps each profile to a model for each tool, and to an engine for the headless runner. To use OpenAI, Gemini, Grok, or a self-hosted model, fill in the commented `opencode` and `runner` lines with model IDs that you can use. Then build and install again.
