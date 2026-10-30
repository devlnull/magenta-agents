import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters"))

import verify  # noqa: E402

VERIFY = ROOT / "adapters" / "verify.py"
PY = f'"{Path(sys.executable).as_posix()}"'


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class StateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "test")
        git(self.repo, "config", "commit.gpgsign", "false")
        write(self.repo / "a.txt", "a\n")
        write(self.repo / ".gitignore", "__pycache__/\ngenerated/\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "init")
        verify.git_exclude(self.repo, ".magenta/")

    def tearDown(self):
        self.tmp.cleanup()

    def script(self, name, code):
        write(self.repo / ".magenta" / "t" / f"{name}.py", code)
        return f"{PY} .magenta/t/{name}.py"

    def checks(self, file, items):
        lines = ["checks:"]
        for item in items:
            first = True
            for key, value in item.items():
                lines.append(("  - " if first else "    ") + f"{key}: {json.dumps(value)}")
                first = False
        write(self.repo / ".magenta" / "checks" / file, "\n".join(lines) + "\n")

    def has_b(self):
        return self.script("has_b", "import sys\nsys.exit(0 if 'b' in open('a.txt').read() else 1)\n")

    def approved_has_b(self):
        self.checks("qa.yaml", [{"id": "qa.must-pass", "command": self.has_b()}])
        verify.approve(self.repo, ["qa.must-pass"])

    def approved_ok(self):
        self.checks("qa.yaml", [{"id": "qa.ok", "command": self.script("ok", "pass\n")}])
        verify.approve(self.repo, ["qa.ok"])

    def cli(self, *args):
        return subprocess.run([sys.executable, str(VERIFY), "--repo", str(self.repo), *args], cwd=self.repo,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def hook(self, session):
        """Run the Stop hook. A structured block (exit 0 with {"decision": "block"}) counts as exit code 2,
        because Claude Code blocks the stop in both cases."""
        event = json.dumps({"session_id": session, "cwd": str(self.repo)})
        out = subprocess.run([sys.executable, str(VERIFY), "hook"], input=event, cwd=self.repo,
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            decision = json.loads(out.stdout or "{}")
            if out.returncode == 0 and decision.get("decision") == "block":
                out.returncode, out.stderr = 2, decision.get("reason", "")  # what Claude gets
        except ValueError:
            pass
        return out

    def result(self):
        out = self.cli("status")
        self.assertEqual(out.returncode, 0, out.stderr)
        found = re.search(r"Result for the current code: (.+)", out.stdout)
        self.assertIsNotNone(found, out.stdout)
        return found.group(1).strip()

    def active_line(self):
        out = self.cli("status")
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.splitlines()[0]

    def start(self, item, session, *extra):
        return self.cli("start", item, "--session", session, *extra)

    def failing_task_of_s1(self, run_checks=True):
        self.approved_has_b()
        self.assertEqual(self.start("T1-x", "S1").returncode, 0)
        write(self.repo / "a.txt", "a\nc\n")
        if run_checks:
            self.assertEqual(self.cli("run").returncode, 1)

    def passing_task_of_s1(self):
        self.approved_has_b()
        self.assertEqual(self.start("T1-x", "S1").returncode, 0)
        write(self.repo / "a.txt", "a\nb\n")
        self.assertEqual(self.cli("run").returncode, 0)


class W2ResumeKeepsSessionTest(StateCase):
    def test_another_session_cannot_resume_a_failing_task(self):
        self.failing_task_of_s1()
        out = self.start("T1-x", "S2")
        self.assertNotEqual(out.returncode, 0, out.stdout)
        self.assertEqual(self.active_line(), "Active task: T1-x, session S1")
        self.assertEqual(self.hook("S1").returncode, 2)

    def test_another_session_cannot_resume_a_changed_task_that_did_not_run(self):
        self.failing_task_of_s1(run_checks=False)
        out = self.start("T1-x", "S2")
        self.assertNotEqual(out.returncode, 0, out.stdout)
        self.assertEqual(self.active_line(), "Active task: T1-x, session S1")
        self.assertEqual(self.hook("S1").returncode, 2)

    def test_the_human_can_force_the_resume(self):
        self.failing_task_of_s1()
        out = self.start("T1-x", "S2", "--force")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.active_line(), "Active task: T1-x, session S2")


class W2ReplaceKeepsFailingTaskTest(StateCase):
    def test_another_session_cannot_replace_a_failing_task(self):
        self.failing_task_of_s1()
        out = self.start("T2-y", "S2")
        self.assertNotEqual(out.returncode, 0, out.stdout)
        self.assertEqual(self.active_line(), "Active task: T1-x, session S1")
        self.assertEqual(self.hook("S1").returncode, 2)

    def test_another_session_cannot_replace_a_changed_task_that_did_not_run(self):
        self.failing_task_of_s1(run_checks=False)
        out = self.start("T2-y", "S2")
        self.assertNotEqual(out.returncode, 0, out.stdout)
        self.assertEqual(self.active_line(), "Active task: T1-x, session S1")
        self.assertEqual(self.hook("S1").returncode, 2)

    def test_the_human_can_force_the_replacement(self):
        self.failing_task_of_s1()
        out = self.start("T2-y", "S2", "--force")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.active_line(), "Active task: T2-y, session S2")


class W2StillWorksTest(StateCase):
    def test_the_same_session_resumes_a_failing_task_and_keeps_the_base(self):
        self.failing_task_of_s1()
        out = self.start("T1-x", "S1")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Task T1-x resumed.", out.stdout)
        self.assertEqual(self.active_line(), "Active task: T1-x, session S1")
        self.assertEqual(self.hook("S1").returncode, 2)

    def test_another_session_replaces_an_unchanged_task(self):
        self.approved_has_b()
        self.assertEqual(self.start("T1-x", "S1").returncode, 0)
        out = self.start("T2-y", "S2")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.active_line(), "Active task: T2-y, session S2")

    def test_another_session_resumes_an_unchanged_task(self):
        self.approved_has_b()
        self.assertEqual(self.start("T1-x", "S1").returncode, 0)
        out = self.start("T1-x", "S2")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.active_line(), "Active task: T1-x, session S2")

    def test_the_same_session_replaces_a_passing_task(self):
        self.passing_task_of_s1()
        out = self.start("T2-y", "S1")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.active_line(), "Active task: T2-y, session S1")

    def test_another_session_replaces_a_passing_task(self):
        self.passing_task_of_s1()
        out = self.start("T2-y", "S2")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.active_line(), "Active task: T2-y, session S2")

    def test_another_session_resumes_a_passing_task(self):
        self.passing_task_of_s1()
        out = self.start("T1-x", "S2")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.active_line(), "Active task: T1-x, session S2")


class W3AssumeUnchangedTest(StateCase):
    def setUp(self):
        super().setUp()
        self.approved_ok()
        self.assertEqual(self.start("T1-x", "S1").returncode, 0)
        self.assertEqual(self.cli("run").returncode, 0)
        self.assertEqual(self.result(), "PASS")

    def check_hidden_change(self, flag):
        git(self.repo, "update-index", flag, "a.txt")
        write(self.repo / "a.txt", "a\nhidden change\n")
        self.assertEqual(self.result(), "NOT VERIFIED")
        self.assertEqual(self.hook("S1").returncode, 2)

    def test_a_change_to_an_assume_unchanged_file_counts(self):
        self.check_hidden_change("--assume-unchanged")

    def test_a_change_to_a_skip_worktree_file_counts(self):
        self.check_hidden_change("--skip-worktree")


class W3NestedOutputFolderTest(StateCase):
    FOLDERS = ("bin", "out", "build", "target", "dist", "coverage", "obj")

    def setUp(self):
        super().setUp()
        self.approved_ok()
        self.assertEqual(self.cli("run").returncode, 0)
        self.assertEqual(self.result(), "PASS")

    def test_a_new_source_file_in_a_nested_folder_counts(self):
        for name in self.FOLDERS:
            with self.subTest(folder=name):
                try:
                    write(self.repo / "src" / name / "tool.py", "print('new')\n")
                    self.assertEqual(self.result(), "NOT VERIFIED")
                finally:
                    shutil.rmtree(self.repo / "src", ignore_errors=True)
                self.assertEqual(self.result(), "PASS")

    def test_untracked_output_folders_at_the_root_do_not_count(self):
        for name in self.FOLDERS:
            write(self.repo / name / "tool.py", "print('output')\n")
        self.assertEqual(self.result(), "PASS")

    def test_ignored_nested_folders_do_not_count(self):
        write(self.repo / "src" / "generated" / "tool.py", "print('ignored')\n")
        self.assertEqual(self.result(), "PASS")


class W3NonUtf8ChecksFileTest(StateCase):
    def broken_checks_file(self):
        path = self.repo / ".magenta" / "checks" / "architect.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"checks:\n  - id: arch.x\n    command: \xff\xfe broken\n")

    def test_run_exits_with_a_configuration_error(self):
        self.approved_ok()
        self.broken_checks_file()
        out = self.cli("run")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("architect.yaml", out.stderr)
        self.assertNotIn("Traceback", out.stderr)

    def test_the_stop_hook_blocks_with_a_configuration_error(self):
        self.approved_ok()
        self.assertEqual(self.start("T1-x", "S1").returncode, 0)
        write(self.repo / "a.txt", "a\nchanged\n")
        self.broken_checks_file()
        out = self.hook("S1")
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("configuration has an error", out.stderr)
        self.assertIn("architect.yaml", out.stderr)


class W3PendingCheckNamesFailuresTest(StateCase):
    def test_the_hook_names_the_failed_checks_while_a_task_check_waits(self):
        self.checks("qa.yaml", [{"id": "qa.must-pass", "command": self.has_b()},
                                {"id": "qa.waits", "command": self.script("ok", "pass\n"), "work_item": "T1-x"}])
        verify.approve(self.repo, ["qa.must-pass"])
        self.assertEqual(self.start("T1-x", "S1").returncode, 0)
        write(self.repo / "a.txt", "a\nc\n")
        self.assertEqual(self.cli("run").returncode, 1)
        out = self.hook("S1")
        text = out.stdout + out.stderr
        self.assertIn("qa.must-pass", text)
        self.assertIn("qa.waits", text)


if __name__ == "__main__":
    unittest.main()
