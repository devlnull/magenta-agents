"""Magenta state protection: a PreToolUse rule for sessions that are not Magenta agents (ADR-0012).

The verify script writes the evidence that the checks pass. Only the human approves checks.
This rule stops the model in the main session from:

  1. writing the state files of the verify script with the file tools,
  2. naming these files in a shell command, or deleting `.magenta/` (rm, git clean -x),
  3. running the commands that only the human runs: approve, --force, and the removal of the hooks.

`approve` and `--force` are decisions of the human. In the main session, `evaluate` answers "ask" for them:
Claude Code shows its permission dialog, and the human confirms or refuses there. Subagents never get the
dialog (`decide` blocks them). When Claude Code cannot ask (bypass mode without the ask rules of
`magenta.py init`), the call is blocked, and the human approves in a terminal.
This rule is a guardrail, not a sandbox.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path, PurePath

STATE_NAMES = ("checks.lock", "verify-state.json", "active.json", "acceptance.lock")
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PATH_KEYS = ("file_path", "notebook_path", "path")
CASE_INSENSITIVE = sys.platform in ("darwin", "win32")
_STATE_IN_SHELL = re.compile(r"\.magenta[/\\][^\s'\";|&<>]*?(" + "|".join(re.escape(n) for n in STATE_NAMES)
                             + r"|agents(?=[/\\\s'\"]|$))", re.IGNORECASE if CASE_INSENSITIVE else 0)
_HUMAN_ONLY = re.compile(r"(verify\.py|magenta\.py)\b.*(?:^|\s)(approve|uninstall-hook|unhook|uninstall|--fo(?:r(?:ce?)?)?)"
                         r"(?:\s|=|$)")
_ASK_WORDS = {"approve"}  # and --force with its abbreviations; the other human-only words are always blocked
# Permission rules that `magenta.py init` adds. Claude Code asks for a matching command in every mode.
ASK_RULES = ("Bash(*verify.py*approve*)", "Bash(*verify.py*--force*)", "Bash(*magenta.py*approve*)",
             "Bash(*magenta.py*--force*)")
_DELETE_STATE = re.compile(r"(\brm\b[^|;&]*\.magenta(?:[/\\\s'\"]|$))|(\bgit\s+clean\b[^|;&]*\s-[A-Za-z]*[xX])")


def unquoted(command: str) -> str:
    """The command with the quotes removed, so that `'approve'` is `approve`. A parse error removes the quote marks."""
    try:
        return " ".join(shlex.split(command))
    except ValueError:
        return command.replace('"', " ").replace("'", " ")


def _is_state_path(raw: str) -> bool:
    path = PurePath(raw.replace("\\", "/"))
    parts = [p.lower() if CASE_INSENSITIVE else p for p in path.parts]
    name = parts[-1] if parts else ""
    names = [n.lower() if CASE_INSENSITIVE else n for n in STATE_NAMES]
    if ".magenta" in parts and parts.index(".magenta") + 1 < len(parts) and parts[parts.index(".magenta") + 1] == "agents":
        return True  # the records of the running subagents (the Stop hook trusts them)
    return ".magenta" in parts and name in names


def _uses_magenta(cwd) -> bool:
    """True if the folder or a parent folder has `.magenta/`. Only then are deletions of it blocked."""
    try:
        here = Path(cwd or ".").resolve()
        return any((p / ".magenta").is_dir() for p in [here, *list(here.parents)[:8]])
    except OSError:
        return False


def _ask_rules_installed(cwd) -> bool:
    """True if the settings of the project or the user have the ask rules of Magenta."""
    try:
        here = Path(cwd or ".").resolve()
    except OSError:
        return False
    folders = [here, *list(here.parents)[:8]]
    files = [f / ".claude" / n for f in folders for n in ("settings.local.json", "settings.json")]
    files.append(Path.home() / ".claude" / "settings.json")
    for path in files:
        try:
            rules = json.loads(path.read_text(encoding="utf-8")).get("permissions", {}).get("ask", [])
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(rules, list) and ASK_RULES[0] in rules:
            return True
    return False


def evaluate(event: dict) -> tuple[str, str]:
    """For the main session: ("allow" | "ask" | "deny", reason). Approve and --force ask the human."""
    tool_input = event.get("tool_input") or {}
    if event.get("tool_name") == "Bash":
        human = _HUMAN_ONLY.search(unquoted(str(tool_input.get("command") or "")))
        if human and (human.group(2) in _ASK_WORDS or human.group(2).startswith("--fo")):
            word = "approve the checks" if human.group(2) == "approve" else f"run `{human.group(2)}`"
            if event.get("permission_mode") == "bypassPermissions" and not _ask_rules_installed(event.get("cwd")):
                return "deny", (f"only the human can {word}, and Claude Code runs without permission prompts, so it "
                                "cannot ask the human. Show the human this command to run in a terminal. To get the "
                                "approval dialog in all modes, the human runs `magenta.py init` for this repository "
                                "one time.")
            return "ask", f"Magenta: only you can {word}. Allow this command only if you agree."
    reason = decide(event)
    return ("deny", reason) if reason else ("allow", "")


def hook_output(kind: str, reason: str) -> tuple[int, str, str]:
    """(exit code, stdout, stderr) for a Claude Code PreToolUse hook."""
    if kind == "ask":
        return 0, json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                                     "permissionDecisionReason": reason}}), ""
    if kind == "deny":
        return 2, "", f"Magenta: {reason}"
    return 0, "", ""


def decide(event: dict) -> str | None:
    """Return a reason to block the tool call, or None. For subagents: they never approve or force."""
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        human = _HUMAN_ONLY.search(unquoted(command))
        if human:
            return (f"only the human runs `{human.group(2)}`. Return the command to the conductor, which asks the "
                    "human to confirm it.")
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
