#!/usr/bin/env python3
"""Magenta verify: the rules of a repository as commands (ADR-0012).

Checks are in `.magenta/checks/*.yaml`. Each agent writes only its own file: `qa.yaml` (QA),
`architect.yaml` (Architect), `project.yaml` (Principal), `sre.yaml` (SRE), `security.yaml` (Security),
or `database.yaml` (Database). The human can write any file.
A check runs only after the human approves its exact command, set, and work item (`.magenta/checks.lock`),
because a check is a command that runs on the computer of the human. The approval also seals the test locks.

Commands:
  verify.py run [--set quick|task|full|all] [--only ID,ID]  run the approved checks, record the result
  verify.py list | status                                 show the checks, the active task, the result
  verify.py approve [ID ...]                              (human only) approve checks and seal test locks;
                                                          in Claude Code, the permission dialog is the approval
  verify.py start <work-item> [--session ID] [--force]    (conductor) start or resume a task
  verify.py finish [--force]                              (conductor) close the task; --force: human only
  verify.py lock <work-item> [FILE ...]                   lock the test files of a work item
  verify.py check-lock [<work-item>]                      check the locked test files
  verify.py install-hook [--no-protect] | uninstall-hook  (human) Claude Code hooks for this repository
  verify.py hook                                          Claude Code Stop hook (JSON on stdin)
  verify.py protect                                       Claude Code PreToolUse hook (JSON on stdin)

All commands take `--repo PATH` (default: the git root of the current folder).
Exit codes of `run`: 0 all selected checks pass; 1 a check failed, or the code changed during the run;
2 configuration error; 3 nothing failed, but some checks wait for approval; 4 no checks exist.
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import YamlError, parse_yaml  # noqa: E402
import lock as test_lock  # noqa: E402
import protect  # noqa: E402

SETS = ("quick", "full", "manual")
SET_SELECTION = {"quick": ("quick",), "full": ("quick", "full"), "all": ("quick", "full", "manual")}
# --set task: the quick checks and the full checks of the active work item (what "done" needs)
RUN_SETS = ("quick", "task", "full", "all")
DEFAULT_TIMEOUT = 600
MAX_BLOCKS = 2  # Stop hook: the maximum number of blocks in one turn of the human
HOOK_TIMEOUT = 120
PASS = "PASS"
OK_TO_CLOSE = (PASS, "NO CHECKS")
# Untracked files in these folders, or with these endings, are build or test outputs, not code. Tracked files
# always count. (Most repositories ignore them in .gitignore already.)
ARTIFACT_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", "htmlcov",
                 "node_modules", ".gradle", ".next", "test-results", "playwright-report"}
# These names are common in source paths (src/bin/tool.py), so they are outputs only at the repository root.
ROOT_ARTIFACT_DIRS = {"coverage", "build", "target", "out", "dist", "bin", "obj"}
ARTIFACT_ENDINGS = (".pyc", ".pyo", ".class", ".coverage", "coverage.xml", ".log")
SETTINGS = Path(".claude") / "settings.local.json"


class VerifyError(Exception):
    pass


# ----- paths and small helpers -----

def _git(repo: Path, *args, env=None) -> bytes | None:
    try:
        out = subprocess.run(["git", *args], cwd=repo, capture_output=True, env=env)
    except OSError:
        return None
    return out.stdout if out.returncode == 0 else None


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", "replace").strip()


def find_repo(start: Path) -> Path:
    raw = _git(Path(start), "rev-parse", "--show-toplevel")
    return Path(_text(raw)).resolve() if raw and _text(raw) else Path(start).resolve()


def _git_path(repo: Path, name: str) -> Path | None:
    raw = _git(repo, "rev-parse", "--git-path", name)
    if raw is None:
        return None
    path = Path(_text(raw))
    return path if path.is_absolute() else repo / path


def config_root(repo: Path) -> Path:
    """The working tree that holds the checks and the approvals. In a linked git worktree, it is the main
    working tree, so that all worktrees use the same approved checks."""
    raw = _git(repo, "rev-parse", "--git-common-dir")
    if raw:
        common = Path(_text(raw))
        common = (common if common.is_absolute() else repo / common).resolve()
        if common.name == ".git" and (common.parent / ".magenta").is_dir():
            return common.parent
    return repo


def _mdir(repo: Path) -> Path:
    return repo / ".magenta"


def _checks_lock(repo: Path) -> Path:
    return _mdir(config_root(repo)) / "checks.lock"


def _read_json(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def self_command() -> str:
    """The command that runs this script, for messages and hooks (it also works in Git Bash on Windows)."""
    return f'"{Path(sys.executable).as_posix()}" "{Path(__file__).resolve().as_posix()}"'


def git_exclude(repo: Path, entry: str) -> bool:
    """Add an entry to `.git/info/exclude`. Return True if the entry was added."""
    path = _git_path(repo, "info/exclude")
    if path is None:
        return False
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if entry in current.split():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(("" if current.endswith("\n") or not current else "\n") + entry + "\n")
    return True


# ----- checks and approval -----

def load_checks(repo: Path) -> list[dict]:
    folder = _mdir(config_root(repo)) / "checks"
    checks: list[dict] = []
    seen: dict[str, str] = {}
    for path in sorted(folder.glob("*.yaml")) if folder.is_dir() else []:
        try:
            data = parse_yaml(path.read_text(encoding="utf-8")) or {}
        except (YamlError, UnicodeDecodeError) as exc:
            raise VerifyError(f"{path.name}: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("checks") or [], list):
            raise VerifyError(f"{path.name}: the file must be a map with a 'checks' list")
        for raw in data.get("checks") or []:
            if not isinstance(raw, dict):
                raise VerifyError(f"{path.name}: each check must be a map")
            cid = str(raw.get("id") or "").strip()
            command = raw.get("command")
            if isinstance(command, bool):  # the YAML subset reads `true` and `false` as booleans
                command = "true" if command else "false"
            if not cid or not command:
                raise VerifyError(f"{path.name}: each check needs an 'id' and a 'command'")
            if not re.fullmatch(r"[A-Za-z0-9._-]+", cid) or cid.startswith("lock."):
                raise VerifyError(f"{path.name}: the id {cid!r} can contain only letters, digits, and . _ - "
                                  "(and cannot start with 'lock.')")
            if cid in seen:
                raise VerifyError(f"{path.name}: the id {cid!r} is also in {seen[cid]}")
            seen[cid] = path.name
            cset = str(raw.get("set") or "quick")
            if cset not in SETS:
                raise VerifyError(f"{path.name}: check {cid!r}: 'set' must be one of {', '.join(SETS)}")
            try:
                timeout = int(raw.get("timeout") or DEFAULT_TIMEOUT)
            except (TypeError, ValueError) as exc:
                raise VerifyError(f"{path.name}: check {cid!r}: 'timeout' must be a number of seconds") from exc
            check = {
                "id": cid,
                "name": str(raw.get("name") or cid),
                "command": " ".join(str(c) for c in command) if isinstance(command, list) else str(command),
                "set": cset,
                "source": path.stem,
                "timeout": timeout,
                "cwd": str(raw.get("cwd") or ""),
                "work_item": str(raw.get("work_item") or ""),
                "why": str(raw.get("why") or ""),
                "file": path.name,
            }
            check["hash"] = check_hash(check)
            checks.append(check)
    return checks


def check_hash(check: dict) -> str:
    """The approved identity of a check: what it runs, where, in which set, and for which work item."""
    key = json.dumps({k: check[k] for k in ("id", "command", "cwd", "set", "work_item")}, sort_keys=True)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _approval_data(repo: Path) -> dict:
    data = _read_json(_checks_lock(repo), {})
    approved = data.get("approved") if isinstance(data.get("approved"), dict) else {}
    locks = data.get("locks") if isinstance(data.get("locks"), dict) else {}
    return {"approved": approved, "locks": locks}


def approvals(repo: Path) -> dict:
    return _approval_data(repo)["approved"]


def check_status(check: dict, approved: dict) -> str:
    """'approved', 'pending' (never approved), or 'changed' (approved, then the check changed)."""
    entry = approved.get(check["id"])
    if not isinstance(entry, dict):
        return "pending"
    return "approved" if entry.get("hash") == check["hash"] else "changed"


def _lock_files(repo: Path) -> dict[str, Path]:
    work = _mdir(repo) / "work"
    return {p.name: p / test_lock.LOCK_NAME for p in (sorted(work.iterdir()) if work.is_dir() else [])
            if (p / test_lock.LOCK_NAME).is_file()}


def approve(repo: Path, ids: list[str]) -> tuple[list[dict], list[str], list[str]]:
    """Approve new and changed checks, confirm removed ones, and seal the test locks.
    Without ids: all of them. Return (approved checks, removed ids, sealed lock ids)."""
    checks = load_checks(repo)
    data = _approval_data(repo)
    approved, seals = data["approved"], data["locks"]
    known = {c["id"] for c in checks}
    removed = [i for i in approved if i not in known]
    files = _lock_files(repo)
    lock_ids = {f"lock.{name}" for name in set(files) | set(seals)}
    unknown = sorted(set(ids) - known - set(removed) - lock_ids)
    if unknown:
        raise VerifyError(f"unknown check ids: {', '.join(unknown)}")
    if ids:
        selected = [c for c in checks if c["id"] in ids]
        pruned = [i for i in removed if i in ids]
        sealed = sorted(i[len("lock."):] for i in ids if i in lock_ids)
    else:
        selected = [c for c in checks if check_status(c, approved) != "approved"]
        pruned = removed
        sealed = sorted(set(files) | set(seals))
    for c in selected:
        approved[c["id"]] = {"hash": c["hash"], "command": c["command"], "cwd": c["cwd"], "set": c["set"],
                             "work_item": c["work_item"], "at": _now()}
    for i in pruned:
        del approved[i]
    for name in sealed:
        if name in files:
            seals[name] = _file_hash(files[name])
        else:
            seals.pop(name, None)
    _write_json(_checks_lock(repo), {"approved": approved, "locks": seals})
    return selected, pruned, [f"lock.{n}" for n in sealed]


# ----- fingerprint of the code -----

def fingerprint(repo: Path) -> str | None:
    """A content hash of the working tree: the tracked files and the untracked files that git does not ignore,
    without `.magenta/`, plus the locked tests in `.magenta/work/*/`. A commit of the same content does not
    change it. None outside a git repository."""
    if _git(repo, "rev-parse", "--git-dir") is None:
        return None
    return (_tree_fingerprint(repo) or _diff_fingerprint(repo)) + _acceptance_digest(repo)


def _tree_fingerprint(repo: Path) -> str | None:
    """`git write-tree` of a temporary index that has all files (the real index does not change)."""
    index = _git_path(repo, "index")
    tmp = Path(tempfile.mkdtemp(prefix="magenta-verify-"))
    try:
        temp_index = tmp / "index"
        if index is not None and index.is_file():
            shutil.copyfile(index, temp_index)
        env = dict(os.environ, GIT_INDEX_FILE=str(temp_index))
        hidden = [e[2:] for e in (_git(repo, "ls-files", "-v", "-z", env=env) or b"").split(b"\0")
                  if e[:1].islower() or e[:1] == b"S"]  # assume-unchanged and skip-worktree files
        for flag in ("--no-assume-unchanged", "--no-skip-worktree") if hidden else ():
            subprocess.run(["git", "update-index", flag, "-z", "--stdin"], cwd=repo, env=env,
                           input=b"\0".join(hidden) + b"\0", capture_output=True)
        untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z")
        # No pathspec here: git add exits with 1 when a pathspec names an ignored path (.magenta/ usually is).
        if _git(repo, "add", "-A", env=env) is None or untracked is None:
            return None
        _git(repo, "rm", "-r", "--cached", "-q", "--ignore-unmatch", "--", ".magenta", env=env)
        artifacts = [n for n in untracked.split(b"\0") if n and _is_artifact(n.decode("utf-8", "replace"))]
        if artifacts:
            subprocess.run(["git", "update-index", "--force-remove", "-z", "--stdin"], cwd=repo, env=env,
                           input=b"\0".join(artifacts) + b"\0", capture_output=True)
        tree = _git(repo, "write-tree", env=env)
        return "tree:" + _text(tree) if tree else None
    except OSError:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _is_artifact(path: str) -> bool:
    parts = path.split("/")
    return (any(p in ARTIFACT_DIRS for p in parts[:-1]) or (len(parts) > 1 and parts[0] in ROOT_ARTIFACT_DIRS)
            or parts[-1].endswith(ARTIFACT_ENDINGS))


def _diff_fingerprint(repo: Path) -> str:
    """Fallback: HEAD, the changes against HEAD, and the untracked files."""
    head = _git(repo, "rev-parse", "HEAD")
    digest = hashlib.sha256(head or b"no-commit")
    exclude = ["--", ".", ":(exclude).magenta"]
    diff = _git(repo, "diff", "HEAD", "--binary", "--no-color", "--no-ext-diff", *exclude) if head else \
        _git(repo, "diff", "--cached", "--binary", "--no-color", "--no-ext-diff", *exclude)
    digest.update(diff or b"")
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z", *exclude) or b""
    for name in sorted(n for n in untracked.split(b"\0") if n and not _is_artifact(n.decode("utf-8", "replace"))):
        digest.update(name)
        try:
            digest.update(hashlib.sha256((repo / name.decode("utf-8", "replace")).read_bytes()).digest())
        except OSError:
            pass
    return "diff:" + digest.hexdigest()


def _acceptance_digest(repo: Path) -> str:
    """The tests in `.magenta/work/*/acceptance/` and the lock files are code too."""
    work = _mdir(repo) / "work"
    files: list[Path] = []
    for item in (work.iterdir() if work.is_dir() else []):
        if item.is_dir():
            files += [p for p in [item / test_lock.LOCK_NAME] if p.is_file()]
            files += [p for p in (item / "acceptance").rglob("*") if p.is_file()]
    if not files:
        return ""
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.relative_to(repo).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return "+acc:" + digest.hexdigest()[:16]


# ----- the active task -----

def active(repo: Path) -> dict:
    return _read_json(_mdir(repo) / "active.json", {})


def _clean_session(value) -> str:
    value = str(value or "").strip()
    return "" if not value or value.startswith("$") or "{" in value else value


def _blocks_close(repo: Path, data: dict) -> str | None:
    """Return the status when the active task cannot close (the code changed and the checks do not pass)."""
    if not data.get("work_item") or fingerprint(repo) == data.get("base_fingerprint"):
        return None
    status = evaluate(repo)["status"]
    return None if status in OK_TO_CLOSE else status


def start(repo: Path, item: str, session=None, force: bool = False) -> dict:
    """Start a task, or resume it when it is already active (the base fingerprint does not change).
    A task that changed code and does not pass cannot be replaced, and cannot be taken over by another session,
    without --force."""
    session = _clean_session(session)
    data = active(repo)
    current = data.get("work_item")
    owner = data.get("session") or ""
    other_session = bool(owner and session and owner != session)
    if current and not force and (current != item or other_session):
        status = _blocks_close(repo, data)
        if status:
            raise VerifyError(f"the task {current} is active, changed the code, and its checks do not pass "
                              f"({status}). Finish it first. Only the human can replace it: "
                              f"{self_command()} start {item} --force")
    if current == item:
        data.update(session=session or owner, resumed_at=_now())
        _write_json(_mdir(repo) / "active.json", data)
        return data
    note = f"replaced the task {current} of another session" if current and other_session else ""
    data = {"work_item": item, "session": session, "base_fingerprint": fingerprint(repo), "started_at": _now(),
            "blocks": 0, "previous": current or data.get("last"), "note": note}
    _write_json(_mdir(repo) / "active.json", data)
    return data


def finish(repo: Path, force: bool = False) -> dict:
    data = active(repo)
    item = data.get("work_item")
    if not item:
        return {"work_item": None, "last": data.get("last"), "last_status": "NO TASK"}
    status = evaluate(repo)["status"]
    if not force and _blocks_close(repo, data):
        raise VerifyError(f"the checks of {item} do not pass on the current code ({status}). Fix them, or ask the "
                          f"human to close the task: {self_command()} finish --force")
    out = {"work_item": None, "last": item, "last_status": status + (" (closed by the human)" if force else ""),
           "finished_at": _now()}
    _write_json(_mdir(repo) / "active.json", out)
    return out


# ----- selection and evaluation -----

def _active_lock(repo: Path, item: str | None, seals: dict):
    """Return (state, check) for the test lock of the active work item, or None."""
    if not item:
        return None
    try:
        folder = test_lock.find_work_item(repo, item)
    except test_lock.LockError:
        folder = None
    name = folder.name if folder else item
    check = {"id": f"lock.{name}", "name": f"Locked tests of {name}", "builtin": "lock", "item": name,
             "set": "quick", "source": "lock", "work_item": item, "command": "", "cwd": ""}
    lock_file = folder / test_lock.LOCK_NAME if folder else None
    if lock_file is not None and lock_file.is_file():
        check["hash"] = _file_hash(lock_file)
        if name not in seals:
            return "pending", check
        return ("runnable", check) if seals[name] == check["hash"] else ("invalid", dict(check, status="CHANGED"))
    if name in seals:
        return "invalid", dict(check, status="REMOVED", hash="")
    return None


def required(repo: Path, set_name: str = "quick", only: list[str] | None = None):
    """Return (runnable, pending, invalid) checks: the checks of the set (or `only`) and the test lock of the
    active work item. The set `task` has the quick checks and the full checks linked to the active work item:
    the checks that "done" needs. `invalid`: approved checks that changed or were removed after the approval.
    """
    item = active(repo).get("work_item")
    data = _approval_data(repo)
    approved = data["approved"]
    checks = load_checks(repo)
    picked = []
    for c in checks:
        if only:
            take = c["id"] in only
        elif set_name == "task":
            take = c["set"] == "quick" or (bool(item) and c["work_item"] == item and c["set"] == "full")
        else:
            take = c["set"] in SET_SELECTION[set_name]
        if take:
            picked.append(c)
    runnable = [c for c in picked if check_status(c, approved) == "approved"]
    pending = [c for c in picked if check_status(c, approved) == "pending"]
    scope = picked if only else checks
    invalid = [dict(c, status="CHANGED") for c in scope if check_status(c, approved) == "changed"]
    if not only:
        known = {c["id"] for c in checks}
        invalid += [{"id": i, "name": i, "set": "-", "source": "-", "status": "REMOVED", "hash": ""}
                    for i in approved if i not in known]
    lock_state = _active_lock(repo, item, data["locks"])
    if lock_state and (not only or lock_state[1]["id"] in only):
        {"runnable": runnable, "pending": pending, "invalid": invalid}[lock_state[0]].append(lock_state[1])
    return runnable, pending, invalid


def evaluate(repo: Path, current: str | None = None) -> dict:
    """The result for the current code, from the recorded runs: PASS, FAIL, NOT VERIFIED, NO CHECKS, or ERROR."""
    out = {"status": "", "failed": [], "not_run": [], "runnable": [], "pending": [], "pending_linked": [],
           "invalid": [], "error": "", "full": False}
    try:
        runnable, pending, invalid = required(repo, "task")
    except (VerifyError, test_lock.LockError, OSError) as exc:
        out.update(status="ERROR", error=str(exc))
        return out
    item = active(repo).get("work_item")
    out.update(runnable=[c["id"] for c in runnable], pending=[c["id"] for c in pending],
               pending_linked=[c["id"] for c in pending if item and c.get("work_item") == item],
               invalid=[f"{c['id']} ({c['status']})" for c in invalid])
    if not runnable and not invalid:
        out["status"] = "NO CHECKS"
        return out
    current = current or fingerprint(repo)
    state = _read_json(_mdir(repo) / "verify-state.json", {})
    results = state.get("results") if state.get("fingerprint") == current and isinstance(state.get("results"), dict) \
        else {}
    for c in runnable:
        result = results.get(c["id"]) or {}
        if result.get("hash") != c["hash"]:
            out["not_run"].append(c["id"])
            out["full"] = out["full"] or c["set"] == "full"
        elif result.get("status") != PASS:
            out["failed"].append(c["id"])
    out["status"] = "FAIL" if (out["failed"] or invalid) else ("NOT VERIFIED" if out["not_run"] else PASS)
    return out


# ----- run -----

def _windows_bash() -> str | None:
    """Git Bash on Windows (the shell of Claude Code there). Not the bash of WSL."""
    configured = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if configured and Path(configured).is_file():
        return configured
    git = shutil.which("git")
    if git:
        base = Path(git).resolve().parent.parent
        for candidate in (base / "bin" / "bash.exe", base / "usr" / "bin" / "bash.exe"):
            if candidate.is_file():
                return str(candidate)
    return None


def _execute(command: str, cwd: Path, timeout: int):
    """Run a shell command. Return (exit code or None on timeout, output). A timeout stops all its processes.
    The shell is sh on macOS and Linux, and Git Bash on Windows when it exists (else cmd)."""
    kwargs = {"cwd": cwd, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "text": True,
              "encoding": "utf-8", "errors": "replace"}
    args = command
    if os.name == "posix":
        kwargs.update(shell=True, start_new_session=True)
    else:
        bash = _windows_bash()
        if bash:
            args = [bash, "-c", command]
        else:
            kwargs["shell"] = True
    proc = subprocess.Popen(args, **kwargs)
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, out or ""
    except subprocess.TimeoutExpired:
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        except OSError:
            proc.kill()
        out, _ = proc.communicate()
        return None, out or ""


def _run_one(repo: Path, check: dict, log_dir: Path) -> dict:
    started = time.monotonic()
    if check.get("builtin") == "lock":
        problems = test_lock.check(repo, check["item"])
        status, output = (PASS, "The locked tests did not change.\n") if not problems else ("FAIL", "\n".join(problems))
    else:
        cwd = (repo / check["cwd"]) if check["cwd"] else repo
        try:
            code, output = _execute(check["command"], cwd, check["timeout"])
            status = "TIMEOUT" if code is None else (PASS if code == 0 else "FAIL")
            if code is None:
                output += f"\n[magenta] timeout after {check['timeout']} s\n"
        except OSError as exc:
            status, output = "ERROR", str(exc)
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / (re.sub(r"[^A-Za-z0-9._-]", "_", check["id"]) + ".log")
    log.write_text(output, encoding="utf-8")
    return {"id": check["id"], "status": status, "seconds": round(time.monotonic() - started, 1),
            "set": check["set"], "source": check["source"], "log": log.relative_to(repo).as_posix(), "at": _now(),
            "hash": check.get("hash", ""), "tail": "\n".join(output.splitlines()[-25:]) if status != PASS else ""}


def _invalid_result(check: dict) -> dict:
    return {"id": check["id"], "status": check["status"], "seconds": 0, "set": check.get("set", "-"),
            "source": check.get("source", "-"), "log": "", "at": _now(), "hash": "", "tail": ""}


def run(repo: Path, set_name: str = "quick", only: list[str] | None = None) -> dict:
    """Run the selected checks. The results belong to the code before the run. The state is saved after each
    check, so that a stopped run keeps the results that it has."""
    runnable, pending, invalid = required(repo, set_name, only)
    item = active(repo).get("work_item")
    log_dir = _mdir(repo) / "runs" / "verify" / dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    state_file = _mdir(repo) / "verify-state.json"
    before = fingerprint(repo)
    previous = _read_json(state_file, {})
    merged = dict(previous.get("results") or {}) if before and previous.get("fingerprint") == before else {}
    state = {"fingerprint": before, "at": _now(), "set": set_name, "work_item": item, "results": merged,
             "pending": [c["id"] for c in pending]}
    keys = ("status", "seconds", "set", "source", "log", "at", "hash")
    results = [_invalid_result(c) for c in invalid]
    for r in results:
        merged[r["id"]] = {k: r[k] for k in keys}
    _write_json(state_file, state)
    for c in runnable:
        r = _run_one(repo, c, log_dir)
        results.append(r)
        merged[r["id"]] = {k: r[k] for k in keys}
        _write_json(state_file, state)
    after = fingerprint(repo)
    changed = bool(before) and after != before
    if changed:
        state["changed_during_run"] = True
        _write_json(state_file, state)
    if results:
        _write_json(log_dir / "summary.json", {"at": state["at"], "set": set_name, "work_item": item,
                                               "fingerprint": before, "changed_during_run": changed,
                                               "results": results, "pending": state["pending"]})
    data = active(repo)
    if data.get("work_item") and not changed and evaluate(repo, before)["status"] == PASS:
        data["blocks"] = 0
        _write_json(_mdir(repo) / "active.json", data)
    return {"results": results, "pending": pending, "state": state, "changed_files": changed,
            "empty": not (runnable or pending or invalid)}


def exit_code(outcome: dict) -> int:
    if any(r["status"] != PASS for r in outcome["results"]) or outcome.get("changed_files"):
        return 1
    if outcome.get("empty"):
        return 4
    return 3 if outcome["pending"] else 0


def summary(outcome: dict) -> str:
    results, pending = outcome["results"], outcome["pending"]
    passed = sum(1 for r in results if r["status"] == PASS)
    code = exit_code(outcome)
    verdict = {0: "PASS", 1: "FAIL", 3: "PASS, but some checks wait for approval", 4: "NO CHECKS"}[code]
    lines = [f"Magenta verify: {verdict}. {passed} passed, {len(results) - passed} failed, "
             f"{len(pending)} wait for approval.", "",
             "| Check | Source | Set | Result | Time (s) |", "|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['source']} | {r['set']} | {r['status']} | {r['seconds']} |" for r in results]
    lines += [f"| {c['id']} | {c['source']} | {c['set']} | WAITS FOR APPROVAL | - |" for c in pending]
    if outcome.get("empty"):
        lines += ["| (no checks) | | | | |", "", "No check exists for this selection. Nothing was verified."]
    for r in results:
        if r["status"] in ("FAIL", "TIMEOUT", "ERROR"):
            lines += ["", f"--- {r['id']}: {r['status']} (log: {r['log']}) ---", r["tail"]]
    changed = [r["id"] for r in results if r["status"] == "CHANGED"]
    removed = [r["id"] for r in results if r["status"] == "REMOVED"]
    if changed:
        lines += ["", f"These checks or locks changed after the human approved them: {', '.join(changed)}. "
                      "Restore them, or ask the human to approve the change."]
    if removed:
        lines += ["", f"These approved checks or locks were removed: {', '.join(removed)}. "
                      "Only the human confirms a removal."]
    if pending or changed or removed:
        ids = " ".join([c["id"] for c in pending] + changed + removed)
        lines += ["", "To approve: show the human the checks (`list`), then run the approve command below. Claude Code "
                      "asks the human to confirm it. That confirmation is the approval. (In a terminal, the human can "
                      "run the same command.)", f"  {self_command()} approve {ids}"]
    if outcome.get("changed_files"):
        lines += ["", "The code changed during the run (by a check, or by another process). These results are for "
                      "the code before the run. Run verify again. If a check writes files, add them to .gitignore."]
    return "\n".join(lines)


# ----- Claude Code hooks -----

def hook(event: dict) -> tuple[int, str]:
    """Stop hook. Return (exit code, text). Exit 2 blocks the stop; the text goes to the agent.
    Exit 0 with text: the text goes to the human as a system message."""
    repo = find_repo(Path(event.get("cwd") or os.getcwd()))
    data = active(repo)
    item, session = data.get("work_item"), data.get("session")
    if not item or not session or session != event.get("session_id"):
        return 0, ""  # no task, or the task does not belong to this session
    if not event.get("stop_hook_active") and data.get("blocks"):
        data["blocks"] = 0  # a new turn of the human
        _write_json(_mdir(repo) / "active.json", data)
    current = fingerprint(repo)
    if current is None or current == data.get("base_fingerprint"):
        return 0, ""  # not a git repository, or the code did not change
    result = evaluate(repo, current)
    if result["status"] == PASS:
        return 0, ""
    if result["pending_linked"]:
        failing = result["failed"] + result["invalid"]
        return 0, (f"Magenta: {len(result['pending_linked'])} checks of the task {item} wait for your approval: "
                   f"{', '.join(result['pending_linked'])}. Say \"approve\" to the agent, then confirm the command "
                   "in the dialog of Claude Code."
                   + (f"\nThese checks fail on the current code: {', '.join(failing)}." if failing else ""))
    if result["status"] == "NO CHECKS":
        note = " Some checks wait for the approval of the human." if result["pending"] else ""
        return 0, f"Magenta: the task {item} changed the code, but no approved check exists, so nothing enforces the rules.{note}"
    blocks = (int(data.get("blocks") or 0) if event.get("stop_hook_active") else 0) + 1
    data["blocks"] = blocks
    _write_json(_mdir(repo) / "active.json", data)
    run_cmd = f"{self_command()} run" + (" --set task" if result["full"] else "")
    if result["status"] == "ERROR":
        reason = (f"Magenta: the checks configuration has an error: {result['error']}. "
                  "The owner of the file must fix it: the file name is the role (qa.yaml: QA, project.yaml: Principal).")
    elif result["invalid"]:
        reason = (f"Magenta: these checks or locks changed after the human approved them: {', '.join(result['invalid'])}. "
                  "Restore them, or ask the human to approve the change.")
    elif result["failed"]:
        reason = (f"Magenta: these checks fail on the current code: {', '.join(result['failed'])}. Fix the code through "
                  f"the lead agent. Do not change the checks or the locked tests. Then run: {run_cmd}")
    else:
        reason = (f"Magenta: these checks did not run on the current code: {', '.join(result['not_run'])}. "
                  f"Before you finish, run: {run_cmd}")
    if blocks > MAX_BLOCKS:
        return 0, f"{reason}\nThe agent stopped without a pass. Its report must say that the checks of {item} do not pass."
    return 2, (reason + "\nIf you wait for the human, or the human asked you to stop, say in your answer that the "
               "checks do not pass, and stop.")


def _is_ours(command) -> bool:
    text = str(command or "").rstrip()
    return text.endswith('verify.py" hook') or text.endswith('verify.py" protect')


def _settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise VerifyError(f"{path} is not valid JSON ({exc}). Fix it first.") from exc
    if not isinstance(data, dict):
        raise VerifyError(f"{path} must contain a JSON object")
    return data


def _remove_ours(hooks: dict) -> int:
    removed = 0
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            inner = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(inner, list):
                kept_groups.append(group)
                continue
            kept = [h for h in inner if not (isinstance(h, dict) and _is_ours(h.get("command")))]
            removed += len(inner) - len(kept)
            if kept:
                kept_groups.append(dict(group, hooks=kept))
        if kept_groups:
            hooks[event] = kept_groups
        else:
            del hooks[event]
    return removed


def hook_command(mode: str) -> str:
    """A hook command that does nothing when this script was removed. (Python exits with 2 when the script
    file is missing, and exit code 2 would block Claude Code.)"""
    script = Path(__file__).resolve().as_posix()
    return f'[ ! -f "{script}" ] || {self_command()} {mode}'


def install_rules(repo: Path) -> Path:
    """Add the ask rules to `.claude/settings.local.json`: Claude Code asks the human before approve or --force,
    in every permission mode. The rules do not depend on where Magenta is installed (plugin or user level)."""
    path = repo / SETTINGS
    data = _settings(path)
    permissions = data.get("permissions") if isinstance(data.get("permissions"), dict) else {}
    ask = [r for r in (permissions.get("ask") or []) if isinstance(r, str)]
    permissions["ask"] = ask + [r for r in protect.ASK_RULES if r not in ask]
    data["permissions"] = permissions
    _write_json(path, data)
    git_exclude(repo, SETTINGS.as_posix())
    return path


def _remove_rules(data: dict) -> int:
    permissions = data.get("permissions")
    if not isinstance(permissions, dict) or not isinstance(permissions.get("ask"), list):
        return 0
    kept = [r for r in permissions["ask"] if r not in protect.ASK_RULES]
    removed = len(permissions["ask"]) - len(kept)
    if kept:
        permissions["ask"] = kept
    else:
        permissions.pop("ask")
    if not permissions:
        data.pop("permissions")
    return removed


def install_hook(repo: Path, protect_main: bool = True) -> Path:
    """Add the Stop hook, the protect hook, and the ask rules to `.claude/settings.local.json` of the repository."""
    install_rules(repo)
    path = repo / SETTINGS
    data = _settings(path)
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    _remove_ours(hooks)
    hooks.setdefault("Stop", []).append(
        {"hooks": [{"type": "command", "command": hook_command("hook"), "timeout": HOOK_TIMEOUT}]})
    if protect_main:
        hooks.setdefault("PreToolUse", []).append(
            {"matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit",
             "hooks": [{"type": "command", "command": hook_command("protect"), "timeout": 30}]})
    data["hooks"] = hooks
    _write_json(path, data)
    git_exclude(repo, SETTINGS.as_posix())
    return path


def uninstall_hook(repo: Path) -> int:
    path = repo / SETTINGS
    if not path.exists():
        return 0
    data = _settings(path)
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    removed = _remove_ours(hooks)
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    removed += _remove_rules(data)
    _write_json(path, data)
    return removed


def _in_plugin() -> bool:
    here = Path(__file__).resolve().parent
    return any((p / ".claude-plugin" / "plugin.json").is_file() for p in [here, *list(here.parents)[:4]])


def hook_status(repo: Path) -> str:
    """'plugin', 'installed', or 'missing': is a Stop hook active for this repository?"""
    if _in_plugin():
        return "plugin"
    for path in (repo / SETTINGS, repo / ".claude" / "settings.json", Path.home() / ".claude" / "settings.json"):
        hooks = _read_json(path, {}).get("hooks")
        for group in (hooks.get("Stop") if isinstance(hooks, dict) else None) or []:
            for h in (group.get("hooks") if isinstance(group, dict) else None) or []:
                if isinstance(h, dict) and _is_ours(h.get("command")) and str(h["command"]).rstrip().endswith("hook"):
                    return "installed"
    return "missing"


# ----- command line -----

def _read_event() -> dict:
    try:
        stream = getattr(sys.stdin, "buffer", None)
        raw = stream.read().decode("utf-8", "replace") if stream is not None else sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
        return event if isinstance(event, dict) else {}
    except (ValueError, OSError):
        return {}


def _run_hook(mode: str) -> int:
    if mode == "hook":
        try:
            code, text = hook(_read_event())
        except Exception as exc:  # a broken hook must not trap the session
            code, text = 0, f"Magenta verify hook error: {exc}"
        if code == 2:
            print(text, file=sys.stderr)
        elif text:
            print(json.dumps({"systemMessage": text}))
        return code
    try:
        event = _read_event()
        kind, reason = protect.evaluate(event)
        if kind == "ask":
            reason += approval_details(event)
    except Exception:  # a broken guardrail must not block the session
        kind, reason = "allow", ""
    code, out, err = protect.hook_output(kind, reason)
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code


def approval_details(event: dict, limit: int = 12) -> str:
    """The checks and locks that an approve command approves, for the permission dialog of Claude Code."""
    command = protect.unquoted(str((event.get("tool_input") or {}).get("command") or ""))
    if " approve" not in f" {command}":
        return ""
    words = command.split()
    ids = [w for w in words[words.index("approve") + 1:] if not w.startswith("-")] if "approve" in words else []
    repo = find_repo(Path(event.get("cwd") or os.getcwd()))
    approved = approvals(repo)
    checks = load_checks(repo)
    lines = []
    for c in checks:
        status = check_status(c, approved)
        if (ids and c["id"] in ids) or (not ids and status != "approved"):
            note = " (CHANGED)" if status == "changed" else ""
            lines.append(f"- {c['id']}{note} [{c['set']}]: {c['command']}" + (f" (in {c['cwd']})" if c["cwd"] else ""))
    lines += [f"- {i}: seal the locked tests" for i in ids if i.startswith("lock.")]
    if not ids:
        lines += [f"- lock.{n}: seal the locked tests" for n in _lock_files(repo)]
    if not lines:
        return ""
    more = f"\n... and {len(lines) - limit} more" if len(lines) > limit else ""
    return "\nChecks to approve (each one runs on your computer):\n" + "\n".join(lines[:limit]) + more


def _print_list(repo: Path) -> None:
    data = _approval_data(repo)
    approved, seals = data["approved"], data["locks"]
    checks = load_checks(repo)
    print("| Check | Source | Set | Approval | Work item | Command |")
    print("|---|---|---|---|---|---|")
    for c in checks:
        state = {"approved": "approved", "pending": "WAITS", "changed": "CHANGED"}[check_status(c, approved)]
        cwd = f" (in {c['cwd']})" if c["cwd"] else ""
        print(f"| {c['id']} | {c['source']} | {c['set']} | {state} | {c['work_item'] or '-'} | `{c['command']}`{cwd} |")
    for cid in sorted(set(approved) - {c["id"] for c in checks}):
        print(f"| {cid} | - | - | REMOVED | - | `{approved[cid].get('command', '')}` |")
    files = _lock_files(repo)
    for name in sorted(set(files) | set(seals)):
        if name not in files:
            state = "REMOVED"
        else:
            state = "approved" if seals.get(name) == _file_hash(files[name]) else ("CHANGED" if name in seals else "WAITS")
        count = len(_read_json(files[name], {}).get("files", {})) if name in files else 0
        print(f"| lock.{name} | lock | quick | {state} | {name} | {count} locked test files |")
    if not checks and not approved and not files and not seals:
        print("| (no checks in .magenta/checks/) | | | | | |")


def _print_status(repo: Path) -> None:
    data = active(repo)
    result = evaluate(repo)
    state = _read_json(_mdir(repo) / "verify-state.json", {})
    item = data.get("work_item")
    print(f"Active task: {item or '(none)'}" + (f", session {data.get('session')}" if data.get("session") else ""))
    if not item and data.get("last"):
        print(f"Last task: {data['last']}, finished with {data.get('last_status')}")
    print(f"Stop hook: {hook_status(repo)}")
    print(f"Checks: {len(result['runnable'])} required now, {len(result['pending'])} wait for approval, "
          f"{len(result['invalid'])} changed or removed")
    if state:
        print(f"Last run: {state.get('at')} (set {state.get('set')})")
    print(f"Result for the current code: {result['status']}" + (f" ({result['error']})" if result["error"] else ""))
    for cid in result["failed"] + result["invalid"]:
        print(f"  - failed: {cid}")
    for cid in result["not_run"]:
        print(f"  - did not run on this code: {cid}")
    for cid in result["pending_linked"]:
        print(f"  - waits for approval: {cid}")


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv in (["hook"], ["protect"]):  # hooks never go through argparse: its errors exit with 2 (block)
        return _run_hook(argv[0])
    parser = argparse.ArgumentParser(prog="verify", description="Magenta checks: run, approve, and enforce them",
                                     allow_abbrev=False)
    parser.add_argument("--repo", type=Path, default=None, help="the repository (default: the git root of this folder)")
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--repo", type=Path, default=argparse.SUPPRESS, help="the repository")
    sub = parser.add_subparsers(dest="cmd", parser_class=functools.partial(argparse.ArgumentParser, allow_abbrev=False))
    p_run = sub.add_parser("run", parents=[shared], help="run the approved checks")
    p_run.add_argument("--set", choices=RUN_SETS, default="quick")
    p_run.add_argument("--only", default="", help="comma-separated check ids")
    sub.add_parser("list", parents=[shared], help="show the checks, the locks, and their approval")
    sub.add_parser("status", parents=[shared], help="show the active task and the result for the current code")
    p_app = sub.add_parser("approve", parents=[shared], help="approve checks and seal test locks (human only)")
    p_app.add_argument("ids", nargs="*")
    p_start = sub.add_parser("start", parents=[shared], help="start or resume a task")
    p_start.add_argument("item")
    p_start.add_argument("--session", default="")
    p_start.add_argument("--force", action="store_true", help="replace a failing task (human only)")
    p_finish = sub.add_parser("finish", parents=[shared], help="close the active task")
    p_finish.add_argument("--force", action="store_true", help="close a task with failing checks (human only)")
    p_lock = sub.add_parser("lock", parents=[shared], help="lock the test files of a work item")
    p_lock.add_argument("item")
    p_lock.add_argument("files", nargs="*")
    p_cl = sub.add_parser("check-lock", parents=[shared], help="check the locked test files")
    p_cl.add_argument("item", nargs="?")
    p_ih = sub.add_parser("install-hook", parents=[shared], help="add the Claude Code hooks (human)")
    p_ih.add_argument("--no-protect", action="store_true", help="add only the Stop hook")
    sub.add_parser("uninstall-hook", parents=[shared], help="remove the Claude Code hooks of Magenta (human)")
    sub.add_parser("hook", parents=[shared], help="Claude Code Stop hook (JSON on stdin)")
    sub.add_parser("protect", parents=[shared], help="Claude Code PreToolUse hook (JSON on stdin)")
    args = parser.parse_args(argv)
    cmd = args.cmd or "run"
    if cmd in ("hook", "protect"):
        return _run_hook(cmd)

    repo = (args.repo or find_repo(Path.cwd())).resolve()
    try:
        if cmd == "run":
            only = [x.strip() for x in getattr(args, "only", "").split(",") if x.strip()]
            outcome = run(repo, getattr(args, "set", "quick"), only or None)
            print(summary(outcome))
            return exit_code(outcome)
        if cmd == "list":
            _print_list(repo)
            return 0
        if cmd == "status":
            _print_status(repo)
            return 0
        if cmd == "approve":
            done, pruned, sealed = approve(repo, args.ids)
            if not done and not pruned and not sealed:
                print("Nothing to approve.")
            for c in done:
                print(f"approved {c['id']} ({c['set']}): {c['command']}" + (f" (in {c['cwd']})" if c["cwd"] else ""))
            for cid in pruned:
                print(f"removed {cid}")
            for lid in sealed:
                print(f"sealed {lid}")
            return 0
        if cmd == "start":
            data = start(repo, args.item, args.session, args.force)
            print(f"Task {args.item} {'resumed' if data.get('resumed_at') else 'started'}."
                  + (f" Note: {data['note']}." if data.get("note") else ""))
            if not data.get("session"):
                print("Note: no session id, so the Claude Code Stop hook does not enforce this task.")
            status = hook_status(repo)
            if status == "missing":
                print("Note: the Claude Code Stop hook is not installed for this repository, so nothing stops the "
                      "agent when the checks fail. The human can install it (one time) with:\n"
                      f"  {self_command()} install-hook")
            else:
                print(f"Stop hook: {status}.")
            return 0
        if cmd == "finish":
            data = finish(repo, args.force)
            print(f"Task {data['last'] or '(none)'} finished. Result for the current code: {data['last_status']}.")
            return 0
        if cmd == "lock":
            target = test_lock.lock(repo, args.item, args.files)
            files = json.loads(target.read_text(encoding="utf-8"))["files"]
            print(f"Locked {len(files)} test files in {target.relative_to(repo).as_posix()}:")
            for name in files:
                print(f"  {name}")
            print("The human seals the lock with the approval of the checks (approve).")
            return 0
        if cmd == "check-lock":
            items = [args.item] if args.item else sorted(_lock_files(repo))
            failed = False
            for it in items:
                problems = test_lock.check(repo, it)
                print(f"{it}: {'OK' if not problems else 'CHANGED'}")
                for problem in problems:
                    print(f"  - {problem}")
                failed = failed or bool(problems)
            return 1 if failed else 0
        if cmd == "install-hook":
            path = install_hook(repo, protect_main=not args.no_protect)
            print(f"Installed the Magenta hooks in {path}.")
            print("Restart Claude Code, or open /hooks, to load them.")
            return 0
        if cmd == "uninstall-hook":
            count = uninstall_hook(repo)
            print(f"Removed {count} Magenta hooks from {repo / SETTINGS}." if count else "No Magenta hook found.")
            return 0
    except (VerifyError, test_lock.LockError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
