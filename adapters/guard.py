#!/usr/bin/env python3
"""Magenta guard: a Claude Code PreToolUse hook that enforces the Magenta rules (RFC-0001, 6.6).

Two modes (`.magenta/policy.json`: `{"guard": "strict"}`, or the environment variable MAGENTA_GUARD):

  standard (default)  The code is free: git, the approved checks, the locks, and the review find mistakes.
                      The guard protects the process (`.magenta/`, the approvals, the locked tests for makers),
                      the files of the human (`.claude/`, `.git/`), the secrets, and blocks dangerous commands.
  strict              Also file ownership (an agent writes only its own paths) and a shell allowlist.

In both modes: secret paths, one simple command (no operators, no hidden expansion, no inline code), no
dangerous container options, and the human-only files. Denied commands always lose.

Usage:
  guard.py <agent-id>   per-agent hook in the agent file (user-level install). Fails closed.
  guard.py --auto       one hook for all agents (plugin install). It finds the agent from the
                        `agent_type` input field. For sessions that are not Magenta agents, it
                        only protects the verify state (protect.py).

Write patterns are ordered. The last matching pattern wins. A pattern that starts with "!" denies.
A block is a JSON `deny` decision with the reason for the agent. In a task with --auto, a call that passes the
rules gets `allow`, so Claude Code does not ask. Exit code 2 (fail closed) only when the input or the policy is bad.
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
HUMAN_ONLY = [".magenta/policy.json", ".magenta/checks.lock", ".magenta/verify-state.json", ".magenta/active.json",
              ".magenta/agents/**", "**/acceptance.lock", ".claude/**", ".git/**", ".opencode/**"]
# At any depth too: a session in a workspace can hold repositories in its subfolders.
HARD_DENY_WRITES = HUMAN_ONLY + ["**/" + p for p in HUMAN_ONLY if not p.startswith("**/")]
# Secret files for all agents, in addition to the denies of each agent.
SECRET_DENIES = ["**/.env*", "**/*.pem", "**/*.key", "**/secrets/**", "**/.ssh/**", "**/id_rsa*", "**/id_dsa*",
                 "**/id_ecdsa*", "**/id_ed25519*", "**/*.p12", "**/*.pfx", "**/*.jks", "**/*.keystore", "**/.netrc",
                 "**/.git-credentials", "**/.aws/credentials", "**/.docker/config.json"]
MAKERS = {"engineer", "frontend", "platform", "writer"}
MODES = ("standard", "strict")
# Commands that no agent runs, in both modes: they publish, deploy, rewrite or discard work, delete files, or
# change the computer. A pattern in the `shell` list of `.magenta/policy.json` can allow one of them again.
DANGEROUS_COMMANDS = [
    "git push*", "git pull*", "git merge*", "git rebase*", "git reset --hard*", "git reset --merge*", "git clean*",
    "git checkout -- *", "git checkout .", "git checkout -f*", "git checkout * -- *", "git restore*", "git stash*",
    "git switch -f*", "git switch --discard-changes*", "git branch -D*", "git branch -d*", "git branch --delete*",
    "git tag*", "git config*", "git remote*", "git update-ref*", "git filter-branch*", "git filter-repo*",
    "git reflog*", "git gc*", "git worktree remove*", "git submodule*",
    "rm", "rm *", "rmdir *", "unlink *", "shred *", "dd *", "mkfs*", "chmod -R*", "chown *", "sudo *", "su", "su *",
    "doas *", "kill *", "killall *", "pkill *", "shutdown*", "reboot*", "crontab *", "launchctl *", "systemctl *",
    "kubectl *", "helm install*", "helm upgrade*", "helm uninstall*", "helm delete*", "helm rollback*",
    "terraform apply*", "terraform destroy*", "terraform import*", "terraform state*", "terraform plan*",
    "terraform refresh*", "terraform taint*", "terraform untaint*", "terraform force-unlock*",
    "terraform workspace delete*", "terraform workspace new*", "terraform workspace select*", "tofu apply*",
    "tofu destroy*", "pulumi up*", "pulumi destroy*",
    "docker push*", "docker login*", "docker system prune*", "docker volume rm*", "docker volume prune*",
    "docker image prune*", "docker container prune*", "docker rm *", "docker rmi *", "docker compose down*",
    "docker-compose down*", "podman push*", "podman rm *", "podman rmi *",
    "npm publish*", "yarn publish*", "yarn npm publish*", "pnpm publish*", "cargo publish*", "twine upload*",
    "gem push*", "mvn deploy*", "./mvnw deploy*", "./gradlew publish*", "gradle publish*", "dotnet nuget push*",
    "gh *", "glab *", "ssh *", "scp *", "sftp *", "rsync *",
    "pip install*", "pip3 install*", "python -m pip install*", "python3 -m pip install*", "npm install -g*",
    "npm i -g*", "npm install --global*", "yarn global*", "pnpm add -g*", "brew *", "apt *", "apt-get *",
    "yum *", "dnf *", "apk add*", "choco *", "winget *",
]
CONTAINER_TOOLS = {"docker", "podman", "nerdctl", "docker-compose"}
CONTAINER_HOST_OPTIONS = ("--privileged", "--cap-add", "--device", "--security-opt", "--pid=host", "--ipc=host",
                          "--uts=host", "--userns=host", "--cgroupns=host")
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


def last_match(path: str, patterns) -> bool | None:
    """The decision of the last pattern that matches the path: True (allow), False (`!` deny), or None."""
    decision = None
    for pattern in patterns or []:
        if pattern.startswith("!"):
            if _matches(path, [pattern[1:]]):
                decision = False
        elif _matches(path, [pattern]):
            decision = True
    return decision


def ordered_allow(path: str, patterns) -> bool:
    return last_match(path, patterns) is True


def _project_policy(cwd: Path) -> dict:
    try:
        data = json.loads((cwd / ".magenta" / "policy.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def guard_mode(policy_data: dict) -> str:
    """`standard` or `strict`. The environment variable MAGENTA_GUARD wins over `.magenta/policy.json`."""
    value = os.environ.get("MAGENTA_GUARD") or policy_data.get("guard") or "standard"
    if isinstance(value, dict):
        value = value.get("mode") or "standard"
    value = str(value).strip().lower()
    return value if value in MODES else "strict"  # an unknown value fails closed


def repo_root(target: Path, cwd: Path) -> Path:
    """The repository of a file in the session folder. The write rules of the agents are relative to it.

    1. The nearest folder between the file and the session folder that has `.magenta/` (a Magenta repository in a
       workspace, also when the workspace is a git repository, for example a package in `vendor/`).
    2. Else the session folder, when it is a repository.
    3. Else the nearest folder between the file and the session folder that has `.git`.
    4. Else the session folder."""
    between = []
    for folder in target.parents:
        if folder == cwd or not _inside(folder, cwd):
            break
        between.append(folder)
    for folder in between:
        if (folder / ".magenta").is_dir():
            return folder
    if (cwd / ".magenta").is_dir() or (cwd / ".git").exists():
        return cwd
    for folder in between:
        if (folder / ".git").exists():
            return folder
    return cwd


def _locked_files(root: Path) -> set[str]:
    """The test files that the acceptance locks of the repository protect (paths from the repository root)."""
    found: set[str] = set()
    for lock in (root / ".magenta" / "work").glob("*/acceptance.lock"):
        try:
            found.update(json.loads(lock.read_text(encoding="utf-8")).get("files", {}))
        except (OSError, ValueError, AttributeError):
            continue
    return {_norm(f) for f in found}


def _mount_roots(cwd: Path, policy_data: dict) -> list[Path]:
    """Host folders that a container can mount: the session folder, the git repository that holds it (a package
    inside an application), and the `mounts` of `.magenta/policy.json`."""
    roots = [cwd]
    try:
        home = Path.home().resolve()
    except (RuntimeError, OSError):
        home = None
    for folder in cwd.parents:
        if folder == home or folder.parent == folder:
            break  # never the home folder (a git repository of dotfiles) or the root of the disk
        if (folder / ".git").exists():
            roots.append(folder)
            break
    for raw in policy_data.get("mounts") or []:
        try:
            path = Path(str(raw)).expanduser()
            roots.append((path if path.is_absolute() else cwd / path).resolve())
        except (OSError, ValueError):
            continue
    return roots


def _bind_source(spec: str) -> str | None:
    """The host path of `-v <host>:<container>[:options]`, or None for a named or anonymous volume."""
    drive = re.match(r"^[A-Za-z]:[\\/]", spec)
    rest = spec[2:] if drive else spec
    if ":" not in rest:
        return None
    host = (spec[:2] if drive else "") + rest.split(":", 1)[0]
    return host if drive or host.startswith(("/", ".", "~")) else None


def _mount_source(spec: str) -> str | None:
    """The host path of `--mount type=bind,source=<host>,...`, or None."""
    fields = dict(part.split("=", 1) for part in spec.split(",") if "=" in part)
    source = fields.get("source") or fields.get("src")
    if not source or fields.get("type", "bind") != "bind" and not source.startswith(("/", ".", "~")):
        return None
    return source


def _container_problem(tokens, cwd: Path, policy_data: dict, denies) -> str | None:
    """A container option that reaches the computer outside the project: a mount of a folder outside the session
    folder, the Docker socket, or a host option such as `--privileged`. None when there is no such option."""
    if not tokens or re.split(r"[\\/]", tokens[0])[-1].lower().removesuffix(".exe") not in CONTAINER_TOOLS:
        return None
    socket = next((w for w in tokens if "docker.sock" in w or "podman.sock" in w), None)
    if socket:
        return f"the container socket ({socket})"
    for i, word in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if any(word == o or word.startswith(o + "=") for o in CONTAINER_HOST_OPTIONS):
            return f"the host option {word}"
        if word in ("--pid", "--ipc", "--uts", "--userns", "--cgroupns") and nxt == "host":
            return f"the host option {word} host"
        source = None
        if word in ("-v", "--volume"):
            source = _bind_source(nxt)
        elif word.startswith("--volume="):
            source = _bind_source(word.split("=", 1)[1])
        elif word.startswith("-v") and len(word) > 2 and word[2] != "-":
            source = _bind_source(word[2:])
        elif word == "--mount":
            source = _mount_source(nxt)
        elif word.startswith("--mount="):
            source = _mount_source(word.split("=", 1)[1])
        if source is None:
            continue
        host = Path(source).expanduser()
        host = (host if host.is_absolute() else cwd / host).resolve()
        if not any(host == root or _inside(host, root) for root in _mount_roots(cwd, policy_data)):
            return (f"a mount of {source}, outside the project. The human can add the folder to `mounts` in "
                    ".magenta/policy.json")
        rel = host.relative_to(cwd).as_posix() if _inside(host, cwd) else host.as_posix()
        if _matches(rel, denies) or _matches(rel + "/x", denies) or _matches(host.name, denies):
            return f"a mount of the secret path {source}"
    return None


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
    project = _project_policy(cwd)
    extra = project.get(agent, {}) if isinstance(project.get(agent), dict) else {}
    denies = list(policy.get("denies", [])) + SECRET_DENIES

    if tool == "Bash":
        return _decide_shell(me, policy, extra, project, denies, cwd, str(tool_input.get("command") or ""))

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
        project = _project_policy(root)
        extra = project.get(agent, {}) if isinstance(project.get(agent), dict) else {}
    writes = list(policy.get("writes", [])) + list(extra.get("writes", []))

    if _matches(rel, denies) or _matches(target.name, denies):
        return f"{me} cannot access the secret path {rel}"
    if tool not in WRITE_TOOLS:
        return None
    if not inside:
        return f"{me} cannot write outside the project: {rel}"
    if _matches(rel, HARD_DENY_WRITES):
        return f"{me} cannot write {rel}. Only the human changes this file."
    locked = _norm(rel) in _locked_files(root)
    if locked and agent in MAKERS:
        return (f"{me} cannot write {rel}: the human sealed this test in the acceptance lock. Fix the code, not the "
                "test. If the test is wrong, return BLOCKED with the evidence.")
    decision = last_match(rel, writes)
    owned = ", ".join(writes)
    if guard_mode(project) == "strict" or locked or _norm(rel).startswith(".magenta/"):
        if decision is not True:  # the process files, the locked tests, and strict mode: only the own paths
            return (f"{me} cannot write {rel}. Its write rules: {owned}. Report the needed change to the owner of "
                    "the file.")
    elif decision is False:  # standard mode: only the paths that the rules deny with `!`
        return (f"{me} cannot write {rel}: another role owns it (a `!` rule of {me}). Report the needed change to "
                "the conductor.")
    return None


def _human_only_token(token: str, cwd: Path) -> bool:
    """True if a word of a command names a human-only file in the session folder (for example `.magenta/policy.json`).
    Paths outside the session folder (for example the verify script in ~/.claude) do not count."""
    if PureWindowsPath(token).drive and os.name != "nt":
        return False  # a Windows path: not in this session folder
    path = Path(token).expanduser()
    if path.is_absolute():
        try:
            token = path.resolve().relative_to(cwd).as_posix()
        except (ValueError, OSError):
            return False
    return _matches(token, HARD_DENY_WRITES)


def _decide_shell(me: str, policy: dict, extra: dict, project: dict, denies, cwd: Path, raw: str):
    command = " ".join(raw.split())
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
    shell = list(policy.get("shell", [])) + list(extra.get("shell", []))
    shell_deny = list(policy.get("shell_deny", [])) + list(extra.get("shell_deny", []))
    if not shell:
        return f"{me} has no shell. Report the need to the conductor."
    if any(fnmatch.fnmatchcase(command, p) for p in shell_deny):
        return f"{me} cannot run {command!r}: the command is denied"
    allowed_by_human = any(fnmatch.fnmatchcase(command, p) for p in extra.get("shell", []))
    if not allowed_by_human and any(fnmatch.fnmatchcase(command, p) for p in DANGEROUS_COMMANDS):
        return (f"{me} cannot run {command!r}: it can publish, deploy, discard work, delete files, or change the "
                "computer. Agents never push, merge, or deploy. Report the need to the conductor.")
    allowing = [p for p in shell if fnmatch.fnmatchcase(command, p)]
    if guard_mode(project) == "strict" and not allowing:
        return f"{me} cannot run {command!r}. Allowed commands: {shell or 'none'}"
    try:
        tokens = shlex.split(command)
    except ValueError:
        return f"{me} cannot run {command!r}: the quotes are not valid"
    names_verify = any(re.split(r"[\\/]", t)[-1].lower() == "verify.py" for t in tokens[:2])
    if (names_verify or (allowing and all("verify.py" in p for p in allowing))) and not _is_verify_command(tokens, cwd):
        return (f"{me} cannot run {command!r}. The verify script runs as: <python> <path>/verify.py <command>, "
                "and the script is outside the project.")
    unsafe = _unsafe_git_option(tokens)
    if unsafe:
        return f"{me} cannot run {command!r}: the git option {unsafe!r} writes a file or runs a program"
    inline = _inline_code(tokens)
    if inline:
        return (f"{me} cannot run {command!r}: `{inline}` runs code from the command line, and that code is "
                "outside the write and secret rules. Put the code in a test or a script, or report the need to the "
                "conductor.")
    container = _container_problem(tokens, cwd, project, denies)
    if container:
        return f"{me} cannot run {command!r}: {container}."
    for word in tokens:
        secret = _secret_by_glob(word, cwd, denies)
        if secret:
            return f"{me} cannot access the secret path {secret!r} (from the wildcard {word!r})"
        for token in re.split(r"[\s:=]+", word):
            token = token[2:] if token.startswith("./") else token
            if token and (_matches(token, denies) or _matches(Path(token).name, denies)):
                return f"{me} cannot access the secret path {token!r}"
        for token in [word, *re.split(r"[:=]", word)]:
            token = token[2:] if token.startswith("./") else token
            if token and _human_only_token(token, cwd):
                return f"{me} cannot name {token!r} in a shell command. Only the human changes this file."
    return None


def _load_policy(agent: str):
    path = Path(__file__).resolve().parent / "policies" / f"{agent}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# The rules for the main session and other subagents in an --auto task: the same checks as for an agent in
# standard mode, with all paths and commands of the project. A call that does not pass gets the normal prompt.
MAIN_POLICY = {"writes": ["**"], "shell": ["*"], "shell_deny": [], "denies": []}
FILE_TOOLS = WRITE_TOOLS | {"Read", "Glob", "Grep"}


def auto_allows(event: dict, agent: str | None = None, policy: dict | None = None) -> bool:
    """True when the human started the task of this session with --auto and the call passes the rules. Then the
    hook allows the call, and Claude Code does not ask. Files must be in the session folder."""
    try:
        import verify  # next to this file in the plugin and in ~/.claude/magenta
        if not verify.auto_session(event):
            return False
    except Exception:
        return False
    if event.get("tool_name") in FILE_TOOLS:
        tool_input = event.get("tool_input") or {}
        raw = next((tool_input[k] for k in PATH_KEYS if tool_input.get(k)), None)
        if raw is not None:
            cwd = Path(event.get("cwd") or os.getcwd()).resolve()
            target = Path(str(raw)).expanduser()
            if not _inside((target if target.is_absolute() else cwd / target).resolve(), cwd):
                return False
    elif event.get("tool_name") != "Bash":
        return False
    return decide(agent or "conductor", policy or MAIN_POLICY, event) is None


def _emit(kind: str, reason: str = "") -> int:
    code, out, err = protect.hook_output(kind, reason)
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code


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
    event = event if isinstance(event, dict) else {}
    if argv[0] == "--auto":
        agent = agent_id_from_type(event.get("agent_type"))
        if agent is None:  # not a Magenta agent: the verify state is protected; --auto tasks skip the prompts
            kind, reason = protect.evaluate(event)
            if kind == "ask":
                try:  # the plugin has verify.py next to this file: show what the human approves
                    import verify
                    reason += verify.approval_details(event)
                except Exception:
                    pass
            if kind == "allow" and auto_allows(event):
                kind, reason = "auto", "Magenta: the task runs with --auto"
            return _emit(kind, reason)
    else:
        agent = argv[0]
    try:
        policy = _load_policy(agent)
    except (OSError, ValueError) as exc:
        print(f"Magenta guard: blocked, because the policy of {agent!r} is not readable: {exc}", file=sys.stderr)
        return 2
    reason = decide(agent, policy, event)
    if reason:
        return _emit("deny", f"Magenta guard: {reason}")
    if auto_allows(event, agent, policy):
        return _emit("auto", "Magenta: the task runs with --auto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
