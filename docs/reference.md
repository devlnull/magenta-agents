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
| `init <repo> [--no-hook]` | Make `.magenta/`, keep it out of git, add the ask rules for the approval dialog, and add the Claude Code hooks (not with `--no-hook`). |
| `unhook <repo>` | Remove the Claude Code hooks of Magenta. |
| `verify list --repo <repo>` | Show the checks, the test locks, and their approval. |
| `verify approve [ID ...] --repo <repo>` | Approve new and changed checks, and seal the test locks. Only the human decides: in Claude Code, through the permission dialog; otherwise in a terminal. |
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
  "guard":       "standard",
  "fingerprint": { "include": ["tests/Unit/**"] },
  "mounts":      ["/path/to/the/application"],
  "qa":          { "writes": ["src/acceptanceTest/**"], "shell": ["./gradlew acceptanceTest*"] },
  "engineer":    { "writes": ["!src/acceptanceTest/**"] }
}
```

| Key | Meaning |
|---|---|
| `guard` | `standard` (default) or `strict`. See [Guard modes](#guard-modes). The environment variable `MAGENTA_GUARD` wins over it. |
| `fingerprint.include` | Files that git ignores, but the checks use, for example local-only tests. A change of these files makes the old results invalid. The locked tests are always in the fingerprint. |
| `mounts` | Host folders that a container command of an agent can mount (`docker run -v`), in addition to the session folder and the git repository that holds it. |
| `<agent>.writes`, `<agent>.shell`, `<agent>.shell_deny` | More rules for one agent. A `shell` pattern here can also allow a command that the guard blocks as dangerous, for example `gh pr view*`. |

Write a shell pattern as narrow as possible, for example `docker compose exec -T app php artisan test*`, not `docker compose exec *`. A `*` matches any text, also other words and options. The guard blocks inline code (`php -r`, `sh -c`) in all commands, but a broad pattern still lets an agent run any program in the container.

## Enforcement

| Tool | Rules of the agents | Checks |
|---|---|---|
| Claude Code (user level) | A guard hook in each agent | The verify script, and the Stop and protect hooks from `init` |
| Claude Code (plugin) | One plugin guard hook for all sessions | The verify script, and the Stop, SubagentStart, and SubagentStop hooks of the plugin |
| OpenCode | Ordered permission rules in each agent | The verify script, run by the conductor |
| Codex CLI | Rules as instructions, plus the Codex sandbox and approvals | The verify script, run by the conductor |
| Gemini CLI | Rules as instructions, plus the Gemini approvals | The verify script, run by the conductor |

### Auto mode

`verify.py start <ID> --session=<id> --auto` records that the human started the task with `--auto` (the conductor does it for `/magenta --auto`). While the task is active, the PreToolUse hooks answer `allow` for each tool call of that session (the conductor, the Magenta agents, and other subagents) that passes the rules: files in the session folder, no human-only file, no secret, and no dangerous command. Then Claude Code does not ask. `approve` and `--force` still ask the human. A blocked call stays blocked. Other calls get the normal prompt. `finish` ends auto mode.

### Hook output

The hooks answer with JSON decisions, not with "hook errors": a blocked tool call gets `permissionDecision: deny` with the reason for the model; the Stop and SubagentStop hooks block with `decision: block`, and the reason goes only to Claude. The human sees a note only when the human must act (checks that wait for approval), one time for each state.

### Guard modes

| | `standard` (default) | `strict` |
|---|---|---|
| Code and other files of the repository | All agents write them. Git, the approved checks, the locks, and the review find mistakes. Only the paths that the rules of a role deny with `!` stay blocked (for example CI files and Dockerfiles for the Engineer, ADRs for all roles except the Architect). | Each agent writes only its own paths. |
| `.magenta/` (checks, work items, profile) | Only the owner of each file | Only the owner of each file |
| Locked tests of a task | Makers cannot write them. QA and the Architect can, and the lock check then fails until the human approves the new seal. | Only the owners |
| Shell | Any simple command, except dangerous commands: push, pull, merge, rebase, reset `--hard`, stash, restore, clean, delete files (`rm`), `kubectl`, deploy and publish commands, `gh`, `ssh`, `sudo`, and global package installs. An agent without a shell list has no shell. | Only the allowlist of the agent |

Select strict mode for a repository with `{"guard": "strict"}` in `.magenta/policy.json`, or for all repositories with the environment variable `MAGENTA_GUARD=strict`. An unknown value means strict.

In both modes, the guard blocks:

- access to secret paths (`.env`, keys, `secrets/`, `.ssh/`, `id_rsa`, `*.p12`, `.netrc`, and more),
- all shell operators (`;`, `|`, `>`, and more),
- shell syntax that bash expands and the guard does not see: `$` outside single quotes (variables, `$@`, encoded characters such as `$'\x3b'`), brace expansion such as `{a,b}`, and wildcards that give a secret path (`.e?v`),
- inline code for an interpreter, also behind a wrapper such as `docker compose exec`: `php -r`, `python -c`, `node -e`, `sh -c`, `bash -lc`, `perl -e`, `ruby -e`, `deno eval`, `pwsh -Command`, `cmd /c`,
- container options that reach the computer: a mount of a folder outside the project (see `mounts`), the Docker socket, `--privileged`, `--pid host`, `--cap-add`, and `--device`,
- shell commands that name a human-only file, for example `.magenta/policy.json`,
- for subagents: the approve command and `--force` (in the main session, Claude Code asks you instead),
- writes to `.magenta/policy.json`, `.magenta/checks.lock`, `.magenta/verify-state.json`, `.magenta/active.json`, `acceptance.lock`, `.claude/`, and `.git/`, also in a repository in a subfolder of the session folder.

The rules of a file apply to its path in its repository: the nearest folder with `.magenta/` between the file and the session folder. So a session can start in an application that holds the repository, for example in `vendor/`.

The guard and the hooks are guardrails against mistakes. They are not a sandbox. The OpenCode, Codex CLI, and Gemini CLI adapters get bug fixes, but no new features ([ADR-0012](adr/0012-verify-first.md)).

## Configuration of Magenta

| File | Content |
|---|---|
| `magenta.yaml` | The enabled agents, the lanes, the release version |
| `models.yaml` | The model profiles and the runner engines |
| `standards/organization.md` | Optional organization standards for all agents. Copy `standards/organization.example.md`. |

### Models

Each agent names a profile, for example `reasoning-high` or `coding`. `models.yaml` maps each profile to a model for each tool, and to an engine for the headless runner. To use OpenAI, Gemini, Grok, or a self-hosted model, fill in the commented `opencode` and `runner` lines with model IDs that you can use. Then build and install again.
