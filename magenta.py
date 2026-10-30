#!/usr/bin/env python3
"""Magenta CLI: validate the source, build and install the Claude Code agents, prepare a repository.

  python3 magenta.py validate
  python3 magenta.py build
  python3 magenta.py install [--force]
  python3 magenta.py uninstall
  python3 magenta.py init <path-to-product-repository>
  python3 magenta.py lock <repo> <work-item>        (human, after reviewing the acceptance tests)
  python3 magenta.py check-lock <repo> <work-item>  (QA, CI, or a pre-commit hook)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "adapters"))
sys.path.insert(0, str(ROOT / "runner"))

import agents_md  # noqa: E402
import claude_code  # noqa: E402
import codex  # noqa: E402
import gemini  # noqa: E402
import metrics as team_metrics  # noqa: E402
import opencode  # noqa: E402
import plugin as team_plugin  # noqa: E402
import runner as headless  # noqa: E402
import lock as test_lock  # noqa: E402
from common import YamlError, split_front_matter  # noqa: E402

DIST_ROOT = Path(os.environ.get("MAGENTA_DIST") or ROOT / "dist")
DIST = DIST_ROOT / "claude-code"
TARGETS = ("claude-code", "opencode", "codex", "gemini")
REQUIRED_MAGENTA_KEYS = ("title", "role_type", "model_profile", "tools", "writes", "denies")
REQUIRED_SECTIONS = ("## Mission", "## Procedure", "## Done when", "## Do not", "## Output contract")
ROLE_TYPES = {"lead", "advisor", "reviewer", "maker"}


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        cfg = claude_code.load_config(root)
    except (OSError, YamlError) as exc:
        return [f"config: {exc}"]
    prefix = cfg["prefix"]
    skills = set(claude_code.skill_names(root))
    if "magenta" not in skills:
        errors.append("skills/magenta: the conductor skill (/magenta) is missing")
    if not (root / "workflows" / "routing.md").exists():
        errors.append("workflows/routing.md: the routing table of the conductor is missing")
    known_skills = skills | {f"{prefix}{s}" for s in claude_code.GENERATED_SKILLS}
    owners: dict[str, str] = {}

    for name in sorted(skills):
        try:
            meta, _ = split_front_matter((root / "skills" / name / "SKILL.md").read_text(encoding="utf-8"))
        except YamlError as exc:
            errors.append(f"skills/{name}: {exc}")
            continue
        if meta.get("name") != name:
            errors.append(f"skills/{name}: the front matter name must be {name!r}")
        if not meta.get("description"):
            errors.append(f"skills/{name}: the description is missing")

    for agent_id in cfg.get("agents_enabled") or []:
        path = root / "agents" / f"{agent_id}.md"
        if not path.exists():
            errors.append(f"agents/{agent_id}.md: the file does not exist")
            continue
        try:
            meta, body = split_front_matter(path.read_text(encoding="utf-8"))
        except YamlError as exc:
            errors.append(f"agents/{agent_id}.md: {exc}")
            continue
        where = f"agents/{agent_id}.md"
        if meta.get("name") != agent_id:
            errors.append(f"{where}: the front matter name must be {agent_id!r}")
        if not meta.get("description"):
            errors.append(f"{where}: the description is missing")
        mg = meta.get("magenta") or {}
        for key in REQUIRED_MAGENTA_KEYS:
            if key not in mg:
                errors.append(f"{where}: magenta.{key} is missing")
        if mg.get("role_type") not in ROLE_TYPES:
            errors.append(f"{where}: magenta.role_type must be one of {sorted(ROLE_TYPES)}")
        profile = cfg["profiles"].get(mg.get("model_profile"))
        if not profile or "claude-code" not in profile:
            errors.append(f"{where}: model profile {mg.get('model_profile')!r} has no claude-code mapping in models.yaml")
        for tool in mg.get("tools") or []:
            if tool not in claude_code.TOOL_MAP:
                errors.append(f"{where}: unknown tool {tool!r}")
        if (mg.get("shell") or mg.get("shell_deny")) and "shell" not in (mg.get("tools") or []):
            errors.append(f"{where}: magenta.shell is set, but the tool 'shell' is missing")
        for skill in meta.get("skills") or []:
            if skill not in known_skills:
                errors.append(f"{where}: unknown skill {skill!r}")
        for section in REQUIRED_SECTIONS:
            if section not in body:
                errors.append(f"{where}: the section {section!r} is missing")
        for glob in mg.get("writes") or []:
            if mg.get("role_type") == "maker":
                continue  # makers share production code; the plan gives each task one scope
            if glob.startswith("!") or glob in ("**", "*"):
                if glob in ("**", "*"):
                    errors.append(f"{where}: only maker agents can write {glob!r}")
                continue
            if glob in owners:
                errors.append(f"{where}: {glob!r} also belongs to {owners[glob]} (one writer for each file)")
            owners[glob] = agent_id

    texts = list((root / "agents").glob("*.md")) + list((root / "rules").glob("*.md")) \
        + list((root / "workflows").glob("*.md")) + list((root / "skills").glob("*/SKILL.md"))
    for path in texts:
        for ref in re.findall(r"skill `([a-z0-9-]+)`", path.read_text(encoding="utf-8")):
            if ref not in known_skills:
                errors.append(f"{path.relative_to(root)}: reference to an unknown skill {ref!r}")
    return errors


def init_repo(repo: Path) -> list[str]:
    if not repo.is_dir():
        raise SystemExit(f"error: {repo} is not a folder")
    base = repo / ".magenta"
    (base / "work").mkdir(parents=True, exist_ok=True)
    created = []
    files = {
        "project-context.md": (ROOT / "templates" / "project-context.md").read_text(encoding="utf-8"),
        "product-context.md": (ROOT / "templates" / "product-context.md").read_text(encoding="utf-8"),
        "lessons.md": "# Lessons\n\nThe Principal adds stable lessons from retrospectives here.\n",
        "work/.gitkeep": "",
    }
    for rel, text in files.items():
        path = base / rel
        if not path.exists():
            path.write_text(text, encoding="utf-8")
            created.append(str(path))
    exclude = repo / ".git" / "info" / "exclude"
    if (repo / ".git").is_dir():
        exclude.parent.mkdir(parents=True, exist_ok=True)
        current = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        if ".magenta/" not in current.split():
            with exclude.open("a", encoding="utf-8") as f:
                f.write(("" if current.endswith("\n") or not current else "\n") + ".magenta/\n")
            created.append(f"{exclude} (+ .magenta/)")
    return created


def run_workflow(args) -> int:
    run = headless.Run(ROOT, args.repo.resolve(), args.workflow, budget_usd=args.budget_usd,
                       max_turns=args.max_turns, engine_override=args.engine, dry_run=args.dry_run)
    try:
        if args.workflow == "prd-review":
            if not args.prd:
                print("error: prd-review needs --prd <file>")
                return 1
            result = headless.prd_review(run, args.prd.resolve(), args.id)
        else:
            result = headless.pr_review(run, args.base, args.item)
    except headless.RunError as exc:
        print(f"error: {exc}")
        return 1
    report = result.get("report", "")
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)
    print()
    print(headless.summary(run))
    if result["status"] != "OK":
        print(f"status: {result['status']}")
        return 1
    if args.fail_on_blocker and re.search(r"\|\s*BLOCKER\s*\|", report):
        return 3
    return 0


def check_plugin() -> list[str]:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        team_plugin.build(ROOT, fresh)
        problems = []
        for top in (".claude-plugin", "plugins"):
            new = {p.relative_to(fresh).as_posix(): p for p in (fresh / top).rglob("*") if p.is_file()}
            old = {p.relative_to(ROOT).as_posix(): p for p in (ROOT / top).rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts}
            problems += [f"missing: {k}" for k in sorted(set(new) - set(old))]
            problems += [f"extra: {k}" for k in sorted(set(old) - set(new))]
            problems += [f"changed: {k}" for k in sorted(set(new) & set(old))
                         if new[k].read_bytes().replace(b"\r\n", b"\n") != old[k].read_bytes().replace(b"\r\n", b"\n")]
        return problems


def _extra_builds():
    """The team plugin and marketplace (phase 5)."""
    def build_plugin():
        result = team_plugin.build(ROOT, ROOT)
        return (f"plugin:      magenta {result['version']}: {len(result['agents'])} agents, "
                f"{len(result['skills'])} skills -> plugins/magenta/ and .claude-plugin/marketplace.json")
    return [("plugin", build_plugin)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Magenta agents CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", help="check the canonical source")
    sub.add_parser("build", help="generate dist/claude-code")
    p_install = sub.add_parser("install", help="install into ~/.claude (user level)")
    p_install.add_argument("--force", action="store_true", help="replace files that Magenta did not generate")
    p_install.add_argument("--target", choices=TARGETS, default="claude-code", help="the AI tool (default: claude-code)")
    p_install.add_argument("--python", help="the Python that runs the guard hook (default: this Python)")
    sub.add_parser("check", help="fail if the committed plugin (plugins/, .claude-plugin/) is not current")
    p_install.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    p_uninstall = sub.add_parser("uninstall", help="remove the installed Magenta files")
    p_uninstall.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    p_init = sub.add_parser("init", help="prepare a product repository (.magenta/)")
    p_init.add_argument("repo", type=Path)
    p_lock = sub.add_parser("lock", help="lock the acceptance tests of a work item (human only)")
    p_lock.add_argument("repo", type=Path)
    p_lock.add_argument("item", help="work item ID or folder name")
    p_run = sub.add_parser("run", help="run a headless workflow (prd-review, pr-review)")
    p_run.add_argument("workflow", choices=("prd-review", "pr-review"))
    p_run.add_argument("--repo", type=Path, default=Path.cwd())
    p_run.add_argument("--prd", type=Path, help="prd-review: the PRD file")
    p_run.add_argument("--id", help="prd-review: the work item ID")
    p_run.add_argument("--base", default="origin/main", help="pr-review: the base branch or commit")
    p_run.add_argument("--item", help="pr-review: the related work item ID")
    p_run.add_argument("--budget-usd", type=float, help="stop when the cost reaches this budget")
    p_run.add_argument("--max-turns", type=int, default=40)
    p_run.add_argument("--engine", help="use this engine for all agents (an entry of engines in models.yaml)")
    p_run.add_argument("--output", type=Path, help="write the report to this file")
    p_run.add_argument("--fail-on-blocker", action="store_true", help="pr-review: exit 3 if the report has a BLOCKER")
    p_run.add_argument("--dry-run", action="store_true", help="show the steps; do not call a model")
    p_metrics = sub.add_parser("metrics", help="report work items and headless runs of repositories")
    p_metrics.add_argument("repos", type=Path, nargs="+")
    p_metrics.add_argument("--output", type=Path)
    p_check = sub.add_parser("check-lock", help="fail if the locked acceptance tests changed")
    p_check.add_argument("repo", type=Path)
    p_check.add_argument("item", help="work item ID or folder name")
    args = parser.parse_args(argv)

    if args.cmd in ("validate", "build"):
        errors = validate()
        if errors:
            print("Validation failed:")
            for e in errors:
                print(f"  - {e}")
            return 1
        if args.cmd == "validate":
            print("Validation passed.")
            return 0
        result = claude_code.build(ROOT, DIST)
        print(f"claude-code: {len(result['agents'])} agents, {len(result['skills'])} skills -> dist/claude-code/")
        oc = opencode.build(ROOT, DIST_ROOT / "opencode")
        print(f"opencode:    {len(oc['agents'])} agents, {len(oc['skills'])} skills -> dist/opencode/")
        if oc["agents_without_model"]:
            print("             note: no 'opencode' model in models.yaml for: "
                  + ", ".join(oc["agents_without_model"]) + " (they use the session model)")
        cx = codex.build(ROOT, DIST_ROOT / "codex")
        print(f"codex:       {len(cx['agents'])} agents, {len(cx['skills'])} skills -> dist/codex/")
        gm = gemini.build(ROOT, DIST_ROOT / "gemini")
        print(f"gemini:      {len(gm['agents'])} agents, {len(gm['skills'])} skills, /magenta -> dist/gemini/")
        am = agents_md.build(ROOT, DIST_ROOT / "agents-md")
        print(f"agents-md:   {len(am['skills'])} skills and AGENTS.md (tools without subagents) -> dist/agents-md/")
        for name, fn in _extra_builds():
            print(fn())
        return 0
    if args.cmd == "install":
        try:
            if args.target == "claude-code":
                installed = claude_code.install(DIST, args.home, force=args.force, python=args.python)
                hint = 'cd <repo> && claude, then: /magenta <task>'
            elif args.target == "opencode":
                installed = opencode.install(DIST_ROOT / "opencode", args.home, force=args.force)
                hint = 'cd <repo> && opencode, then: /magenta <task>'
            elif args.target == "codex":
                installed = codex.install(DIST_ROOT / "codex", args.home, force=args.force)
                hint = 'cd <repo> && codex, then: $magenta <task>'
            else:
                installed = gemini.install(DIST_ROOT / "gemini", args.home, force=args.force)
                hint = 'cd <repo> && gemini, then: /magenta <task>'
        except claude_code.BuildError as exc:
            print(f"error: {exc}")
            return 1
        print(f"Installed {len(installed)} items for {args.target}.")
        print(f"Start: {hint}")
        return 0
    if args.cmd == "uninstall":
        removed = claude_code.uninstall(args.home)
        codex.uninstall(args.home)
        print(f"Removed {len(removed)} items." if removed else "Nothing to remove.")
        return 0
    if args.cmd == "check":
        problems = check_plugin()
        if problems:
            print("The committed plugin is not current. Run: python3 magenta.py build")
            for problem in problems[:20]:
                print(f"  - {problem}")
            return 1
        print("The committed plugin is current.")
        return 0
    if args.cmd == "metrics":
        text = team_metrics.report(team_metrics.collect([r.resolve() for r in args.repos]))
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        print(text)
        return 0
    if args.cmd == "run":
        return run_workflow(args)
    if args.cmd == "lock":
        try:
            target = test_lock.lock(args.repo.resolve(), args.item)
        except test_lock.LockError as exc:
            print(f"error: {exc}")
            return 1
        files = json.loads(target.read_text(encoding="utf-8"))["files"]
        print(f"Locked {len(files)} acceptance test files in {target}")
        return 0
    if args.cmd == "check-lock":
        try:
            problems = test_lock.check(args.repo.resolve(), args.item)
        except test_lock.LockError as exc:
            print(f"error: {exc}")
            return 1
        if problems:
            print("The acceptance tests changed after the lock:")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print("The acceptance tests agree with the lock.")
        return 0
    if args.cmd == "init":
        created = init_repo(args.repo.resolve())
        for c in created:
            print(f"created {c}")
        print("Next: cd into the repository, run `claude --agent magenta-principal`, and ask it to run discover-project.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
