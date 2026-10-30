import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))
sys.path.insert(0, str(ROOT / "runner"))

import magenta  # noqa: E402
import runner  # noqa: E402

FAKE_ENGINE = (
    "import json, sys\n"
    "print(json.dumps({'result': 'review from stdout', 'total_cost_usd': 0.25, 'num_turns': 3,"
    " 'is_error': EXIT_CODE != 0}))\n"
    "sys.stderr.write('warning: noise on stderr\\n')\n"
    "sys.exit(EXIT_CODE)\n"
)

FINDINGS_HEADER = "| Severity | File:line | Finding | Risk | Fix |\n|---|---|---|---|---|\n"


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def cli(*args):
    out = subprocess.run([sys.executable, str(ROOT / "magenta.py"), *args], capture_output=True, text=True)
    return out.returncode, out.stdout + out.stderr


def read_log(repo):
    log = repo / ".magenta/runs/runs.jsonl"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


class W8PrdReviewRefusesExistingItem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.prd = self.repo / "prd.md"
        self.prd.write_text("# Cancel orders\n", encoding="utf-8")
        self.item = self.repo / ".magenta/work/42-prd"

    def tearDown(self):
        self.tmp.cleanup()

    def review(self):
        return cli("run", "prd-review", "--repo", str(self.repo), "--prd", str(self.prd), "--id", "42", "--dry-run")

    def review_again(self):
        code, out = self.review()
        self.assertEqual(code, 0, out)
        self.state = (self.item / "state.yaml").read_text(encoding="utf-8")
        self.request = (self.item / "00-request.md").read_text(encoding="utf-8")
        (self.item / "01-prd-review.md").write_text("# PRD review\nOLD VERDICT\n", encoding="utf-8")
        self.prd.write_text("# Cancel orders, second version\n", encoding="utf-8")
        return self.review()

    def test_new_id_creates_the_work_item(self):
        code, out = self.review()
        self.assertEqual(code, 0, out)
        self.assertIn("step: prd-review", (self.item / "state.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(read_log(self.repo)), 1)

    def test_existing_id_fails_with_a_clear_message(self):
        code, out = self.review_again()
        self.assertNotEqual(code, 0, out)
        self.assertIn("42", out)
        self.assertRegex(out, r"(?i)exist|already")

    def test_existing_id_keeps_the_state_and_the_request(self):
        self.review_again()
        self.assertEqual((self.item / "state.yaml").read_text(encoding="utf-8"), self.state)
        self.assertEqual((self.item / "00-request.md").read_text(encoding="utf-8"), self.request)

    def test_existing_id_does_not_report_the_old_review(self):
        _, out = self.review_again()
        self.assertNotIn("OLD VERDICT", out)

    def test_existing_id_runs_no_agent(self):
        self.review_again()
        self.assertEqual(len(read_log(self.repo)), 1)


class W8CostReadFromStdoutOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        self.repo.mkdir()
        self.engine = base / "engine"
        self.engine.mkdir()
        self.prd = self.repo / "prd.md"
        self.prd.write_text("# Cancel orders\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def review_with_engine_exit(self, exit_code):
        script = self.engine / "fake_engine.py"
        script.write_text(FAKE_ENGINE.replace("EXIT_CODE", str(exit_code)), encoding="utf-8")
        run = runner.Run(ROOT, self.repo, "prd-review", engine_override="fake-w8")
        run.cfg["engines"]["fake-w8"] = [sys.executable, str(script)]
        result = runner.prd_review(run, self.prd, "7")
        return result, read_log(self.repo)[-1]

    def test_failed_step_with_stderr_keeps_text_cost_and_turns(self):
        result, entry = self.review_with_engine_exit(1)
        self.assertEqual(entry["status"], "FAILED")
        self.assertIsNotNone(entry["cost_usd"])
        self.assertAlmostEqual(entry["cost_usd"], 0.25)
        self.assertEqual(entry["turns"], 3)
        self.assertIn("review from stdout", result["report"])

    def test_successful_step_with_stderr_keeps_text_cost_and_turns(self):
        result, entry = self.review_with_engine_exit(0)
        self.assertEqual(entry["status"], "OK")
        self.assertAlmostEqual(entry["cost_usd"], 0.25)
        self.assertEqual(entry["turns"], 3)
        self.assertIn("review from stdout", result["report"])


class W8BudgetCheckedBeforeEachStep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "a.py").write_text("x = 1\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "init")
        (self.repo / "a.py").write_text("x = 2\n")
        git(self.repo, "commit", "-qam", "change")
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def fake(self, cost=0.5):
        def executor(cmd, cwd, timeout):
            self.calls.append(cmd)
            for item in (cwd / ".magenta/work").glob("*"):
                (item / "01-prd-review.md").write_text("# PRD review\nGO\n", encoding="utf-8")
            return 0, json.dumps({"result": "| MINOR | a.py:1 | x | y | z |", "total_cost_usd": cost,
                                  "num_turns": 2, "is_error": False})
        return executor

    def test_zero_budget_pr_review_runs_no_reviewer(self):
        run = runner.Run(ROOT, self.repo, "pr-review", budget_usd=0.0, executor=self.fake())
        result = runner.pr_review(run, "HEAD~1")
        self.assertEqual(result["status"], "BUDGET_EXCEEDED")
        self.assertEqual(self.calls, [])
        self.assertEqual(list(run.run_dir.glob("review-*.md")), [])

    def test_zero_budget_prd_review_runs_no_agent(self):
        prd = self.repo / "prd.md"
        prd.write_text("# Cancel orders\n", encoding="utf-8")
        run = runner.Run(ROOT, self.repo, "prd-review", budget_usd=0.0, executor=self.fake())
        try:
            status = runner.prd_review(run, prd, "9")["status"]
        except runner.RunError:
            status = "REFUSED"
        self.assertNotEqual(status, "OK")
        self.assertEqual(self.calls, [])

    def test_budget_reached_by_reviews_skips_the_merge(self):
        run = runner.Run(ROOT, self.repo, "pr-review", budget_usd=1.2, executor=self.fake(cost=0.5))
        result = runner.pr_review(run, "HEAD~1")
        self.assertEqual(result["status"], "BUDGET_EXCEEDED")
        self.assertEqual(len(self.calls), 3)
        self.assertFalse((run.run_dir / "merge.md").exists())

    def test_no_budget_runs_reviews_and_merge(self):
        run = runner.Run(ROOT, self.repo, "pr-review", executor=self.fake())
        result = runner.pr_review(run, "HEAD~1")
        self.assertEqual(result["status"], "OK")
        self.assertEqual(len(self.calls), 4)


class W8FailOnBlockerMatchesFindingsOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def exit_code(self, report, *flags):
        result = {"status": "OK", "report": report}
        with mock.patch.object(magenta.headless, "pr_review", return_value=result):
            with contextlib.redirect_stdout(io.StringIO()):
                return magenta.main(["run", "pr-review", "--repo", str(self.repo), *flags])

    def test_bold_blocker_finding_fails(self):
        report = "CHANGES REQUESTED, 1 BLOCKER, 0 MAJOR\n\n" + FINDINGS_HEADER + "| **BLOCKER** | a.py:1 | bad | risk | fix |\n"
        self.assertEqual(self.exit_code(report, "--fail-on-blocker"), 3)

    def test_plain_blocker_finding_fails(self):
        report = FINDINGS_HEADER + "| BLOCKER | a.py:1 | bad | risk | fix |\n"
        self.assertEqual(self.exit_code(report, "--fail-on-blocker"), 3)

    def test_count_row_does_not_fail(self):
        for row in ("| BLOCKER | 0 |", "|BLOCKER|0|", "| **BLOCKER** | 0 |"):
            with self.subTest(row=row):
                report = ("APPROVED\n\n| Severity | Count |\n|---|---|\n" + row + "\n| MAJOR | 0 |\n\n"
                          + FINDINGS_HEADER + "| MINOR | a.py:1 | name | low | rename |\n")
                self.assertEqual(self.exit_code(report, "--fail-on-blocker"), 0)

    def test_without_the_flag_a_blocker_does_not_fail(self):
        report = FINDINGS_HEADER + "| **BLOCKER** | a.py:1 | bad | risk | fix |\n"
        self.assertEqual(self.exit_code(report), 0)


if __name__ == "__main__":
    unittest.main()
