#!/usr/bin/env python3
"""Magenta guard: a Claude Code PreToolUse hook that enforces the Magenta rules (RFC-0001, 6.6).

  1. File ownership: an agent writes only to its own paths.
  2. Secret paths: an agent does not read or write secret files.
  3. Shell allowlist: an agent runs only allowed, simple commands. Denied commands always lose.

Usage:
  guard.py <agent-id>   per-agent hook in the agent file (user-level install). Fails closed.
  guard.py --auto       one hook for all agents (plugin install). It finds the agent from the
                        `agent_type` input field. Sessions that are not Magenta agents pass.

Write patterns are ordered. The last matching pattern wins. A pattern that starts with "!" denies.
Exit code 2 blocks the tool call. Claude Code shows the stderr message to the agent.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import path_matches  # noqa: E402

PREFIX = "magenta-"
PLUGIN_SCOPE = "magenta:"
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PATH_KEYS = ("file_path", "notebook_path", "path")
HARD_DENY_WRITES = [".magenta/policy.json", "**/acceptance.lock", ".claude/**", ".git/**", ".opencode/**"]
SHELL_OPERATORS = (";", "&", "|", ">", "<", "`", "$(", "\n")
# macOS and Windows file systems ignore case by default: compare paths without case there.
CASE_INSENSITIVE = sys.platform in ("darwin", "win32")


def _norm(value: str) -> str:
    return value.lower() if CASE_INSENSITIVE else value


def _matches(path: str, patterns) -> bool:
    return path_matches(_norm(path), [_norm(p) for p in patterns or []])


def agent_id_from_type(agent_type) -> str | None:
    """'magenta-qa', 'magenta:qa', and 'magenta:magenta-qa' all give 'qa'. Other names give None."""
    if not agent_type:
        return None
    name = str(agent_type)
    if name.startswith(PLUGIN_SCOPE):
        name = name[len(PLUGIN_SCOPE):]
        return name[len(PREFIX):] if name.startswith(PREFIX) else name
    return name[len(PREFIX):] if name.startswith(PREFIX) else None


def ordered_allow(path: str, patterns) -> bool:
    allowed = False
    for pattern in patterns or []:
        if pattern.startswith("!"):
            if _matches(path, [pattern[1:]]):
                allowed = False
        elif _matches(path, [pattern]):
            allowed = True
    return allowed


def _project_policy(cwd: Path) -> dict:
    try:
        data = json.loads((cwd / ".magenta" / "policy.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def decide(agent: str, policy: dict, event: dict):
    """Return a reason to block the tool call, or None to let the normal flow continue."""
    me = PREFIX + agent
    other = agent_id_from_type(event.get("agent_type"))
    if other and other != agent:
        return None  # another Magenta agent: its own policy decides

    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    cwd = Path(event.get("cwd") or os.getcwd()).resolve()
    extra = _project_policy(cwd).get(agent, {})
    writes = list(policy.get("writes", [])) + list(extra.get("writes", []))
    shell = list(policy.get("shell", [])) + list(extra.get("shell", []))
    shell_deny = list(policy.get("shell_deny", [])) + list(extra.get("shell_deny", []))
    denies = list(policy.get("denies", []))

    if tool == "Bash":
        command = " ".join(str(tool_input.get("command") or "").split())
        if any(op in command for op in SHELL_OPERATORS):
            return f"{me} can run only one simple command, without shell operators: {command!r}"
        if any(fnmatch.fnmatchcase(command, p) for p in shell_deny):
            return f"{me} cannot run {command!r}: the command is denied"
        if not any(fnmatch.fnmatchcase(command, p) for p in shell):
            return f"{me} cannot run {command!r}. Allowed commands: {shell or 'none'}"
        for token in re.split(r"[\s:=]+", command):
            token = token[2:] if token.startswith("./") else token
            if token and (_matches(token, denies) or _matches(Path(token).name, denies)):
                return f"{me} cannot access the secret path {token!r}"
        return None

    raw = next((tool_input[k] for k in PATH_KEYS if tool_input.get(k)), None)
    if raw is None:
        return None
    target = Path(str(raw)).expanduser()
    target = (target if target.is_absolute() else cwd / target).resolve()
    try:
        rel, inside = target.relative_to(cwd).as_posix(), True
    except ValueError:
        rel, inside = target.as_posix(), False

    if _matches(rel, denies) or _matches(target.name, denies):
        return f"{me} cannot access the secret path {rel}"
    if tool in WRITE_TOOLS:
        if not inside:
            return f"{me} cannot write outside the project: {rel}"
        if _matches(rel, HARD_DENY_WRITES):
            return f"{me} cannot write {rel}. Only the human changes this file."
        if not ordered_allow(rel, writes):
            owned = ", ".join(writes)
            return f"{me} cannot write {rel}. Its write rules: {owned}. Report the needed change to the owner of the file."
    return None


def _load_policy(agent: str):
    path = Path(__file__).resolve().parent / "policies" / f"{agent}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Magenta guard: usage: guard.py <agent-id> | --auto", file=sys.stderr)
        return 2
    try:
        event = json.load(sys.stdin)
    except ValueError as exc:
        print(f"Magenta guard: blocked, because the input is not readable: {exc}", file=sys.stderr)
        return 2
    if argv[0] == "--auto":
        agent = agent_id_from_type(event.get("agent_type"))
        if agent is None:
            return 0  # not a Magenta agent
    else:
        agent = argv[0]
    try:
        policy = _load_policy(agent)
    except (OSError, ValueError) as exc:
        print(f"Magenta guard: blocked, because the policy of {agent!r} is not readable: {exc}", file=sys.stderr)
        return 2
    reason = decide(agent, policy, event)
    if reason:
        print(f"Magenta guard: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
