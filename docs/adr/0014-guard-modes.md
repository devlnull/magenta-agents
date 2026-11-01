# ADR-0014: Guard modes: free code, protected process

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-11-01 |
| Decider | AMQ |
| Source | Request: "the guard is a pain, since the work is mostly on code, so uncommitted changes need no approve, we might need to fix that or loose the restrictions on most changes for guard" |

## Context

The guard enforced file ownership (each agent writes only its own paths) and a shell allowlist for each agent. In real tasks this blocked normal work: a reviewer could not fix a small thing, and each project command (for example tests in a container) needed a pattern in `.magenta/policy.json`.

Since ADR-0012, the integrity of a task does not come from the guard. It comes from verify: the human approves each check, a changed check fails, the locked tests have a sealed hash, and the Stop hook does not let the agent finish until the checks pass. The code changes are not committed and not pushed: git shows them, and the human reviews them.

## Decision

The guard has two modes. `standard` is the default.

- **standard:** all agents write the code and the other files of the repository. The guard keeps the protection of the process and of the computer: the files in `.magenta/` keep their owners, makers cannot write locked tests, the human-only files (`policy.json`, approvals, verify state, `.claude/`, `.git/`) stay blocked at any depth, secrets stay blocked, and the paths that a role denies with `!` stay blocked. The shell runs any simple command except dangerous commands (push, merge, rebase, reset `--hard`, stash, restore, `rm`, deploy, publish, `gh`, `ssh`, `sudo`, global installs). A human pattern in `.magenta/policy.json` can allow one of them again.
- **strict:** the former rules: file ownership and a shell allowlist, plus the protections of standard mode.

In both modes: one simple command (no operators, no hidden expansion, no inline code) and no container options that reach the computer outside the project.

Select strict mode with `{"guard": "strict"}` in `.magenta/policy.json`, or `MAGENTA_GUARD=strict`. An unknown value means strict.

## Consequences

- Fewer blocks during normal work. The agents still never push, merge, or deploy.
- A reviewer can change code. The prompts of the roles still say what each role does, and the review and the checks find a wrong change.
- The OpenCode, Codex CLI, and Gemini CLI adapters keep their rules as before (ADR-0012: bug fixes only).
