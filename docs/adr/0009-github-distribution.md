# ADR-0009: Distribution from GitHub for macOS, Linux, and Windows

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | Request to publish the project on GitHub and to install it on different operating systems |

## Context

The project lives in the public GitHub repository `devlnull/magenta-agents`. Users work on macOS, Linux, and Windows. Claude Code runs hook commands in a shell (Git Bash on Windows). `python3` and `$HOME` are not reliable on Windows.

## Decision

1. Two install paths from GitHub:
   - The Claude Code plugin: `claude plugin marketplace add devlnull/magenta-agents`. The generated plugin is in git, in the repository root.
   - Installer scripts: `install.sh` (macOS, Linux, Git Bash) and `install.ps1` (Windows). They clone a branch or a tag, build, and install for Claude Code, OpenCode, or Codex CLI.
2. The user-level install writes the guard command with the absolute path of the Python that ran the install, with forward slashes and quotes. No `$HOME`, no `python3` name.
3. The plugin hook runs `sh guard.sh --auto`. The launcher tries `python3`, `python`, and `py`. Without Python, it lets other sessions continue and blocks Magenta agents.
4. The guard compares paths without case on macOS and Windows, so a different case cannot go around a write rule.
5. `python3 magenta.py check` fails when the committed plugin is not current. CI runs the tests, the check, and both installers on macOS, Linux, and Windows, with Python 3.9 and 3.13.
6. `.gitattributes` keeps LF line endings, except CRLF for `install.ps1`.
7. Versions are git tags (`v0.5.0`). The plugin version comes from `release` in `magenta.yaml`.

## Consequences

- Good: one command to install on each OS. CI proves the build and the guard on all three systems.
- Bad: generated plugin files are in git. A change to the source needs a build before the commit (CI finds a missing build).
- Follow-up: select a license for the public repository.
