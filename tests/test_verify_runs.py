"""Verify: the fingerprint of ignored files, the run folders, the environment of the checks, and pipelines."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_HOME = tempfile.TemporaryDirectory()  # the session records of `start` (never the real home)
os.environ["MAGENTA_HOME"] = _HOME.name
sys.path.insert(0, str(ROOT / "adapters"))

import verify  # noqa: E402

VERIFY = ROOT / "adapters" / "verify.py"
PY = f'"{Path(sys.executable).as_posix()}"'


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class RepoCase(unittest.TestCase):
    """A repository where git ignores tests/Unit/ (local-only tests in .git/info/exclude)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "test")
        git(self.repo, "config", "commit.gpgsign", "false")
        write(self.repo / "src" / "a.txt", "a\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "init")
        verify.git_exclude(self.repo, ".magenta/")
        verify.git_exclude(self.repo, "tests/Unit/")
        (self.repo / ".magenta").mkdir(exist_ok=True)

    def checks(self, items):
        lines = ["checks:"]
        for item in items:
            first = True
            for key, value in item.items():
                lines.append(("  - " if first else "    ") + f"{key}: {json.dumps(value)}")
                first = False
        write(self.repo / ".magenta" / "checks" / "qa.yaml", "\n".join(lines) + "\n")


class IgnoredFilesTest(RepoCase):
    def test_a_change_of_a_locked_test_in_an_ignored_folder_changes_the_fingerprint(self):
        write(self.repo / "tests" / "Unit" / "SaveTest.php", "<?php // v1\n")
        write(self.repo / ".magenta" / "work" / "1-x" / "acceptance.lock",
              json.dumps({"patterns": ["tests/Unit/SaveTest.php"], "files": {"tests/Unit/SaveTest.php": "x"}}))
        before = verify.fingerprint(self.repo)
        write(self.repo / "tests" / "Unit" / "SaveTest.php", "<?php // v2: the test is weaker\n")
        self.assertNotEqual(verify.fingerprint(self.repo), before)

    def test_fingerprint_include_adds_ignored_files(self):
        write(self.repo / "tests" / "Unit" / "OtherTest.php", "<?php // v1\n")
        before = verify.fingerprint(self.repo)
        write(self.repo / "tests" / "Unit" / "NewTest.php", "<?php\n")
        self.assertEqual(verify.fingerprint(self.repo), before)  # git ignores the folder
        write(self.repo / ".magenta" / "policy.json", json.dumps({"fingerprint": {"include": ["tests/Unit/**"]}}))
        with_include = verify.fingerprint(self.repo)
        self.assertIn("+inc:", with_include)
        write(self.repo / "tests" / "Unit" / "OtherTest.php", "<?php // v2\n")
        self.assertNotEqual(verify.fingerprint(self.repo), with_include)

    def test_an_old_pass_does_not_count_after_a_change_of_an_included_file(self):
        write(self.repo / ".magenta" / "policy.json", json.dumps({"fingerprint": {"include": ["tests/Unit/**"]}}))
        write(self.repo / ".magenta" / "t" / "ok.py", "pass\n")
        self.checks([{"id": "qa.ok", "command": f"{PY} .magenta/t/ok.py", "work_item": "T1-x"}])
        verify.approve(self.repo, [])
        verify.start(self.repo, "T1-x", session="S1")
        write(self.repo / "src" / "a.txt", "b\n")
        verify.run(self.repo, "task")
        self.assertEqual(verify.evaluate(self.repo)["status"], verify.PASS)
        write(self.repo / "tests" / "Unit" / "NewTest.php", "<?php\n")
        self.assertNotEqual(verify.evaluate(self.repo)["status"], verify.PASS)


class RunFolderTest(RepoCase):
    def setUp(self):
        super().setUp()
        write(self.repo / ".magenta" / "t" / "env.py",
              "import os, sys\nprint('repo=' + os.environ['MAGENTA_REPO'])\n")
        self.checks([{"id": "qa.env", "command": f"{PY} .magenta/t/env.py"}])
        verify.approve(self.repo, [])

    def test_the_folder_name_is_utc_and_the_check_gets_the_repository(self):
        outcome = verify.run(self.repo)
        log = self.repo / outcome["results"][0]["log"]
        self.assertTrue(log.parent.name.endswith("Z"), log.parent.name)
        self.assertIn(f"repo={self.repo}", log.read_text(encoding="utf-8"))

    def test_old_run_folders_are_deleted(self):
        runs = self.repo / ".magenta" / "runs" / "verify"
        for i in range(40):
            (runs / f"20260101-0000{i:02d}-000000").mkdir(parents=True)
            os.utime(runs / f"20260101-0000{i:02d}-000000", (time.time() - 1000 + i, time.time() - 1000 + i))
        verify.run(self.repo)
        folders = sorted(p.name for p in runs.iterdir())
        self.assertEqual(len(folders), verify.RUNS_KEEP)
        self.assertNotIn("20260101-000000-000000", folders)  # the oldest is gone
        self.assertTrue(any(name.endswith("Z") for name in folders))  # the new run stays

    def test_the_folder_of_a_current_result_stays(self):
        verify.run(self.repo)
        state = json.loads((self.repo / ".magenta" / "verify-state.json").read_text(encoding="utf-8"))
        kept = Path(state["results"]["qa.env"]["log"]).parent.name
        verify._prune_runs(self.repo, state, keep=1)
        self.assertTrue((self.repo / ".magenta" / "runs" / "verify" / kept).is_dir())


class PipelineNoteTest(RepoCase):
    def test_a_pipeline_without_pipefail_gets_a_note(self):
        self.assertIn("pipefail", verify.pipe_note("git diff --name-only | xargs -r php -l"))
        self.assertEqual(verify.pipe_note("set -o pipefail; git diff | xargs -r php -l"), "")
        self.assertEqual(verify.pipe_note("make test || exit 1"), "")
        self.checks([{"id": "qa.lint", "command": "git diff --name-only | xargs -r true"}])
        out = subprocess.run([sys.executable, str(VERIFY), "--repo", str(self.repo), "list"], capture_output=True,
                             text=True)
        self.assertIn("pipefail", out.stdout)
        event = {"tool_input": {"command": '"python3" "/x/verify.py" approve qa.lint'}, "cwd": str(self.repo)}
        self.assertIn("pipefail", verify.approval_details(event))


if __name__ == "__main__":
    unittest.main()


class FewerTurnsTest(RepoCase):
    """begin, gate, and close do the bookkeeping of a task in three calls, with short output."""

    def cli(self, *args):
        return subprocess.run([sys.executable, str(VERIFY), "--repo", str(self.repo), *args], capture_output=True,
                              text=True, cwd=self.repo)

    def test_begin_gate_close(self):
        write(self.repo / ".magenta" / "t" / "ok.py", "pass\n")
        self.checks([{"id": "qa.ok", "command": f"{PY} .magenta/t/ok.py", "work_item": "T1-x"}])
        out = self.cli("begin", "T1-x", "--session", "S1", "--auto")
        self.assertIn("Task T1-x started (auto).", out.stdout)
        self.assertIn("Baseline:", out.stdout)
        write(self.repo / "tests" / "test_a.py", "def test_a():\n    pass\n")
        (self.repo / ".magenta" / "work" / "T1-x").mkdir(parents=True)
        out = self.cli("gate", "T1-x", "tests/test_a.py")
        self.assertEqual(out.returncode, 3, out.stdout + out.stderr)
        self.assertIn("Locked 1 test files", out.stdout)
        self.assertIn("approve qa.ok lock.T1-x", out.stdout)
        verify.approve(self.repo, [])
        self.assertIn("No check waits", self.cli("gate", "T1-x").stdout)
        out = self.cli("close")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("finished: PASS", out.stdout)
        self.assertIn("| qa.ok |", out.stdout)  # the table for the report
        self.assertFalse(verify.active(self.repo).get("work_item"))

    def test_close_keeps_a_failing_task_open(self):
        write(self.repo / ".magenta" / "t" / "bad.py", "raise SystemExit(1)\n")
        self.checks([{"id": "qa.bad", "command": f"{PY} .magenta/t/bad.py", "work_item": "T2-y"}])
        verify.approve(self.repo, [])
        self.cli("begin", "T2-y", "--session", "S2")
        out = self.cli("close")
        self.assertEqual(out.returncode, 1)
        self.assertIn("stays open", out.stdout)
        self.assertEqual(verify.active(self.repo)["work_item"], "T2-y")

    def test_a_passing_run_prints_one_line(self):
        write(self.repo / ".magenta" / "t" / "ok.py", "pass\n")
        self.checks([{"id": "qa.ok", "command": f"{PY} .magenta/t/ok.py"}])
        verify.approve(self.repo, [])
        out = self.cli("run")
        self.assertEqual(out.stdout.strip().count("\n"), 0, out.stdout)
        self.assertIn("PASS. 1 checks passed", out.stdout)
        self.assertIn("| qa.ok |", self.cli("run", "--table").stdout)


class ContextTest(RepoCase):
    def test_rule_files_and_callers(self):
        write(self.repo / "shop" / "money.py", "def to_rials(a):\n    return int(a)\n")
        write(self.repo / "shop" / "refunds.py", "from .money import to_rials\n\ndef refund(p):\n    return to_rials(p)\n")
        write(self.repo / "SECURITY.md", "# Security\n\n- A user reads only their own data.\n- Only names that match\n  a pattern are valid; else raise `ValueError`.\nOther text.\n")
        git(self.repo, "add", "-A")
        text = verify.context(self.repo, ["shop/money.py"])
        self.assertIn("### SECURITY.md", text)
        self.assertIn("A user reads only their own data.", text)
        self.assertIn("else raise `ValueError`", text)  # the continuation line of a rule
        self.assertNotIn("Other text", text)
        self.assertIn("to_rials: shop/refunds.py:1:", text)


class DirectRiskTest(RepoCase):
    def ctx(self, *paths):
        git(self.repo, "add", "-A")
        return verify.context(self.repo, list(paths)).split("## Direct mode", 1)[1]

    def test_a_plain_helper_is_direct(self):
        write(self.repo / "shop" / "pages.py", "def paginate(items, page, size):\n    return items\n")
        self.assertIn("Allowed", self.ctx("shop/pages.py"))

    def test_a_rule_file_that_names_the_module(self):
        write(self.repo / "shop" / "utils.py", "def slug(t):\n    return t\n")
        write(self.repo / "CONTRIBUTING.md", "- `shop.utils` is a public API.\n")
        self.assertIn("CONTRIBUTING.md names shop/utils.py", self.ctx("shop/utils.py"))

    def test_sensitive_format_and_shared_callers(self):
        write(self.repo / "shop" / "store.py", "import json\n\ndef save(p, o):\n    p.write_text(json.dumps(o))\n")
        self.assertIn("stored format", self.ctx("shop/store.py"))
        write(self.repo / "shop" / "login.py", "def login(user, password):\n    return user\n")
        self.assertIn("sensitive area", self.ctx("shop/login.py"))
        write(self.repo / "shop" / "conv.py", "def to_int(a):\n    return int(a)\n")
        write(self.repo / "shop" / "a.py", "from .conv import to_int\n")
        write(self.repo / "shop" / "b.py", "from .conv import to_int\n")
        self.assertIn("to_int in shop/conv.py is used by 2 other files", self.ctx("shop/conv.py"))

    def test_a_longer_name_is_not_a_caller(self):
        write(self.repo / "shop" / "conv.py", "def to_int(a):\n    return int(a)\n")
        write(self.repo / "shop" / "a.py", "from .other import to_integer\nx = to_integer(1)\n")
        self.assertIn("Allowed", self.ctx("shop/conv.py"))
