"""Acceptance-test lock (RFC-0001, 6.6): the human locks the QA acceptance tests; a check finds any change.

The lock covers the files in `.magenta/work/<ID>/acceptance/` and the files that match the QA write
patterns in `.magenta/policy.json` (for example `src/acceptanceTest/**`).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from pathlib import Path

from common import path_matches

SKIP_DIRS = {".git", "node_modules", "build", "target", ".gradle", "dist", ".idea", "vendor", "__pycache__", ".venv"}
LOCK_NAME = "acceptance.lock"


class LockError(Exception):
    pass


def find_work_item(repo: Path, item: str) -> Path:
    work = repo / ".magenta" / "work"
    if (work / item).is_dir():
        return work / item
    matches = sorted(p for p in work.glob(f"{item}*") if p.is_dir()) if work.is_dir() else []
    if len(matches) != 1:
        raise LockError(f"work item {item!r} not found or not unique in {work} ({len(matches)} matches)")
    return matches[0]


def patterns(repo: Path, work_item: Path) -> list[str]:
    rel_item = work_item.relative_to(repo).as_posix()
    result = [f"{rel_item}/acceptance/**"]
    try:
        policy = json.loads((repo / ".magenta" / "policy.json").read_text(encoding="utf-8"))
        result += [p for p in policy.get("qa", {}).get("writes", []) if not p.startswith("!")]
    except (OSError, ValueError):
        pass
    return result


def hash_files(repo: Path, globs: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(repo).as_posix()
            if name == LOCK_NAME or not path_matches(rel, globs):
                continue
            found[rel] = hashlib.sha256(full.read_bytes()).hexdigest()
    return dict(sorted(found.items()))


def lock(repo: Path, item: str) -> Path:
    work_item = find_work_item(repo, item)
    globs = patterns(repo, work_item)
    files = hash_files(repo, globs)
    if not files:
        raise LockError(f"no acceptance test files match {globs}. QA must write them first.")
    data = {"locked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "patterns": globs, "files": files}
    target = work_item / LOCK_NAME
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return target


def check(repo: Path, item: str) -> list[str]:
    """Return the differences between the lock and the files now. An empty list means OK."""
    work_item = find_work_item(repo, item)
    target = work_item / LOCK_NAME
    if not target.exists():
        return [f"{target.relative_to(repo)} does not exist. The human must lock the acceptance tests first."]
    data = json.loads(target.read_text(encoding="utf-8"))
    now = hash_files(repo, data.get("patterns", []))
    before = data.get("files", {})
    problems = [f"changed: {p}" for p in before if p in now and now[p] != before[p]]
    problems += [f"removed: {p}" for p in before if p not in now]
    problems += [f"added: {p}" for p in now if p not in before]
    return problems
