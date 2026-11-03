# Changelog

All notable changes are in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/). Before 1.0, a minor version can change commands and file formats.

## [Unreleased]

### Added

- **A benchmark at each release.** `evals/benchmark/release.py` runs the benchmark (a plain prompt against `/magenta`, 18 tasks with hidden tests, 4 Claude models, 3 runs), writes `evals/benchmark/results/v<version>.json`, makes the images in `docs/assets/benchmark/`, and updates the benchmark block of the README. The release workflow stops when the results of the tag are missing or not published (`release.py check`).
- The results of 0.14.0, 0.15.0, and 0.16.0 in `evals/benchmark/results/`, and a chart that compares the versions.
- A new README with a banner, the benchmark results, and a table that tells when to use Magenta and when a plain prompt is enough.

### Changed

- The older benchmark notes and scripts are in `evals/benchmark/archive/`.

## [0.16.0] - 2026-11-03

### Added

- **The script decides if direct mode is allowed.** `verify context` now ends with a "Direct mode" section. It says "Not allowed" (with the reasons) when a rule file names the changed file or module, when the code is about money, security, personal data, or a migration, when the code writes a stored format, or when two or more other files use a changed function. The conductor follows this verdict.
- Conductor rule 2: follow the rules of the repository exactly (names, exception types, formats, defaults). Write a better idea in the report, and let the human decide.
- Benchmark: 4 held-out tasks (h7 to h10) that were not used to tune Magenta, and 3 runs for each task.

### Changed

- `models.yaml`: `reasoning-high` and `reviewer-alt` use `sonnet` on Claude Code (before: `opus`). In the benchmark, Sonnet 5.5 with Magenta passed all hidden tests at a lower cost. Put `opus` back for very hard design or review work.

### Fixed

- `verify context` kept only the first line of a rule. The next lines of the same rule (for example "...for other names raise `ValueError`") are now in the output.

## [0.15.0] - 2026-11-03

### Added

- **Direct mode.** For a small, clear, low-risk task (the lite lane), the conductor does the work itself: it reads the rules near the change, writes the test first for a bug, changes the code, and runs the project checks. No other agents. A task with money, security, a stored format, a public API, or callers with another meaning is never direct.
- `verify context <files>`: a script that finds the rule files of the repository (RULES, SPEC, SECURITY, ARCHITECTURE, CONTRIBUTING, ADRs, the project profile, the lessons) and, for each function in the files, the other files that use it. It costs no model tokens. The conductor uses it before it selects the mode.
- `verify begin`, `gate`, and `close`: the bookkeeping of a task in three calls (start and baseline; lock and the checks that wait; the final run and the close).
- `verify run --table`. A test budget for each lane.

### Changed

- The conductor skill is 15 KB (34 KB before): it no longer carries the constitution of the agents, and team mode and the collaboration patterns are in the skill `magenta-workflow`. The agents get a short roster.
- When all checks pass, `verify run` prints one line.
- Benchmark (`evals/benchmark/`, 14 tasks, 4 models, one run each), 0.15 against 0.14: hidden tests 95.3% → 96.3%, tasks with all hidden tests passed 48 → 50 of 56, tokens −68%, cost −64%, time −67%. A plain prompt: 93.4%.

## [0.14.0] - 2026-11-03

### Changed

- **QA only when the task needs it.** QA joins for tests, features and behavior changes that users or other systems see, money, security, personal data, data migrations, performance targets, and changed code without tests. For other tasks (a log line, a patch upgrade, a refactor with good tests, alerts, docs), the lead writes the tests of its change before the change; they are locked, and you approve them with the checks. In the evaluation (30 scenarios, 3 runs each), QA took part 24% less, never where it was not wanted, was never missing where it was needed, and the plans won 51 to 26 against 0.13.0 (13 ties). See `evals/driver/results.md`.

## [0.13.0] - 2026-11-03

### Added

- **A driver for each task (ADR-0016).** The conductor stays the orchestrator and keeps the process. The driver owns the domain decisions: QA for tests, the Architect for a design, the SRE for an incident or reliability, Security for a vulnerability, Database for data changes, Platform for infrastructure, the Writer for docs, and the Principal for the other tasks and for tasks with more than one main domain. A different role checks the work of the driver. The conductor selects the driver from your request; `--driver <role>` or `--driver none` selects it by hand.
- The rule `driver` for all agents, and the driver fields in the brief and plan templates.
- `evals/driver/`: 26 scenarios, the runner, and the results of the comparison with 0.12.0.

### Changed

- Signal precedence in the routing: a CVE is a security task (also in an upgrade), a slow query whose fix is an index or a schema change is a data task, a CI/CD change is an infrastructure task. A task that only writes a design, an RFC, or an ADR uses the standard lane.
- Domain questions of the agents go to the driver first, and to you only when the driver cannot decide or for a one-way-door decision.

## [0.12.0] - 2026-11-02

### Added

- **Auto mode (ADR-0015).** `/magenta --auto <task>` lets the agents work to the end without a permission prompt for each tool call. Magenta allows each call of the task that passes its rules. You decide only at the checks gate (one approval), at a blocker, and at the done gate. `approve` and `--force` always ask. `verify.py start --auto` records it; `finish` ends it.
- **Result block.** Each agent ends with one Result block (status, summary, changes, evidence, findings, the question for the human). The conductor reads only this block.

### Changed

- The conductor talks to you only for questions, the checks to approve, and the final report. It does not report internal steps (locks, verify runs, hooks, the guard).
- The hooks answer with JSON decisions. A blocked tool call is a `deny` with the reason for the model, not a "PreToolUse hook error". A SubagentStop block is a `decision: block`, not a "hook error". The Stop hook does not show "Claude continues the task" and does not repeat that the checks still fail. You see a note only when you must act (checks wait for your approval), one time for each state.
- `start` and `lock` print one line. `status` shows "(auto)".

## [0.11.0] - 2026-11-01

### Changed

- **Guard modes (ADR-0014).** The default mode `standard` lets all agents change the code. Git, the approved checks, the locks, and the review find mistakes. The guard still protects the files in `.magenta/` (each one keeps its owner), the locked tests (makers cannot write them), the human-only files, the secrets, and the paths that a role denies with `!`. The shell runs any simple command except dangerous commands (push, merge, rebase, reset `--hard`, stash, restore, `rm`, deploy, publish, `gh`, `ssh`, `sudo`, global installs). The former rules (file ownership and a shell allowlist) are the mode `strict`: `{"guard": "strict"}` in `.magenta/policy.json`, or `MAGENTA_GUARD=strict`.
- The conductor writes the result of each review lens in `06-review-<role>.md` of the work item, and each decision of the human in `decisions/`. It asks the human to confirm the project profile.
- The run folders in `.magenta/runs/verify/` have UTC names (like the state files). Verify keeps the last 30 runs.

### Added

- `fingerprint.include` in `.magenta/policy.json`: files that git ignores, but the checks use (for example local-only tests).
- `mounts` in `.magenta/policy.json`: host folders that a container command of an agent can mount.
- Checks get the environment variable `MAGENTA_REPO` (the repository folder), so a check does not need the absolute path of one computer.
- `list`, `approve`, and the approval dialog show a note for a check that is a pipeline without `pipefail`: only the last command can fail it.

### Fixed

- A session in an application that is a git repository, with the Magenta repository in a subfolder (for example a package in `vendor/`): the guard used the rules of the application. The Engineer could write the `policy.json`, the checks, and the Claude Code settings of the package, and the Principal and QA could not write their own files. Now the rules of the nearest folder with `.magenta/` apply, and the human-only files are protected at any depth.
- The fingerprint did not see a change of a locked test in a folder that git ignores, so an old PASS counted for the changed test. Now the current content of the locked tests is in the fingerprint.
- Verify commands in an application folder did not find a Magenta repository in `vendor/`. Now they use the session records of `start` first, and the search includes `vendor/`.

### Security

- The guard blocks container options that reach the computer: a mount of a folder outside the project (except the git repository that holds the session folder and the `mounts` of the policy), the Docker socket, `--privileged`, `--pid host`, `--cap-add`, and `--device`.
- More secret paths for all agents: `.ssh/`, `id_rsa`, `id_ed25519`, `*.p12`, `*.pfx`, `*.jks`, `*.keystore`, `.netrc`, `.git-credentials`, `.aws/credentials`, `.docker/config.json`.
- A shell command of an agent cannot name a human-only file, for example `sed -i … .magenta/policy.json`.

## [0.10.3] - 2026-10-31

### Security

- The guard blocks inline code for interpreters in the commands of the agents: `php -r`, `python -c`, `node -e`, `sh -c`, `bash -lc`, `perl -e`, `ruby -e`, `deno eval`, `pwsh -Command`, `cmd /c`, and more. It also finds them behind a wrapper such as `docker compose exec app`. Before, a QA lens used `docker compose exec ... php -r` (allowed by a broad pattern in `.magenta/policy.json`) with an encoded `;` to read a file.
- The guard blocks shell syntax that bash expands but the guard does not see: `$` outside single quotes (variables, `$@`, and encoded characters such as `$'\x3b'`) and brace expansion such as `{a,b}`. Before, `git diff --ou$@tput=<file>` could write a file.
- The guard blocks a wildcard word that gives a secret path in bash, for example `.e?v`.
- When the guard blocks a shell operator, it tells the agent not to encode or hide it, and to report the need to the conductor.

## [0.10.2] - 2026-10-31

### Fixed

- A session that starts in a parent folder of the repository (a workspace with many repositories) works. Before, the guard compared the path of a file from the session folder (for example `group/app/.magenta/checks/project.yaml`) with the write rules of the agent (`.magenta/checks/project.yaml`), and blocked an agent that owns the file. Now the rules apply to the path in the repository of the file, and the `.magenta/policy.json` of that repository applies.
- The Stop and subagent hooks find the repository of the active task of the session when the session folder is not that repository. `start` records the repository of the session, and `finish` removes the record.
- Verify commands without `--repo` in a workspace folder use the one repository below it with an active task. When there is more than one, the command tells you to add `--repo`.
- The permission dialog of `approve` reads `--repo`, and does not show the path as a check id.

### Added

- Agents can run their allowed git commands as `git -C <folder> <command>`, when the folder is in the session folder.

## [0.10.1] - 2026-10-31

### Changed

- The Stop hook sends Claude back one time for each state of the code and of the results, not two times in each turn. While nothing changes (for example, Claude waits for your answer), it does not repeat the same message. A new change of the code gives a new reminder.

## [0.10.0] - 2026-10-30

### Added

- Commands in Claude Code: `/magenta:run-checks` runs the checks now, `/magenta:task-status` shows the task and the checks, and `/magenta:approve-checks` approves the waiting checks through the permission dialog (only the human can start it). User-level installs: `/magenta-run-checks`, `/magenta-task-status`, `/magenta-approve-checks`.
- SubagentStart and SubagentStop hooks (plugin, and `magenta.py init`). Magenta knows which subagents of the task still work.
- A maker (Engineer, Front-End, Platform, Writer) that changed the code cannot return to the conductor until the checks of the task pass (two blocks at most).

### Changed

- The Stop hook does not block while a subagent of the task still works, for example the lead in the background. It checks again when the subagent returns.
- The Stop hook blocks with a structured decision: the reason goes to Claude, and the human sees a short note, not a "Stop hook error" with a command line.

## [0.9.0] - 2026-10-30

### Changed

- **Approve checks in the permission dialog of Claude Code.** At the checks gate, the conductor shows the checks and requests `approve` with their ids. Claude Code asks you to confirm, and the dialog lists each check and its command. You do not type a command. The same dialog confirms `--force` (close or replace a failing task). Subagents still cannot request an approval.
- `magenta.py init` adds ask rules to `.claude/settings.local.json` (also with `--no-hook`), so that Claude Code asks in every permission mode. Without the rules, in bypass mode, Magenta blocks the approval and shows the command to run in a terminal. `unhook` and `uninstall` remove the rules.

### Fixed

- The guard and the protect hook close shell bypasses: git options that write a file or run a program, a verify path that is not a real `verify.py` outside the project, quoted secret paths, and quoted or abbreviated human-only words. `verify.py` rejects abbreviated options.
- `verify.py start` keeps a failing task that changed the code with its session. Only the human can replace it, with `--force`.
- The code fingerprint counts files marked assume-unchanged or skip-worktree, and source files in nested `bin/`, `out/`, `build/`, and similar folders. A checks file that is not UTF-8 makes the Stop hook block. The Stop hook names the failed checks while a check waits for approval.
- The YAML parser keeps the indentation and the final newline of block scalars, keeps the empty lines of folded blocks, drops a comment after an apostrophe, and accepts CRLF front matter. CI runs the PyYAML cross-check.
- `validate` rejects overlapping write paths of two agents and finds more unknown skill names. Each path has one owner: nested deployment files belong to the Platform Engineer, `runbooks/` to the SRE, and `docs/architecture/` to the Architect.
- QA and the SRE can run the test and lint commands that their steps need. The engineer can run `python3 -m unittest`.
- The runner refuses an existing work item id for `prd-review`, reads the cost from stdout only, checks the budget before each step, and `--fail-on-blocker` matches BLOCKER findings, not count rows.
- The CI templates clone into a writable folder, pin the Magenta release (`MAGENTA_REF`) and the Claude Code version (`CLAUDE_CODE_VERSION`), and pass values through `env`. Only the publish job of the release workflow can write.
- `install` removes the Magenta agents and skills that a new release no longer has. An apostrophe in the home path gives valid YAML. The installers update from `--repo` or `MAGENTA_REPO`, `install.sh --help` works through `curl | sh`, and `install.ps1` finds Python on Windows PowerShell 5.1. `metrics` skips bad lines, and `lock` rejects a file outside the repository with a clear error.
- The workflows, templates, and docs agree with the 0.8.0 team: the PRD steps of the standard lane apply to features only, and the full lane names the correct readiness step.

## [0.8.0] - 2026-10-30

### Added

- Five new roles ([ADR-0013](docs/adr/0013-extended-team.md)): Site Reliability Engineer (`sre`), Platform Engineer (`platform`), Security Engineer (`security`), Database Engineer (`database`), and Technical Writer (`writer`).
- Skills: `slo-observability`, `resilience-review`, `ci-cd-pipeline`, `containers-kubernetes`, `infrastructure-as-code`, `secure-code-review`, `dependency-security`, `zero-downtime-migration`, `query-optimization`, `technical-writing`.
- Templates: `reliability`, `security`, `data`, `runbook`, `postmortem`.
- Task types `infrastructure`, `reliability`, `data`, and `docs`, with playbooks. SRE, Security, and Database lenses.
- [docs/team.md](docs/team.md): the roles, when each one joins, and the files that each one owns.

### Changed

- The SRE leads incidents. The Security Engineer leads security tasks.
- The Engineer and the Front-End Engineer can no longer change CI pipelines, container and deployment files, infrastructure code, alert rules, scanner configuration, runbooks, or postmortems.

## [0.7.1] - 2026-10-30

The first published release.

### Added

- `release` workflow (CD): a version tag runs the full CI, builds the assets, and publishes a GitHub release.
- `magenta.py package`: the source bundle with the built files, the plugin bundle, and `SHA256SUMS`.
- MIT license, contribution guide, security policy, code of conduct, issue and pull request templates.
- Documentation: user guide, reference, architecture, and release guide.

### Changed

- The README is shorter. The details moved to `docs/`.
- The Claude Code plugin has author, license, homepage, and keywords.

### Fixed

- CI: the installer check on Linux and macOS looked for the wrong text.

## [0.7.0] - 2026-10-30

### Added

- Verify first ([ADR-0012](docs/adr/0012-verify-first.md)): checks in `.magenta/checks/*.yaml` as the definition of done, human approval of checks, the verify script, test locks sealed by the approval.
- Claude Code Stop hook and protect hook (plugin, and `magenta.py init` for user-level installs).
- QA, Architect, and Principal own their checks files and have a review lens.
- Three-mode evals (plain, default, team) and `magenta.py eval-summary`.

### Changed

- The default mode of `/magenta` is one lead agent, checks, and one to three reviewers. Team mode runs on a trigger or with `--team`.
- The OpenCode, Codex CLI, and Gemini CLI adapters get bug fixes only.

## [0.6.0] - 2026-10-30

### Added

- The `/magenta` conductor for all daily tasks: task types, playbooks, dynamic teams, and the constraint ledger.
- Entry points for OpenCode, Codex CLI (`$magenta`), and Gemini CLI.
- Skills for performance investigation, root-cause analysis, safe refactoring, and incident response.

## [0.5.0] - 2026-10-30

### Added

- Six role-based agents, the constitution, templates, workflows with human gates, and the guard hook.
- Claude Code adapter, plugin, and marketplace; OpenCode and AGENTS.md adapters.
- Headless runner for PRD reviews and pull request reviews, with CI templates.
- Installers for macOS, Linux, and Windows.

[Unreleased]: https://github.com/devlnull/magenta-agents/compare/v0.15.0...HEAD
[0.15.0]: https://github.com/devlnull/magenta-agents/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/devlnull/magenta-agents/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/devlnull/magenta-agents/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/devlnull/magenta-agents/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/devlnull/magenta-agents/compare/v0.10.3...v0.11.0
[0.10.3]: https://github.com/devlnull/magenta-agents/compare/v0.10.2...v0.10.3
[0.10.2]: https://github.com/devlnull/magenta-agents/compare/v0.10.1...v0.10.2
[0.10.1]: https://github.com/devlnull/magenta-agents/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/devlnull/magenta-agents/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/devlnull/magenta-agents/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/devlnull/magenta-agents/compare/v0.7.1...v0.8.0
[0.7.1]: https://github.com/devlnull/magenta-agents/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/devlnull/magenta-agents/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/devlnull/magenta-agents/compare/832c22a...v0.6.0
[0.5.0]: https://github.com/devlnull/magenta-agents/commit/832c22a
