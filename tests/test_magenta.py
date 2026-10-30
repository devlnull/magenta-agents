"""Tests for the Magenta CLI, the Claude Code adapter, and the guard hook. Run: python3 -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters"))
sys.path.insert(0, str(ROOT))

import claude_code  # noqa: E402
import source  # noqa: E402
import guard  # noqa: E402
import magenta  # noqa: E402
from common import parse_yaml, path_matches, split_front_matter  # noqa: E402

try:
    import yaml  # optional: used only to cross-check the subset parser
except ImportError:  # pragma: no cover
    yaml = None


class ParserTest(unittest.TestCase):
    def test_subset(self):
        text = """
a: 1
b: "x: y"   # comment
c: [one, "two, three", 3]
d:
  e: >-
    folded
    text
  f:
    - "**/.env*"
    - g: h
      i: [j]
k: {provider: openai-compatible, base_url: "https://llm.internal/v1"}
"""
        self.assertEqual(parse_yaml(text), {
            "a": 1, "b": "x: y", "c": ["one", "two, three", 3],
            "d": {"e": "folded text", "f": ["**/.env*", {"g": "h", "i": ["j"]}]},
            "k": {"provider": "openai-compatible", "base_url": "https://llm.internal/v1"},
        })

    @unittest.skipIf(yaml is None, "PyYAML is not installed")
    def test_matches_pyyaml_on_all_source_files(self):
        files = [ROOT / "magenta.yaml", ROOT / "models.yaml"]
        for path in files:
            self.assertEqual(parse_yaml(path.read_text(encoding="utf-8")), yaml.safe_load(path.read_text(encoding="utf-8")), path)
        for path in list((ROOT / "agents").glob("*.md")) + list((ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            fm = text.split("---\n")[1]
            self.assertEqual(split_front_matter(text)[0], yaml.safe_load(fm), path)


class GlobTest(unittest.TestCase):
    def test_globs(self):
        self.assertTrue(path_matches(".env", ["**/.env*"]))
        self.assertTrue(path_matches("config/.env.local", ["**/.env*"]))
        self.assertTrue(path_matches(".magenta/work/42-x/04-plan.md", [".magenta/work/*/04-plan.md"]))
        self.assertFalse(path_matches(".magenta/work/42-x/sub/04-plan.md", [".magenta/work/*/04-plan.md"]))
        self.assertTrue(path_matches("docs/adr/0005-x.md", ["docs/adr/**"]))
        self.assertFalse(path_matches("src/main/App.java", ["docs/adr/**"]))


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        self.policy = {"writes": [".magenta/work/*/04-plan.md"], "denies": ["**/.env*", "**/secrets/**"],
                       "shell": ["git log*", "git diff*"]}

    def tearDown(self):
        self.tmp.cleanup()

    def ev(self, tool, agent_type=None, **tool_input):
        e = {"tool_name": tool, "tool_input": tool_input, "cwd": str(self.cwd)}
        if agent_type:
            e["agent_type"] = agent_type
        return e

    def decide(self, event):
        return guard.decide("principal", self.policy, event)

    def test_own_write_allowed(self):
        self.assertIsNone(self.decide(self.ev("Write", file_path=".magenta/work/7-a/04-plan.md")))
        self.assertIsNone(self.decide(self.ev("Edit", file_path=str(self.cwd / ".magenta/work/7-a/04-plan.md"))))

    def test_foreign_write_blocked(self):
        self.assertIn("cannot write", self.decide(self.ev("Write", file_path="src/App.java")))
        self.assertIn("cannot write", self.decide(self.ev("Edit", file_path=".magenta/work/7-a/01-prd-review.md")))

    def test_write_outside_project_blocked(self):
        self.assertIn("outside", self.decide(self.ev("Write", file_path="/etc/hosts")))
        self.assertIn("outside", self.decide(self.ev("Write", file_path="../other/04-plan.md")))

    def test_hard_denied_writes(self):
        self.policy["writes"].append("**")
        self.assertIn("Only the human", self.decide(self.ev("Write", file_path=".magenta/policy.json")))
        self.assertIn("Only the human", self.decide(self.ev("Write", file_path=".claude/settings.json")))

    def test_secret_read_blocked(self):
        self.assertIn("secret", self.decide(self.ev("Read", file_path=".env")))
        self.assertIn("secret", self.decide(self.ev("Read", file_path="app/secrets/key.txt")))
        self.assertIsNone(self.decide(self.ev("Read", file_path="src/App.java")))

    def test_shell_allowlist(self):
        self.assertIsNone(self.decide(self.ev("Bash", command="git log --oneline -5")))
        self.assertIn("cannot run", self.decide(self.ev("Bash", command="rm -rf src")))
        self.assertIn("simple command", self.decide(self.ev("Bash", command="git log; rm -rf src")))
        self.assertIn("simple command", self.decide(self.ev("Bash", command="git diff > out.txt")))
        self.assertIn("secret", self.decide(self.ev("Bash", command="git log -p .env")))
        self.assertIn("secret", self.decide(self.ev("Bash", command="git diff ./config/.env.prod")))

    def test_other_magenta_agent_is_not_judged(self):
        e = self.ev("Write", agent_type="magenta-architect", file_path="docs/adr/0001-x.md")
        self.assertIsNone(self.decide(e))

    def test_non_magenta_subagent_inherits_the_policy(self):
        e = self.ev("Write", agent_type="general-purpose", file_path="src/App.java")
        self.assertIn("cannot write", self.decide(e))

    def test_project_policy_extends_writes(self):
        (self.cwd / ".magenta").mkdir()
        (self.cwd / ".magenta" / "policy.json").write_text(json.dumps({"principal": {"writes": ["notes/**"]}}))
        self.assertIsNone(self.decide(self.ev("Write", file_path="notes/a.md")))


class BuildInstallTest(unittest.TestCase):
    def test_validate_passes(self):
        self.assertEqual(magenta.validate(), [])

    def test_build_install_guard_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dist, home, repo = tmp / "dist", tmp / "home", tmp / "repo"
            result = claude_code.build(ROOT, dist)
            self.assertEqual(result["agents"], ["architect", "engineer", "frontend", "principal", "product-manager", "qa"])
            self.assertIn("magenta-workflow", result["skills"])
            self.assertIn("magenta-templates", result["skills"])

            agent = (dist / "agents" / "magenta-qa.md").read_text(encoding="utf-8")
            meta, body = split_front_matter(agent)
            self.assertEqual(meta["name"], "magenta-qa")
            self.assertEqual(meta["model"], "opus")
            self.assertIn("Bash", meta["tools"])
            self.assertNotIn("Agent", meta["tools"])
            self.assertIn(claude_code.GUARD_TOKEN, meta["hooks"]["PreToolUse"][0]["hooks"][0]["command"])
            self.assertIn("# Magenta constitution", body)
            self.assertIn("`magenta-edge-case-hunt`", body)
            self.assertNotIn("skill `edge-case-hunt`", body)

            installed = claude_code.install(dist, home)
            self.assertTrue((home / ".claude/agents/magenta-principal.md").exists())
            self.assertTrue((home / ".claude/skills/magenta-templates/SKILL.md").exists())
            self.assertTrue((home / ".claude/magenta/policies/qa.json").exists())
            installed_meta = split_front_matter((home / ".claude/agents/magenta-qa.md").read_text(encoding="utf-8"))[0]
            command = installed_meta["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
            self.assertNotIn(claude_code.GUARD_TOKEN, command)
            self.assertIn(Path(sys.executable).as_posix(), command)
            self.assertTrue(command.endswith('/.claude/magenta/guard.py" qa'), command)
            # The rendered hook command runs the real guard.
            import shlex
            argv = shlex.split(command)
            event = {"tool_name": "Write", "tool_input": {"file_path": "src/App.java"}, "cwd": str(home)}
            run = subprocess.run(argv, input=json.dumps(event), capture_output=True, text=True)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertTrue(installed)

            # A foreign file with the same name is protected.
            (home / ".claude/agents/magenta-qa.md").write_text("my own agent")
            with self.assertRaises(claude_code.BuildError):
                claude_code.install(dist, home)
            claude_code.install(dist, home, force=True)

            # The installed guard runs as a real hook.
            repo.mkdir()
            event = {"tool_name": "Write", "tool_input": {"file_path": "src/App.java"}, "cwd": str(repo)}
            run = subprocess.run([sys.executable, str(home / ".claude/magenta/guard.py"), "qa"],
                                 input=json.dumps(event), capture_output=True, text=True)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertIn("magenta-qa cannot write src/App.java", run.stderr)
            event["tool_input"]["file_path"] = ".magenta/work/1-x/05-test-plan.md"
            run = subprocess.run([sys.executable, str(home / ".claude/magenta/guard.py"), "qa"],
                                 input=json.dumps(event), capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            run = subprocess.run([sys.executable, str(home / ".claude/magenta/guard.py"), "nobody"],
                                 input=json.dumps(event), capture_output=True, text=True)
            self.assertEqual(run.returncode, 2, "an unknown agent must fail closed")

            removed = claude_code.uninstall(home)
            self.assertTrue(removed)
            self.assertFalse((home / ".claude/agents/magenta-principal.md").exists())
            self.assertFalse((home / ".claude/magenta").exists())

    def test_init_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git" / "info").mkdir(parents=True)
            (repo / ".git" / "info" / "exclude").write_text("# local excludes")
            magenta.init_repo(repo)
            self.assertTrue((repo / ".magenta/project-context.md").exists())
            self.assertIn("Status: DRAFT", (repo / ".magenta/project-context.md").read_text(encoding="utf-8"))
            self.assertTrue((repo / ".magenta/work").is_dir())
            self.assertIn(".magenta/", (repo / ".git/info/exclude").read_text(encoding="utf-8").split())
            magenta.init_repo(repo)  # idempotent
            self.assertEqual((repo / ".git/info/exclude").read_text(encoding="utf-8").count(".magenta/"), 1)


class PackageTest(unittest.TestCase):
    def test_release_assets(self):
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            assets = magenta.package(Path(tmp))
            self.assertEqual([a.name.split("-")[1] for a in assets[:2]], ["agents", "plugin"])
            version = str(magenta.claude_code.load_config(magenta.ROOT)["release"])
            names = zipfile.ZipFile(assets[0]).namelist()
            self.assertIn(f"magenta-agents-{version}/magenta.py", names)
            self.assertIn(f"magenta-agents-{version}/adapters/verify.py", names)
            plugin = zipfile.ZipFile(assets[1]).namelist()
            self.assertIn(f"magenta-plugin-{version}/.claude-plugin/marketplace.json", plugin)
            self.assertEqual(len(assets[2].read_text(encoding="utf-8").splitlines()), 2)
            self.assertTrue((magenta.ROOT / "docs" / "releases" / f"v{version}.md").exists())

if __name__ == "__main__":
    unittest.main()
