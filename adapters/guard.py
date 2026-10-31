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
import glob
import itertools
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
# Interpreters that run code from the command line. Such code is outside the write rules and the secret rules.
INTERPRETERS = (
    (re.compile(r"php[\d.]*(-cli)?"), "php"),
    (re.compile(r"(python|pypy)[\d.]*|py"), "python"),
    (re.compile(r"node(js)?|bun"), "node"),
    (re.compile(r"deno"), "deno"),
    (re.compile(r"j?ruby[\d.]*"), "ruby"),
    (re.compile(r"perl[\d.]*"), "perl"),
    (re.compile(r"lua[\d.]*|luajit"), "lua"),
    (re.compile(r"rscript|groovy|osascript"), "e"),
    (re.compile(r"(ba|da|z|k|mk|a|tc|c)?sh|fish"), "shell"),
    (re.compile(r"pwsh|powershell"), "pwsh"),
    (re.compile(r"cmd"), "cmd"),
)
# kind: (short options with inline code, short options that take a value, long options with inline code)
INLINE = {
    "php": ("rRBEFa", "cdztSf", ("--run", "--process-code", "--process-begin", "--process-end", "--process-file",
                                 "--interactive")),
    "python": ("c", "WXQ", ()),
    "node": ("ep", "rC", ("--eval", "--print")),
    "deno": ("", "", ("--eval", "--eval-file")),
    "ruby": ("e", "IrCEFxKT0", ()),
    "perl": ("eE", "IMmxlF0iDCd", ()),
    "lua": ("e", "l", ()),
    "e": ("e", "", ()),
    "shell": ("c", "oO", ("--command",)),
}
# Commands of frameworks that run code from the command line or from a console.
EVAL_COMMANDS = {("artisan", "tinker"), ("manage.py", "shell"), ("manage.py", "shell_plus"), ("rails", "runner"),
                 ("rails", "r"), ("rails", "console"), ("rails", "c"), ("npx", "-c"), ("npx", "--call")}
GLOB_LIMIT = 2000
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


def _hidden_expansion(command: str) -> str | None:
    """Return the shell syntax that bash expands but the guard does not see, or None. The guard checks the words of
    the command, so bash must run the same words: no `$` outside single quotes (variables, `$@`, and encoded
    characters such as `$'\\x3b'`), and no brace expansion such as `{a,b}`."""
    view, quote, i = [], None, 0
    while i < len(command):
        ch = command[i]
        if quote == "'":
            quote = None if ch == "'" else quote
            view.append("x")
        elif ch == "\\":
            view.append("xx")
            i += 1
        elif ch == "$":
            return "$"
        elif quote == '"':
            quote = None if ch == '"' else quote
            view.append("x")
        elif ch in "'\"":
            quote = ch
            view.append("x")
        else:
            view.append(ch)
        i += 1
    found = re.search(r"\{[^{}\s]*(,|\.\.)[^{}\s]*\}", "".join(view))
    return found.group(0) if found else None


def _looks_like_file(word: str) -> bool:
    return "/" in word or "\\" in word or bool(re.search(r"\.[A-Za-z0-9]+$", word))


def _inline_option(kind: str, rest) -> str | None:
    """The option of an interpreter that runs code from the command line, in the words after the interpreter."""
    if kind == "cmd":
        return next((w for w in rest if w.lower() in ("/c", "/k", "/r")), None)
    if kind == "pwsh":
        return next((w for w in rest if w[:1] in "-/" and w.lstrip("-/")[:1].lower() in ("c", "e")), None)
    inline, value, longs = INLINE[kind]
    skip, first = False, True
    for word in rest:
        if kind == "php" and ("auto_prepend_file" in word or "auto_append_file" in word):
            return word  # a setting that runs a file before or after the script
        if skip:
            skip = False
            continue
        if word == "--":
            return None
        if word.startswith("--"):
            if word.split("=", 1)[0] in longs:
                return word
            skip = "=" not in word  # the next word can be its value
            continue
        if len(word) > 1 and (word[0] == "-" or (kind == "shell" and word[0] == "+")):
            letters = word[1:]
            for k, letter in enumerate(letters):
                if letter in inline:
                    return word
                if kind == "python" and letter == "m":
                    return None  # a module: the next words are its arguments
                if letter in value:
                    skip = k == len(letters) - 1  # the next word is the value
                    break
            continue
        if kind == "deno" and first and word == "eval":
            return word
        first = False
        if _looks_like_file(word):
            return None  # the script: the next words are its arguments
    return None


def _inline_code(tokens) -> str | None:
    """Return the interpreter and the option that run code from the command line (for example `php -r`), or None.
    Every word is examined, so an interpreter behind a wrapper (for example `docker compose exec app`) counts too."""
    for i, word in enumerate(tokens):
        name = re.split(r"[\\/]", word)[-1].lower()
        name = name[:-4] if name.endswith(".exe") else name
        if i + 1 < len(tokens) and (name, tokens[i + 1].split("=", 1)[0]) in EVAL_COMMANDS:
            return f"{word} {tokens[i + 1]}"
        if name in ("npm", "pnpm") and tokens[i + 1:i + 2] == ["exec"]:
            call = next((w for w in tokens[i + 2:] if w.split("=", 1)[0] in ("-c", "--call")), None)
            if call:
                return f"{word} exec {call}"
        kind = next((k for pattern, k in INTERPRETERS if pattern.fullmatch(name)), None)
        found = _inline_option(kind, tokens[i + 1:]) if kind else None
        if found:
            return f"{word} {found}"
    return None


def _secret_by_glob(word: str, cwd: Path, denies) -> str | None:
    """Return a secret path that a wildcard word (for example `.e?v`) gives in bash, or None."""
    if not any(c in word for c in "*?["):
        return None
    word = os.path.expanduser(word)
    pattern = word if os.path.isabs(word) else os.path.join(glob.escape(str(cwd)), word)
    try:
        for hit in itertools.islice(glob.iglob(pattern), GLOB_LIMIT):
            path = Path(hit)
            try:
                rel = path.resolve().relative_to(cwd).as_posix()
            except ValueError:
                rel = path.as_posix()
            if _matches(rel, denies) or _matches(path.name, denies):
                return rel
    except (OSError, ValueError, re.error):
        return None
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


def _is_repo(folder: Path) -> bool:
    return (folder / ".git").exists() or (folder / ".magenta").is_dir()


def repo_root(target: Path, cwd: Path) -> Path:
    """The repository of a file in the session folder. The write rules of the agents are relative to it.
    When the session folder is a repository, it is the session folder. When the session started in a parent
    folder (a workspace with many repositories), it is the nearest folder between the file and the session folder
    that has `.git` or `.magenta/`. Without such a folder, it is the session folder."""
    if _is_repo(cwd):
        return cwd
    for folder in target.parents:
        if folder == cwd:
            break
        if _is_repo(folder):
            return folder
    return cwd


def _inside(path: Path, cwd: Path) -> bool:
    try:
        path.relative_to(cwd)
        return True
    except ValueError:
        return False


def _without_git_folder(tokens, cwd: Path):
    """`git -C <folder> <command>` with a folder in the session folder is `git <command>` in that folder (a
    session in a workspace with many repositories). Return the tokens without `-C <folder>`, or None."""
    if len(tokens) < 4 or tokens[0] != "git" or tokens[1] != "-C":
        return None
    folder = Path(tokens[2]).expanduser()
    folder = (folder if folder.is_absolute() else cwd / folder).resolve()
    return ["git", *tokens[3:]] if _inside(folder, cwd) else None


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
            return (f"{me} can run only one simple command, without shell operators: {command!r}. Do not encode or "
                    "hide an operator. If you need more, report it to the conductor.")
        hidden = _hidden_expansion(command)
        if hidden:
            return (f"{me} cannot run {command!r}: bash expands {hidden!r}, so the guard cannot check the words that "
                    "run. Write values as plain words, or in single quotes. Do not encode characters.")
        try:
            local = _without_git_folder(shlex.split(command), cwd)
        except ValueError:
            local = None
        if local is not None:  # the rules apply to the git command itself
            command = shlex.join(local)
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
        inline = _inline_code(tokens)
        if inline:
            return (f"{me} cannot run {command!r}: `{inline}` runs code from the command line, and that code is "
                    "outside the write and secret rules. Put the code in a test or a script in your write folders, "
                    "or report the need to the conductor.")
        for word in tokens:
            secret = _secret_by_glob(word, cwd, denies)
            if secret:
                return f"{me} cannot access the secret path {secret!r} (from the wildcard {word!r})"
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
    inside = _inside(target, cwd)  # the session folder is the limit for writes
    root = repo_root(target, cwd) if inside else cwd
    try:
        rel = target.relative_to(root).as_posix()
    except ValueError:
        rel = target.as_posix()
    if inside and root != cwd:  # the rules of the repository of the file
        extra = _project_policy(root).get(agent, {})
        writes = list(policy.get("writes", [])) + list(extra.get("writes", []))

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
