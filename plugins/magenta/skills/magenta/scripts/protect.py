"""Magenta state protection: a PreToolUse rule for sessions that are not Magenta agents (ADR-0012).

The verify script writes the evidence that the checks pass. Only the human approves checks.
This rule stops the model in the main session from:

  1. writing the state files of the verify script with the file tools,
  2. naming these files in a shell command, or deleting `.magenta/` (rm, git clean -x),
  3. running the commands that only the human runs: approve, --force, and the removal of the hooks.

The human can still approve checks: in a terminal, or with `!` in Claude Code (a command that
the human types does not go through the hooks). This rule is a guardrail, not a sandbox.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path, PurePath

STATE_NAMES = ("checks.lock", "verify-state.json", "active.json", "acceptance.lock")
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PATH_KEYS = ("file_path", "notebook_path", "path")
CASE_INSENSITIVE = sys.platform in ("darwin", "win32")
_STATE_IN_SHELL = re.compile(r"\.magenta[/\\][^\s'\";|&<>]*?(" + "|".join(re.escape(n) for n in STATE_NAMES) + ")",
                             re.IGNORECASE if CASE_INSENSITIVE else 0)
_HUMAN_ONLY = re.compile(r"(verify\.py|magenta\.py)\b.*(?:^|\s)(approve|uninstall-hook|unhook|--force)(?:\s|=|$)")
_DELETE_STATE = re.compile(r"(\brm\b[^|;&]*\.magenta(?:[/\\\s'\"]|$))|(\bgit\s+clean\b[^|;&]*\s-[A-Za-z]*[xX])")


def _is_state_path(raw: str) -> bool:
    path = PurePath(raw.replace("\\", "/"))
    parts = [p.lower() if CASE_INSENSITIVE else p for p in path.parts]
    name = parts[-1] if parts else ""
    names = [n.lower() if CASE_INSENSITIVE else n for n in STATE_NAMES]
    return ".magenta" in parts and name in names


def _uses_magenta(cwd) -> bool:
    """True if the folder or a parent folder has `.magenta/`. Only then are deletions of it blocked."""
    try:
        here = Path(cwd or ".").resolve()
        return any((p / ".magenta").is_dir() for p in [here, *list(here.parents)[:8]])
    except OSError:
        return False


def decide(event: dict) -> str | None:
    """Return a reason to block the tool call, or None."""
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        human = _HUMAN_ONLY.search(command)
        if human:
            return (f"only the human runs `{human.group(2)}`. Show the human the command and ask the human to run it "
                    "(in a terminal, or with `!` in Claude Code).")
        if _DELETE_STATE.search(command) and _uses_magenta(event.get("cwd")):
            return ("do not delete `.magenta/` or run `git clean -x`. It holds the checks, the approvals, and the "
                    "work items. Ask the human.")
        state = _STATE_IN_SHELL.search(command)
        if state:
            return (f"do not name {state.group(1)} in a shell command. The verify script owns this file. "
                    "To see the state, run the verify script with `status`.")
        return None
    if tool in WRITE_TOOLS:
        raw = next((tool_input[k] for k in PATH_KEYS if tool_input.get(k)), None)
        if raw and _is_state_path(str(raw)):
            return f"do not write {raw}. Only the verify script writes this file. Only the human approves checks."
    return None
