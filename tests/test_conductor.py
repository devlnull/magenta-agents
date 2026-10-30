"""Tests for the /magenta conductor and the entry points in Claude Code, OpenCode, Codex CLI, and Gemini CLI."""
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))

import claude_code  # noqa: E402
import codex  # noqa: E402
import gemini  # noqa: E402
import magenta  # noqa: E402
import opencode  # noqa: E402
import plugin  # noqa: E402
from common import split_front_matter  # noqa: E402

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None


def read(path):
    return Path(path).read_text(encoding="utf-8")


class ConductorBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        claude_code.build(ROOT, cls.out / "claude-code")
        opencode.build(ROOT, cls.out / "opencode")
        codex.build(ROOT, cls.out / "codex")
        gemini.build(ROOT, cls.out / "gemini")
        plugin.build(ROOT, cls.out / "plugin")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_claude_conductor_is_slash_magenta(self):
        meta, body = split_front_matter(read(self.out / "claude-code/skills/magenta/SKILL.md"))
        self.assertEqual(meta["name"], "magenta")
        self.assertIn("argument-hint", meta)
        self.assertIn("$ARGUMENTS", body)
        self.assertIn("# Magenta constitution", body)
        self.assertIn("| `magenta-qa` |", body)                 # roster
        self.assertIn("`magenta-engineer`", body)                # rewritten references
        self.assertIn("skill `magenta-workflow`", body)
        self.assertFalse((self.out / "claude-code/skills/magenta-magenta").exists())

    def test_workflow_skill_has_routing_and_playbooks(self):
        body = read(self.out / "claude-code/skills/magenta-workflow/SKILL.md")
        for heading in ("## Routing", "## Playbook: bugfix", "## Playbook: performance", "## Playbook: refactor",
                        "## Playbook: investigation", "## Playbook: incident", "### Constraint ledger"):
            self.assertIn(heading, body)
        self.assertIn("`magenta-architect`", body)
        self.assertNotIn("| `qa`,", body)

    def test_principal_knows_conductor_mode(self):
        body = read(self.out / "claude-code/agents/magenta-principal.md")
        self.assertIn("**Conductor mode.**", body)
        self.assertIn("constraint ledger", body)

    def test_plugin_conductor(self):
        meta, body = split_front_matter(read(self.out / "plugin/plugins/magenta/skills/magenta/SKILL.md"))
        self.assertEqual(meta["name"], "magenta")
        self.assertIn("`magenta:qa`", body)
        self.assertIn("skill `magenta:workflow`", body)

    def test_opencode_command(self):
        text = read(self.out / "opencode/commands/magenta.md")
        self.assertIn("$ARGUMENTS", text)
        self.assertIn("skill `magenta`", text)

    def test_codex_agents(self):
        for path in (self.out / "codex/agents").glob("*.toml"):
            text = read(path)
            if tomllib:
                data = tomllib.loads(text)
            else:
                data = {"name": re.search(r'^name = "(.*)"$', text, re.M).group(1),
                        "developer_instructions": text}
            self.assertTrue(data["name"].startswith("magenta-"))
            self.assertIn("# Write and shell rules", data["developer_instructions"])
        engineer = read(self.out / "codex/agents/magenta-engineer.toml")
        self.assertIn("`!.magenta/**`", engineer)
        self.assertIn("$magenta", read(self.out / "codex/AGENTS.md"))
        self.assertTrue((self.out / "codex/skills/magenta/SKILL.md").exists())

    def test_gemini_agents_and_command(self):
        meta, body = split_front_matter(read(self.out / "gemini/agents/magenta-qa.md"))
        self.assertEqual(meta["name"], "magenta-qa")
        self.assertEqual(meta["kind"], "local")
        self.assertIn("# Write and shell rules", body)
        command = read(self.out / "gemini/commands/magenta.toml")
        self.assertIn("{{args}}", command)
        if tomllib:
            self.assertIn("{{args}}", tomllib.loads(command)["prompt"])

    def test_toml_multiline_escape(self):
        self.assertEqual(codex.toml_multiline("a\\b"), "'''\na\\b'''")
        escaped = codex.toml_multiline("x ''' y \\ z")
        self.assertTrue(escaped.startswith('"""'))
        if tomllib:
            self.assertEqual(tomllib.loads("v = " + escaped)["v"], "x ''' y \\ z")


class InstallTargetsTest(unittest.TestCase):
    def test_install_all_targets_and_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dist, home = tmp / "dist", tmp / "home"
            claude_code.build(ROOT, dist / "claude-code")
            opencode.build(ROOT, dist / "opencode")
            codex.build(ROOT, dist / "codex")
            gemini.build(ROOT, dist / "gemini")
            claude_code.install(dist / "claude-code", home)
            self.assertTrue((home / ".claude/skills/magenta/SKILL.md").exists())
            opencode.install(dist / "opencode", home)
            self.assertTrue((home / ".config/opencode/commands/magenta.md").exists())
            self.assertFalse((home / ".config/opencode/skills/magenta").exists())  # already in ~/.claude/skills
            codex.install(dist / "codex", home)
            self.assertTrue((home / ".codex/agents/magenta-principal.toml").exists())
            self.assertTrue((home / ".agents/skills/magenta/SKILL.md").exists())
            self.assertIn("magenta:begin", read(home / ".codex/AGENTS.md"))
            gemini.install(dist / "gemini", home)
            self.assertTrue((home / ".gemini/agents/magenta-qa.md").exists())
            self.assertTrue((home / ".gemini/commands/magenta.toml").exists())
            removed = claude_code.uninstall(home)
            codex.uninstall(home)
            self.assertTrue(removed)
            for path in (".claude/skills/magenta", ".codex/agents/magenta-qa.toml", ".agents/skills/magenta",
                         ".gemini/agents/magenta-qa.md", ".gemini/commands/magenta.toml",
                         ".config/opencode/commands/magenta.md"):
                self.assertFalse((home / path).exists(), path)
            self.assertNotIn("magenta:begin", read(home / ".codex/AGENTS.md"))

    def test_validate(self):
        self.assertEqual(magenta.validate(), [])


if __name__ == "__main__":
    unittest.main()
