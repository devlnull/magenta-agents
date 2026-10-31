"""Sessions that start in a parent folder of the repository (a workspace with many repositories).

Claude Code can start in a folder that holds many repositories. The write rules of the agents are relative to the
repository of the file, and the hooks and the verify commands find the repository of the active task.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))

import guard  # noqa: E402
import protect  # noqa: E402
import source  # noqa: E402
import verify  # noqa: E402

VERIFY = ROOT / "adapters" / "verify.py"
PY = f'"{Path(sys.executable).as_posix()}"'


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "test")
    git(path, "config", "commit.gpgsign", "false")
    write(path / "a.txt", "a\n")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "init")
    verify.git_exclude(path, ".magenta/")
    return path


class WorkspaceCase(unittest.TestCase):
    """workspace/ (not a repository) holds group/app (a Magenta repository) and other (a repository)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.home = base / "home"
        self.old_home = os.environ.get("MAGENTA_HOME")
        os.environ["MAGENTA_HOME"] = str(self.home)
        self.ws = base / "workspace"
        self.app = make_repo(self.ws / "group" / "app")
        self.other = make_repo(self.ws / "other")
        (self.app / ".magenta" / "checks").mkdir(parents=True)

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("MAGENTA_HOME", None)
        else:
            os.environ["MAGENTA_HOME"] = self.old_home
        self.tmp.cleanup()

    def failing_task(self, repo, item="T1-x", session="S1"):
        script = repo / ".magenta" / "t" / "has_b.py"
        write(script, "import sys\nsys.exit(0 if 'b' in open('a.txt').read() else 1)\n")
        write(repo / ".magenta" / "checks" / "qa.yaml",
              f"checks:\n  - id: qa.b\n    command: {json.dumps(PY + ' .magenta/t/has_b.py')}\n")
        verify.approve(repo, [])
        verify.start(repo, item, session=session)
        write(repo / "a.txt", "a\nc\n")

    def cli(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(VERIFY), *args], cwd=cwd or self.ws, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")


class GuardTest(WorkspaceCase):
    @classmethod
    def setUpClass(cls):
        cfg = source.load_config(ROOT)
        agents = source.load_agents(ROOT, cfg["agents_enabled"])
        cls.policies = {a: source.policy(a, agents[a]) for a in agents}

    def decide(self, agent, path, cwd=None, tool="Write"):
        event = {"tool_name": tool, "tool_input": {"file_path": str(path)}, "cwd": str(cwd or self.ws)}
        return guard.decide(agent, self.policies[agent], event)

    def shell(self, agent, command, cwd=None):
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd or self.ws)}
        return guard.decide(agent, self.policies[agent], event)

    def test_the_rules_are_relative_to_the_repository_of_the_file(self):
        self.assertIsNone(self.decide("principal", self.app / ".magenta" / "checks" / "project.yaml"))
        self.assertIsNone(self.decide("principal", "group/app/.magenta/checks/project.yaml"))  # relative path
        self.assertIn("cannot write src/App.java", self.decide("principal", self.app / "src" / "App.java"))
        self.assertIsNone(self.decide("engineer", self.app / "src" / "App.java"))

    def test_the_human_only_files_stay_protected(self):
        for name in (".magenta/checks.lock", ".magenta/active.json", ".claude/settings.json", ".git/config"):
            with self.subTest(name=name):
                self.assertIn("Only the human", self.decide("engineer", self.app / name))

    def test_secrets_and_files_outside_the_session_folder_stay_blocked(self):
        self.assertIn("secret", self.decide("engineer", self.app / ".env"))
        self.assertIn("outside the project", self.decide("engineer", self.ws.parent / "x.txt"))
        self.assertIn("outside the project", self.decide("engineer", self.app / "src" / "App.java", cwd=self.other))

    def test_the_project_policy_of_the_repository_applies(self):
        write(self.app / ".magenta" / "policy.json", json.dumps({"principal": {"writes": ["docs/**"]}}))
        self.assertIsNone(self.decide("principal", self.app / "docs" / "notes.md"))
        self.assertIsNotNone(self.decide("principal", self.other / "docs" / "notes.md"))

    def test_a_session_in_the_repository_works_as_before(self):
        self.assertIsNone(self.decide("principal", self.app / ".magenta" / "checks" / "project.yaml", cwd=self.app))
        self.assertIsNotNone(self.decide("principal", self.app / "src" / "App.java", cwd=self.app))
        nested = make_repo(self.app / "lib" / "nested")  # a repository in the repository: the session root counts
        self.assertIsNotNone(self.decide("principal", nested / ".magenta" / "checks" / "project.yaml", cwd=self.app))

    def test_git_dash_c_with_a_folder_in_the_session_folder(self):
        self.assertIsNone(self.shell("qa", "git -C group/app diff"))
        self.assertIsNone(self.shell("qa", f"git -C {self.app.as_posix()} status"))
        self.assertIsNotNone(self.shell("qa", f"git -C {self.ws.parent.as_posix()} diff"))  # outside the session folder
        self.assertIsNotNone(self.shell("qa", "git -C group/app diff --output=x.patch"))  # writes a file
        self.assertIsNotNone(self.shell("qa", "git -C group/app push"))  # not in the allowed commands


class ProtectTest(WorkspaceCase):
    def decide(self, command):
        return protect.decide({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.ws)})

    def test_the_magenta_folder_of_a_repository_below_is_protected(self):
        self.assertIsNotNone(self.decide("rm -rf group/app/.magenta"))
        self.assertIsNotNone(self.decide(f"rm -rf {self.app.as_posix()}/.magenta/work"))
        self.assertIsNotNone(self.decide("git -C group/app clean -xfd"))
        self.assertIsNone(self.decide("rm -rf other/build"))
        self.assertIsNone(self.decide("git -C other clean -xfd"))  # no .magenta/ there


class HookTest(WorkspaceCase):
    def test_the_stop_hook_finds_the_repository_of_the_task(self):
        self.failing_task(self.app)
        code, reason = verify.hook({"session_id": "S1", "cwd": str(self.ws)})
        self.assertEqual(code, 2)
        self.assertIn("qa.b", reason)
        self.assertEqual(verify.hook({"session_id": "S2", "cwd": str(self.ws)}), (0, ""))  # another session
        self.assertFalse((self.ws / ".magenta").exists())

    def test_subagents_of_the_session_are_recorded_in_the_repository_of_the_task(self):
        self.failing_task(self.app)
        event = {"hook_event_name": "SubagentStart", "session_id": "S1", "cwd": str(self.ws), "agent_id": "a1",
                 "agent_type": "magenta:engineer"}
        verify.subagent_start(event)
        self.assertEqual(len(verify.running_agents(self.app, "S1")), 1)
        code, _ = verify.subagent_stop(dict(event, hook_event_name="SubagentStop"))
        self.assertEqual(code, 2)  # the engineer changed the code, and the checks do not pass

    def test_finish_forgets_the_session(self):
        self.failing_task(self.app)
        write(self.app / "a.txt", "a\nb\n")
        verify.run(self.app, "task")
        verify.finish(self.app)
        self.assertFalse(verify._session_file("S1").exists())
        self.assertEqual(verify.hook({"session_id": "S1", "cwd": str(self.ws)}), (0, ""))

    def test_a_record_for_a_task_of_another_session_is_ignored(self):
        self.failing_task(self.app, session="S1")
        verify.start(self.app, "T1-x", session="S2", force=True)  # S2 took the task over
        self.assertEqual(verify.event_repo({"session_id": "S1", "cwd": str(self.ws)}), self.ws)

    def test_the_approval_dialog_reads_the_repo_option(self):
        write(self.app / ".magenta" / "checks" / "qa.yaml", "checks:\n  - id: qa.one\n    command: \"true\"\n")
        command = f'"python3" "/x/verify.py" approve --repo {self.app.as_posix()} qa.one'
        details = verify.approval_details({"tool_input": {"command": command}, "cwd": str(self.ws)})
        self.assertIn("qa.one", details)
        command = f'"python3" "/x/verify.py" approve --repo={self.app.as_posix()}'  # no ids: all checks that wait
        details = verify.approval_details({"tool_input": {"command": command}, "cwd": str(self.ws)})
        self.assertIn("qa.one", details)


class CommandTest(WorkspaceCase):
    def test_commands_without_repo_use_the_one_active_task_below(self):
        self.failing_task(self.app)
        out = self.cli("status")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("T1-x", out.stdout)
        self.assertEqual(self.cli("run", "--set", "task").returncode, 1)  # the check fails in group/app
        self.assertFalse((self.ws / ".magenta").exists())

    def test_two_active_tasks_need_the_repo_option(self):
        self.failing_task(self.app)
        (self.other / ".magenta").mkdir()
        verify.start(self.other, "T2-y", session="S9")
        out = self.cli("status")
        self.assertEqual(out.returncode, 2)
        self.assertIn("--repo", out.stderr)
        self.assertIn("group/app", out.stderr)
        out = self.cli("status", "--repo", str(self.other))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("T2-y", out.stdout)

    def test_start_with_the_repo_option_after_the_command(self):
        out = self.cli("start", "--repo", str(self.app), "T3-z", "--session", "S3")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(verify.active(self.app)["work_item"], "T3-z")
        record = json.loads(verify._session_file("S3").read_text(encoding="utf-8"))
        self.assertEqual(Path(record["repo"]), self.app)

    def test_a_repository_session_does_not_look_below(self):
        self.failing_task(self.app)
        out = self.cli("status", cwd=self.other)  # a git repository without .magenta/: it is the repository
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("T1-x", out.stdout)

    def test_the_search_skips_dependencies_and_hidden_folders(self):
        (self.ws / "node_modules" / "pkg" / ".magenta").mkdir(parents=True)
        (self.ws / ".cache" / "x" / ".magenta").mkdir(parents=True)
        self.assertEqual(verify.repos_below(self.ws), [self.app])


if __name__ == "__main__":
    unittest.main()
