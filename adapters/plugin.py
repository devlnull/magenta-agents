"""Team distribution (phase 5): a Claude Code plugin and a marketplace, committed to the repository.

GitHub users install it with:
  claude plugin marketplace add devlnull/magenta-agents
  claude plugin install magenta@magenta-marketplace

Output (in the repository root, so that GitHub can serve it):
  .claude-plugin/marketplace.json
  plugins/magenta/.claude-plugin/plugin.json
  plugins/magenta/agents/<id>.md        shown as magenta:<id>
  plugins/magenta/skills/<name>/        shown as magenta:<name>
  plugins/magenta/hooks/hooks.json      the guard hook for all sessions (plugin agents ignore agent hooks)
                                        and the verify Stop hook (ADR-0012)
  plugins/magenta/magenta/              guard.sh, py.sh, guard.py, protect.py, verify.py, lock.py, common.py,
                                        policies/
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import claude_code
import source
from source import PLUGIN_NAMING

PLUGIN = "magenta"
MARKETPLACE = "magenta-marketplace"


def build(root: Path, out: Path) -> dict:
    cfg = source.load_config(root)
    agents = source.load_agents(root, cfg.get("agents_enabled") or [])
    plugin = out / "plugins" / PLUGIN
    for old in (out / ".claude-plugin", plugin):
        if old.exists():
            shutil.rmtree(old)
    (out / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / "agents").mkdir()
    (plugin / "skills").mkdir()
    (plugin / "hooks").mkdir()

    version = str(cfg.get("release") or "0.1.0")
    description = "Magenta: role-based AI agents (PM, Architect, Principal, QA, Engineer, Front-End) with gates and guards."
    (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps(
        {"name": PLUGIN, "version": version, "description": description}, indent=2) + "\n", encoding="utf-8")
    owner = cfg.get("owner") or "Magenta maintainers"
    (out / ".claude-plugin" / "marketplace.json").write_text(json.dumps(
        {"name": MARKETPLACE, "description": "Magenta agents for the team", "owner": {"name": owner},
         "plugins": [{"name": PLUGIN, "source": f"./plugins/{PLUGIN}", "description": description}]},
        indent=2) + "\n", encoding="utf-8")

    for agent_id, agent in agents.items():
        text = claude_code.front_matter(agent_id, agent, cfg, PLUGIN_NAMING, guard_command=None) + \
            source.instructions(root, cfg, agents, agent_id, PLUGIN_NAMING)
        (plugin / "agents" / f"{agent_id}.md").write_text(text, encoding="utf-8")
    skills = claude_code.write_skills(root, cfg, PLUGIN_NAMING, plugin / "skills")
    claude_code.copy_guard(plugin / "magenta", root, cfg, agents)
    claude_code.copy_scripts(plugin / "magenta", ("guard.sh", "py.sh", "verify.py", "lock.py"))
    hooks = {"hooks": {
        "PreToolUse": [{"matcher": claude_code.GUARDED_TOOLS, "hooks": [
            {"type": "command", "command": 'sh "${CLAUDE_PLUGIN_ROOT}/magenta/guard.sh" --auto'}]}],
        "Stop": [{"hooks": [
            {"type": "command", "command": 'sh "${CLAUDE_PLUGIN_ROOT}/magenta/py.sh" --fail-open verify.py hook',
             "timeout": 120}]}]}}
    (plugin / "hooks" / "hooks.json").write_text(json.dumps(hooks, indent=2) + "\n", encoding="utf-8")
    return {"agents": sorted(agents), "skills": sorted(skills), "version": version}
