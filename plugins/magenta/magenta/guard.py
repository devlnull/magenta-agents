#!/usr/bin/env python3
"""Magenta guard: a Claude Code PreToolUse hook that enforces the Magenta rules (RFC-0001, 6.6).

  1. File ownership: an agent writes only to its own paths.
  2. Secret paths: an agent does not read or write secret files.
  3. Shell allowlist: an agent runs only allowed, simple commands. Denied commands always lose.

Usage:
  guard.py <agent-id>   per-agent hook in the agent file (user-level install). Fails closed.
  guard.py --auto       one hook for all agents (plugin install). It finds the agent from the
                        `agent_type` input field. For sessions that are not Magenta agents, it
                        only protects the verify state (protect.py).

Write patterns are ordered. The last matching pattern wins. A pattern that starts with "!" denies.
Exit code 2 blocks the tool call. Claude Code shows the stderr message to the agent.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import path_matches  # noqa: E402
import protect  # noqa: E402

PREFIX = "magenta-"
PLUGIN_SCOPE = "magenta:"
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PATH_KEYS = ("file_path", "notebook_path", "path")
HARD_DENY_WRITES = [".magenta/policy.json", "**/acceptance.lock", ".magenta/checks.lock", ".magenta/verify-state.json",
                    ".magenta/active.json", ".magenta/agents/**", ".claude/**", ".git/**", ".opencode/**"]
PYTHON = re.compile(r"(python3?(\.\d+)?|py)(\.exe)?")
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


def _long_option(token: str, option: str, shortest: int = 4) -> bool:
    """True if the token is the long option, or an abbreviation of it that git accepts, with or without `=value`."""
    name = token.split("=", 1)[0]
    return token.startswith("--") and len(name) >= shortest and option.startswith(name)


def _unsafe_git_option(tokens) -> str | None:
    """Return the git option that writes a file or starts a program, or None. The git read commands stay allowed."""
    if len(tokens) < 2 or tokens[0] != "git":
        return None
    sub, options = tokens[1], tokens[2:]
    if sub == "difftool":
        return sub
    for token in options:
        short = token.startswith("-") and not token.startswith("--")
        if _long_option(token, "--output-directory"):
            return token
        if sub == "format-patch" and short and "o" in token:
            return token
        if sub == "grep" and (_long_option(token, "--open-files-in-pager") or (short and "O" in token)):
            return token
    return None


def _is_verify_command(tokens, cwd: Path) -> bool:
    """True for `<python> <path>/verify.py <command> ...` when the script is outside the project folder."""
    if len(tokens) < 3 or not PYTHON.fullmatch(re.split(r"[\\/]", tokens[0])[-1].lower()):
        return False
    script = tokens[1]
    if re.split(r"[\\/]", script)[-1].lower() != "verify.py":
        return False
    if PureWindowsPath(script).drive and os.name != "nt":
        return True
    target = Path(script).expanduser()
    target = _norm((target if target.is_absolute() else cwd / target).resolve().as_posix())
    root = _norm(cwd.as_posix()).rstrip("/")
    return not (target == root or target.startswith(root + "/"))


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
    state = protect.decide(event)
    if state:
        return f"{me}: {state}"

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
        allowing = [p for p in shell if fnmatch.fnmatchcase(command, p)]
        if not allowing:
            return f"{me} cannot run {command!r}. Allowed commands: {shell or 'none'}"
        try:
            tokens = shlex.split(command)
        except ValueError:
            return f"{me} cannot run {command!r}: the quotes are not valid"
        if all("verify.py" in p for p in allowing) and not _is_verify_command(tokens, cwd):
            return (f"{me} cannot run {command!r}. The verify script runs as: <python> <path>/verify.py <command>, "
                    "and the script is outside the project.")
        unsafe = _unsafe_git_option(tokens)
        if unsafe:
            return f"{me} cannot run {command!r}: the git option {unsafe!r} writes a file or runs a program"
        for word in tokens:
            for token in re.split(r"[\s:=]+", word):
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
        if agent is None:  # not a Magenta agent: only the verify state is protected
            event = event if isinstance(event, dict) else {}
            kind, reason = protect.evaluate(event)
            if kind == "ask":
                try:  # the plugin has verify.py next to this file: show what the human approves
                    import verify
                    reason += verify.approval_details(event)
                except Exception:
                    pass
            code, out, err = protect.hook_output(kind, reason)
            if out:
                print(out)
            if err:
                print(err, file=sys.stderr)
            return code
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
