# Changelog

All notable changes are in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/). Before 1.0, a minor version can change commands and file formats.

## [Unreleased]

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

[Unreleased]: https://github.com/devlnull/magenta-agents/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/devlnull/magenta-agents/compare/v0.7.1...v0.8.0
[0.7.1]: https://github.com/devlnull/magenta-agents/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/devlnull/magenta-agents/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/devlnull/magenta-agents/compare/832c22a...v0.6.0
[0.5.0]: https://github.com/devlnull/magenta-agents/commit/832c22a
