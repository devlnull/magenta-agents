"""AGENTS.md adapter for tools without subagents or hooks (for example Codex CLI).

Each role becomes a skill (`magenta-role-<id>`). A short AGENTS.md block holds the constitution and
the roster, and tells the tool to load the role skill. These tools do not run the guard, so the
rules are instructions only. Use them for the advisor roles; use Claude Code or OpenCode for makers.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import claude_code
import source
from source import MARKER, USER_NAMING, SourceError

BEGIN, END = "<!-- magenta:begin -->", "<!-- magenta:end -->"


def role_skill(root: Path, cfg: dict, agents: dict, agent_id: str) -> str:
    agent = agents[agent_id]
    mg = agent["meta"]["magenta"]
    names = source.all_names(root, cfg)
    writes = "\n".join(f"- `{w}`" for w in mg.get("writes") or [])
    body = (f"# Role: {mg['title']}\n\n"
            "Follow this role when the user asks for it. The Magenta constitution in AGENTS.md applies.\n\n"
            "## Write rules (no guard in this tool: follow them strictly)\n\n"
            "You may write only these paths. A path with `!` is denied. The last matching rule wins.\n\n"
            f"{writes}\n\nDo not run shell commands that change files outside these paths. Do not push.\n\n"
            + source.rewrite_names(agent["body"].strip(), names, USER_NAMING))
    desc = f"Act as the Magenta {mg['title']}. " + source.description(agent)
    return source.skill_file(f"magenta-role-{agent_id}", desc, body)


def agents_md_block(root: Path, cfg: dict, agents: dict) -> str:
    names = source.all_names(root, cfg)
    lines = [BEGIN, f"<!-- {MARKER}. Do not edit this block. -->", "", "# Magenta agents", "",
             "When the user asks for a Magenta role (for example \"as the Magenta architect\"), load the skill "
             "`magenta-role-<role>` and follow it. Roles:", ""]
    for agent_id, agent in agents.items():
        lines.append(f"- `magenta-role-{agent_id}`: {agent['meta']['magenta']['title']}")
    lines += ["", "This tool does not run the Magenta guard. The write rules in each role skill are instructions only.", "",
              source.rewrite_names(source.constitution(root), names, USER_NAMING).strip(), "", END]
    return "\n".join(lines) + "\n"


def build(root: Path, out: Path) -> dict:
    cfg = source.load_config(root)
    agents = source.load_agents(root, cfg.get("agents_enabled") or [])
    if out.exists():
        shutil.rmtree(out)
    (out / "skills").mkdir(parents=True)
    skills = claude_code.write_skills(root, cfg, USER_NAMING, out / "skills")
    for agent_id in agents:
        dst = out / "skills" / f"magenta-role-{agent_id}"
        dst.mkdir()
        (dst / "SKILL.md").write_text(role_skill(root, cfg, agents, agent_id), encoding="utf-8")
        skills.append(dst.name)
    (out / "AGENTS.md").write_text(agents_md_block(root, cfg, agents), encoding="utf-8")
    return {"skills": sorted(skills)}


def merge_block(existing: str, block: str) -> str:
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
    if pattern.search(existing):
        return pattern.sub(lambda _m: block, existing)
    sep = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + sep + block


def remove_block(existing: str) -> str:
    pattern = re.compile(r"\n*" + re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
    return pattern.sub("\n", existing).strip() + "\n" if existing.strip() else ""


def install_codex(dist: Path, home: Path, force: bool = False) -> list[str]:
    if not (dist / "AGENTS.md").exists():
        raise SourceError("dist/agents-md does not exist. Run: python3 magenta.py build")
    codex = home / ".codex"
    plan = [(p, codex / "skills" / p.name) for p in sorted((dist / "skills").iterdir())]
    installed = claude_code._copy_plan(plan, codex / "magenta", None, force)
    agents_md = codex / "AGENTS.md"
    current = agents_md.read_text(encoding="utf-8") if agents_md.exists() else ""
    agents_md.write_text(merge_block(current, (dist / "AGENTS.md").read_text(encoding="utf-8")), encoding="utf-8")
    return installed + [f"{agents_md} (Magenta block)"]


def uninstall_codex(home: Path) -> None:
    agents_md = home / ".codex" / "AGENTS.md"
    if agents_md.exists():
        agents_md.write_text(remove_block(agents_md.read_text(encoding="utf-8")), encoding="utf-8")
