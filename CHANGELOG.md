# Changelog

All notable changes are in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/). Before 1.0, a minor version can change commands and file formats.

## [Unreleased]

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

[Unreleased]: https://github.com/devlnull/magenta-agents/compare/v0.7.1...HEAD
[0.7.1]: https://github.com/devlnull/magenta-agents/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/devlnull/magenta-agents/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/devlnull/magenta-agents/compare/832c22a...v0.6.0
[0.5.0]: https://github.com/devlnull/magenta-agents/commit/832c22a
