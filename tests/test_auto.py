"""--auto: in a task that the human started with --auto, the hooks allow the tool calls that pass the rules, so
Claude Code does not ask for each one. The conductor approves the checks and uses --force itself; blocked calls stay."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_HOME = tempfile.TemporaryDirectory()
os.environ["MAGENTA_HOME"] = _HOME.name
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))

import guard  # noqa: E402
import source  # noqa: E402
import verify  # noqa: E402
from hooktools import decision  # noqa: E402

GUARD = ROOT / "adapters" / "guard.py"
VERIFY = ROOT / "adapters" / "verify.py"


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


class AutoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()
        git(self.repo, "init", "-q")
        (self.repo / ".magenta").mkdir()
        verify.git_exclude(self.repo, ".magenta/")

    def event(self, tool, session="S1", agent_type=None, **tool_input):
        e = {"tool_name": tool, "tool_input": tool_input, "cwd": str(self.repo), "session_id": session}
        if agent_type:
            e["agent_type"] = agent_type
        return e

    def agent(self, event):
        """The plugin guard for a Magenta agent: deny, allow (auto), or None (the normal flow)."""
        name = guard.agent_id_from_type(event["agent_type"])
        agents = source.load_agents(ROOT, [name])
        policy = source.policy(name, agents[name])
        if guard.decide(name, policy, event):
            return "deny"
        return "allow" if guard.auto_allows(event, name, policy) else None

    def hook(self, event, script=GUARD, mode="--auto"):
        run = subprocess.run([sys.executable, str(script), mode], input=json.dumps(event), capture_output=True,
                             text=True)
        return decision(run)[0]

    def test_start_records_auto_and_finish_ends_it(self):
        out = subprocess.run([sys.executable, str(VERIFY), "--repo", str(self.repo), "start", "T1-x", "--session",
                              "S1", "--auto"], capture_output=True, text=True)
        self.assertIn("(auto)", out.stdout)
        self.assertTrue(verify.auto_session(self.event("Write", file_path="src/a.py")))
        self.assertFalse(verify.auto_session(self.event("Write", session="S2", file_path="src/a.py")))
        verify.finish(self.repo)
        self.assertFalse(verify.auto_session(self.event("Write", file_path="src/a.py")))

    def test_without_auto_the_normal_prompts_stay(self):
        verify.start(self.repo, "T1-x", session="S1")
        self.assertIsNone(self.hook(self.event("Write", file_path="src/a.py")))
        self.assertIsNone(self.agent(self.event("Write", agent_type="magenta:engineer", file_path="src/a.py")))

    def test_auto_allows_the_calls_that_pass_the_rules(self):
        verify.start(self.repo, "T1-x", session="S1", auto=True)
        self.assertEqual(self.hook(self.event("Write", file_path="src/a.py")), "allow")  # the conductor
        self.assertEqual(self.hook(self.event("Bash", command="git status")), "allow")
        self.assertEqual(self.agent(self.event("Write", agent_type="magenta:engineer", file_path="src/a.py")), "allow")
        self.assertEqual(self.agent(self.event("Bash", agent_type="magenta:qa", command="git diff")), "allow")
        self.assertEqual(self.hook(self.event("Read", agent_type="Explore", file_path="src/a.py")), "allow")
        self.assertIsNone(self.hook(self.event("Write", session="S2", file_path="src/a.py")))  # another session

    def test_the_conductor_approves_and_forces_without_a_prompt(self):
        approve = '"python3" "/x/verify.py" approve qa.one'
        force = '"python3" "/x/verify.py" finish --force'
        verify.start(self.repo, "T1-x", session="S1")
        self.assertEqual(self.hook(self.event("Bash", command=approve)), "ask")
        verify.start(self.repo, "T1-x", session="S1", auto=True)
        for script, mode in ((GUARD, "--auto"), (VERIFY, "protect")):
            self.assertEqual(self.hook(self.event("Bash", command=approve), script, mode), "allow")
            self.assertEqual(self.hook(self.event("Bash", command=force), script, mode), "allow")
            bypass = dict(self.event("Bash", command=approve), permission_mode="bypassPermissions")
            self.assertEqual(self.hook(bypass, script, mode), "allow")
            self.assertEqual(self.hook(self.event("Bash", agent_type="Explore", command=approve), script, mode), "ask")
            self.assertEqual(self.hook(self.event("Bash", session="S2", command=approve), script, mode), "ask")
        self.assertEqual(self.agent(self.event("Bash", agent_type="magenta:qa", command=approve)), "deny")

    def test_important_and_blocked_calls_are_not_allowed(self):
        verify.start(self.repo, "T1-x", session="S1", auto=True)
        self.assertIsNone(self.hook(self.event("Bash", command="git push origin main")))  # the normal prompt
        self.assertIsNone(self.hook(self.event("Write", file_path=".magenta/policy.json")))
        self.assertIsNone(self.hook(self.event("Read", file_path="/etc/hosts")))  # outside the project
        self.assertIsNone(self.hook(self.event("Read", file_path=".env")))
        self.assertEqual(self.agent(self.event("Write", agent_type="magenta:engineer",
                                               file_path=".magenta/checks/qa.yaml")), "deny")
        self.assertEqual(self.agent(self.event("Bash", agent_type="magenta:engineer", command="gh pr create")), "deny")

    def test_the_protect_hook_of_a_user_level_install_allows_too(self):
        verify.start(self.repo, "T1-x", session="S1", auto=True)
        self.assertEqual(self.hook(self.event("Write", file_path="src/a.py"), VERIFY, "protect"), "allow")
        self.assertEqual(self.hook(self.event("Write", file_path=".magenta/checks.lock"), VERIFY, "protect"), "deny")


if __name__ == "__main__":
    unittest.main()
