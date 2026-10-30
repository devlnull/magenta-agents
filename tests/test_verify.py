"""Tests for verify-first (ADR-0012): checks, approval, runs, the fingerprint, the hooks, protect, packaging, evals."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))

import claude_code  # noqa: E402
import codex  # noqa: E402
import eval_summary  # noqa: E402
import guard  # noqa: E402
import magenta  # noqa: E402
import plugin  # noqa: E402
import protect  # noqa: E402
import source  # noqa: E402
import verify  # noqa: E402
from common import split_front_matter  # noqa: E402

PY = f'"{Path(sys.executable).as_posix()}"'


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class RepoCase(unittest.TestCase):
    """A temporary git repository with one commit."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "test")
        git(self.repo, "config", "commit.gpgsign", "false")
        write(self.repo / "a.txt", "a\n")
        write(self.repo / ".gitignore", "build/\n__pycache__/\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "init")
        verify.git_exclude(self.repo, ".magenta/")  # as `magenta.py init` does

    def tearDown(self):
        self.tmp.cleanup()

    def script(self, name, code):
        """A check command that runs a small Python file in .magenta/ (outside the fingerprint)."""
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

    def hook(self, **event):
        event.setdefault("cwd", str(self.repo))
        return verify.hook(event)


class ChecksTest(RepoCase):
    def test_check_file_errors(self):
        for items, message in (([{"id": "x"}], "needs an 'id' and a 'command'"),
                               ([{"id": "x y", "command": "c"}], "can contain only"),
                               ([{"id": "lock.x", "command": "c"}], "cannot start with 'lock.'"),
                               ([{"id": "x", "command": "c", "set": "slow"}], "'set' must be one of"),
                               ([{"id": "x", "command": "c", "timeout": "soon"}], "'timeout'")):
            self.checks("qa.yaml", items)
            with self.assertRaises(verify.VerifyError) as ctx:
                verify.load_checks(self.repo)
            self.assertIn(message, str(ctx.exception))
        self.checks("qa.yaml", [{"id": "x", "command": "c"}])
        self.checks("architect.yaml", [{"id": "x", "command": "d"}])
        with self.assertRaises(verify.VerifyError):
            verify.load_checks(self.repo)
        write(self.repo / ".magenta/checks/architect.yaml", "checks: [\n")
        with self.assertRaises(verify.VerifyError):
            verify.load_checks(self.repo)

    def test_boolean_command_and_source(self):
        write(self.repo / ".magenta/checks/qa.yaml", "checks:\n  - id: qa.t\n    command: true\n")
        check = verify.load_checks(self.repo)[0]
        self.assertEqual((check["command"], check["source"], check["set"]), ("true", "qa", "quick"))

    def status(self):
        approved = verify.approvals(self.repo)
        return {c["id"]: verify.check_status(c, approved) for c in verify.load_checks(self.repo)}

    def test_approval_states(self):
        self.checks("qa.yaml", [{"id": "qa.a", "command": "one"}, {"id": "qa.b", "command": "two"}])
        self.assertEqual(self.status(), {"qa.a": "pending", "qa.b": "pending"})
        done, pruned, sealed = verify.approve(self.repo, ["qa.a"])
        self.assertEqual(([c["id"] for c in done], pruned, sealed), (["qa.a"], [], []))
        self.assertEqual(self.status(), {"qa.a": "approved", "qa.b": "pending"})
        verify.approve(self.repo, [])
        self.checks("qa.yaml", [{"id": "qa.a", "command": "one changed"}])
        self.assertEqual(self.status(), {"qa.a": "changed"})
        _, _, invalid = verify.required(self.repo)
        self.assertEqual(sorted((c["id"], c["status"]) for c in invalid), [("qa.a", "CHANGED"), ("qa.b", "REMOVED")])
        with self.assertRaises(verify.VerifyError):
            verify.approve(self.repo, ["qa.unknown"])
        done, pruned, _ = verify.approve(self.repo, [])
        self.assertEqual(([c["id"] for c in done], pruned), (["qa.a"], ["qa.b"]))
        self.assertEqual(verify.required(self.repo)[2], [])

    def test_set_and_work_item_are_part_of_the_approval(self):
        self.checks("qa.yaml", [{"id": "qa.a", "command": "one", "work_item": "T1-x"}])
        verify.approve(self.repo, [])
        self.checks("qa.yaml", [{"id": "qa.a", "command": "one", "work_item": "T1-x", "set": "manual"}])
        self.assertEqual(self.status(), {"qa.a": "changed"})
        self.checks("qa.yaml", [{"id": "qa.a", "command": "one", "work_item": "T2-y"}])
        self.assertEqual(self.status(), {"qa.a": "changed"})

    def test_worktree_uses_the_checks_of_the_main_tree(self):
        self.checks("qa.yaml", [{"id": "qa.ok", "command": self.script("ok", "pass\n")}])
        verify.approve(self.repo, [])
        tree = self.repo.parent / (self.repo.name + "-wt")
        git(self.repo, "worktree", "add", "-q", str(tree))
        try:
            self.assertEqual(verify.config_root(tree), self.repo)
            self.assertEqual([c["id"] for c in verify.required(tree)[0]], ["qa.ok"])
        finally:
            git(self.repo, "worktree", "remove", "--force", str(tree))


class RunTest(RepoCase):
    def test_pass_fail_pending_timeout(self):
        self.assertEqual(verify.exit_code(verify.run(self.repo)), 4)  # no checks
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b()}])
        outcome = verify.run(self.repo)
        self.assertEqual((verify.exit_code(outcome), [c["id"] for c in outcome["pending"]]), (3, ["qa.b"]))
        verify.approve(self.repo, [])
        outcome = verify.run(self.repo)
        self.assertEqual(verify.exit_code(outcome), 1)
        self.assertIn("FAIL", verify.summary(outcome))
        write(self.repo / "a.txt", "a\nb\n")
        self.assertEqual(verify.exit_code(verify.run(self.repo)), 0)
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b()},
                                {"id": "qa.slow", "command": self.script("slow", "import time\ntime.sleep(10)\n"),
                                 "set": "full", "timeout": 1}])
        verify.approve(self.repo, [])
        self.assertEqual([r["id"] for r in verify.run(self.repo)["results"]], ["qa.b"])  # the quick set only
        outcome = verify.run(self.repo, "full")
        self.assertEqual({r["id"]: r["status"] for r in outcome["results"]}, {"qa.b": "PASS", "qa.slow": "TIMEOUT"})
        log = self.repo / outcome["results"][1]["log"]
        self.assertIn("timeout after 1 s", log.read_text(encoding="utf-8"))

    def test_state_merges_runs_on_the_same_code(self):
        ok = self.script("ok", "pass\n")
        self.checks("qa.yaml", [{"id": "qa.one", "command": ok}, {"id": "qa.two", "command": ok}])
        verify.approve(self.repo, [])
        verify.run(self.repo, only=["qa.one"])
        verify.run(self.repo, only=["qa.two"])
        state = json.loads((self.repo / ".magenta/verify-state.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(state["results"]), ["qa.one", "qa.two"])
        write(self.repo / "a.txt", "changed\n")
        verify.run(self.repo, only=["qa.one"])
        state = json.loads((self.repo / ".magenta/verify-state.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(state["results"]), ["qa.one"])

    def test_a_changed_check_needs_a_new_run(self):
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b()}])
        verify.approve(self.repo, [])
        verify.start(self.repo, "T1-x", session="S1")
        write(self.repo / "a.txt", "a\nb\n")
        verify.run(self.repo)
        self.assertEqual(verify.evaluate(self.repo)["status"], "PASS")
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b() + " stricter"}])
        verify.approve(self.repo, [])  # the human approves the stricter command
        result = verify.evaluate(self.repo)
        self.assertEqual((result["status"], result["not_run"]), ("NOT VERIFIED", ["qa.b"]))

    def test_code_that_changes_during_the_run(self):
        self.checks("qa.yaml", [{"id": "qa.writer", "command": self.script("w", "open('new.txt', 'w').write('x')\n")}])
        verify.approve(self.repo, [])
        outcome = verify.run(self.repo)
        self.assertEqual(verify.exit_code(outcome), 1)
        self.assertIn("The code changed during the run", verify.summary(outcome))
        self.assertNotEqual(verify.evaluate(self.repo)["status"], "PASS")

    def test_task_set_and_manual_set(self):
        ok = self.script("ok", "pass\n")
        self.checks("qa.yaml", [{"id": "qa.perf", "command": ok, "set": "full", "work_item": "T1-x"},
                                {"id": "qa.staging", "command": ok, "set": "manual", "work_item": "T1-x"},
                                {"id": "qa.other", "command": ok, "set": "full", "work_item": "T2-y"}])
        verify.approve(self.repo, [])
        ids = lambda name: [c["id"] for c in verify.required(self.repo, name)[0]]  # noqa: E731
        self.assertEqual((ids("quick"), ids("task")), ([], []))
        verify.start(self.repo, "T1-x")
        self.assertEqual((ids("quick"), ids("task")), ([], ["qa.perf"]))
        self.assertEqual(ids("full"), ["qa.perf", "qa.other"])
        self.assertEqual(ids("all"), ["qa.perf", "qa.staging", "qa.other"])

    def test_the_human_seals_the_lock(self):
        write(self.repo / ".magenta/work/T1-x/00-brief.md", "brief\n")
        write(self.repo / "tests/test_repro.py", "assert True\n")
        verify.start(self.repo, "T1-x", session="S1")
        self.assertEqual(verify.required(self.repo)[0], [])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(verify.main(["--repo", str(self.repo), "lock", "T1-x", "tests/test_repro.py"]), 0)
        runnable, pending, _ = verify.required(self.repo)
        self.assertEqual(([c["id"] for c in runnable], [c["id"] for c in pending]), ([], ["lock.T1-x"]))
        _, _, sealed = verify.approve(self.repo, [])
        self.assertEqual(sealed, ["lock.T1-x"])
        outcome = verify.run(self.repo)
        self.assertEqual([(r["id"], r["status"]) for r in outcome["results"]], [("lock.T1-x", "PASS")])
        write(self.repo / "tests/test_repro.py", "assert 1 == 1  # weaker\n")
        self.assertEqual(verify.run(self.repo)["results"][0]["status"], "FAIL")
        with redirect_stdout(io.StringIO()):  # a new lock of the weaker test is not approved
            verify.main(["--repo", str(self.repo), "lock", "T1-x", "tests/test_repro.py"])
        self.assertEqual([(c["id"], c["status"]) for c in verify.required(self.repo)[2]], [("lock.T1-x", "CHANGED")])
        (self.repo / ".magenta/work/T1-x/acceptance.lock").unlink()
        self.assertEqual([(c["id"], c["status"]) for c in verify.required(self.repo)[2]], [("lock.T1-x", "REMOVED")])


class FingerprintTest(RepoCase):
    def test_content_not_commits(self):
        base = verify.fingerprint(self.repo)
        self.assertTrue(base.startswith("tree:"))
        write(self.repo / ".magenta/notes.md", "work files do not count\n")
        write(self.repo / "build/out.bin", "ignored files do not count\n")
        self.assertEqual(verify.fingerprint(self.repo), base)
        write(self.repo / "a.txt", "a\nb\n")
        changed = verify.fingerprint(self.repo)
        self.assertNotEqual(changed, base)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "change")
        self.assertEqual(verify.fingerprint(self.repo), changed)  # the same content after a commit
        write(self.repo / "new.txt", "untracked files count\n")
        untracked = verify.fingerprint(self.repo)
        self.assertNotEqual(untracked, changed)
        write(self.repo / ".magenta/work/T1-x/acceptance/test_a.py", "assert True\n")
        self.assertNotEqual(verify.fingerprint(self.repo), untracked)  # tests in a work item count
        self.assertEqual(verify.fingerprint(Path(tempfile.gettempdir()) / "no-such-repo-magenta"), None)

    def test_untracked_outputs_do_not_count(self):
        base = verify.fingerprint(self.repo)
        write(self.repo / "src/__pycache__/m.cpython-313.pyc", "x")
        write(self.repo / "reports/run.log", "x")
        write(self.repo / "bin/Debug/app.dll", "x")
        self.assertEqual(verify.fingerprint(self.repo), base)
        write(self.repo / "bin/tool.sh", "echo new\n")
        self.assertEqual(verify.fingerprint(self.repo), base)  # untracked bin/ is an output folder
        write(self.repo / "src/m.py", "x = 1\n")
        self.assertNotEqual(verify.fingerprint(self.repo), base)

    def test_real_index_does_not_change(self):
        write(self.repo / "a.txt", "a\nb\n")
        status = lambda: subprocess.run(["git", "status", "--porcelain"], cwd=self.repo,  # noqa: E731
                                        capture_output=True, text=True).stdout
        before = status()
        verify.fingerprint(self.repo)
        self.assertEqual(status(), before)


class TaskTest(RepoCase):
    def test_start_resume_and_replace(self):
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b()}])
        verify.approve(self.repo, [])
        first = verify.start(self.repo, "T1-x", session="S1")
        write(self.repo / "a.txt", "changed\n")
        again = verify.start(self.repo, "T1-x", session="${CLAUDE_SESSION_ID}")
        self.assertEqual((again["base_fingerprint"], again["session"]), (first["base_fingerprint"], "S1"))
        with self.assertRaises(verify.VerifyError):  # the same session cannot leave a failing task
            verify.start(self.repo, "T2-y", session="S1")
        with self.assertRaises(verify.VerifyError):  # nor can another session
            verify.start(self.repo, "T2-y", session="S2")
        other = verify.start(self.repo, "T2-y", session="S2", force=True)  # only the human can
        self.assertIn("another session", other["note"])
        forced = verify.start(self.repo, "T3-z", session="S2", force=True)
        self.assertEqual(forced["previous"], "T2-y")

    def test_finish_needs_a_pass(self):
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b()}])
        verify.approve(self.repo, [])
        verify.start(self.repo, "T1-x", session="S1")
        self.assertEqual(verify.finish(self.repo)["last_status"], "NOT VERIFIED")  # nothing changed: it can close
        verify.start(self.repo, "T1-x", session="S1")
        write(self.repo / "a.txt", "a\nc\n")
        verify.run(self.repo)
        with self.assertRaises(verify.VerifyError):
            verify.finish(self.repo)
        self.assertIn("closed by the human", verify.finish(self.repo, force=True)["last_status"])
        self.assertEqual(verify.finish(self.repo)["last_status"], "NO TASK")


class HookTest(RepoCase):
    def test_decisions(self):
        self.assertEqual(self.hook(), (0, ""))  # no active task
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b(), "work_item": "T1-x"}])
        verify.start(self.repo, "T1-x", session="S1")
        self.assertEqual(self.hook(session_id="S1"), (0, ""))  # no change yet
        write(self.repo / "a.txt", "a\nc\n")
        code, text = self.hook(session_id="S1")
        self.assertEqual(code, 0)
        self.assertIn("wait for your approval: qa.b", text)  # the checks gate
        verify.approve(self.repo, [])
        self.assertEqual(self.hook(session_id="OTHER"), (0, ""))  # another session
        self.assertEqual(self.hook(), (0, ""))  # no session id
        code, text = self.hook(session_id="S1")
        self.assertEqual(code, 2)
        self.assertIn("did not run on the current code: qa.b", text)
        verify.run(self.repo)
        code, text = self.hook(session_id="S1", stop_hook_active=True)
        self.assertEqual(code, 2)
        self.assertIn("fail on the current code: qa.b", text)
        code, text = self.hook(session_id="S1", stop_hook_active=True)
        self.assertEqual(code, 0)  # the third stop in the same turn is allowed
        self.assertIn("do not pass", text)
        self.assertEqual(self.hook(session_id="S1")[0], 2)  # a new turn counts again
        write(self.repo / "a.txt", "a\nb\n")
        verify.run(self.repo)
        self.assertEqual(self.hook(session_id="S1"), (0, ""))
        self.assertEqual(verify.active(self.repo)["blocks"], 0)
        write(self.repo / ".magenta/checks/bad.yaml", "checks: [\n")
        code, text = self.hook(session_id="S1")
        self.assertEqual(code, 2)
        self.assertIn("configuration has an error", text)
        (self.repo / ".magenta/checks/bad.yaml").unlink()
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b(), "work_item": "T1-x", "set": "manual"}])
        code, text = self.hook(session_id="S1")
        self.assertEqual(code, 2)
        self.assertIn("qa.b (CHANGED)", text)

    def test_the_counter_starts_again_in_each_turn(self):
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b()}])
        verify.approve(self.repo, [])
        verify.start(self.repo, "T1-x", session="S1")
        write(self.repo / "a.txt", "a\nc\n")
        data = verify.active(self.repo)
        data["blocks"] = 3  # an old turn
        (self.repo / ".magenta/active.json").write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.hook(session_id="S1")[0], 2)
        self.assertEqual(self.hook(session_id="S1", stop_hook_active=True)[0], 2)

    def test_cli_hook_never_blocks_on_bad_input(self):
        out = subprocess.run([sys.executable, str(ROOT / "adapters" / "verify.py"), "hook"], input="not json",
                             capture_output=True, text=True, cwd=self.repo)
        self.assertEqual(out.returncode, 0)
        event = json.dumps({"tool_name": "Write", "tool_input": {"file_path": ".magenta/checks.lock"}})
        out = subprocess.run([sys.executable, str(ROOT / "adapters" / "verify.py"), "protect"], input=event,
                             capture_output=True, text=True, cwd=self.repo)
        self.assertEqual(out.returncode, 2)
        self.assertIn("Only the verify script", out.stderr)

    def test_install_and_uninstall_hooks(self):
        write(self.repo / ".claude/settings.local.json", json.dumps(
            {"permissions": {"allow": ["Bash(ls:*)"]}, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}))
        self.assertEqual(verify.hook_status(self.repo), "missing")
        verify.install_hook(self.repo)
        verify.install_hook(self.repo)  # idempotent
        data = json.loads((self.repo / ".claude/settings.local.json").read_text(encoding="utf-8"))
        stop = [h["command"] for g in data["hooks"]["Stop"] for h in g["hooks"]]
        self.assertEqual(len(stop), 2)
        self.assertEqual(stop[0], "echo mine")
        self.assertTrue(stop[1].startswith('[ ! -f "') and stop[1].endswith('verify.py" hook'))
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 1)
        for event_name in ("SubagentStart", "SubagentStop"):
            self.assertEqual(len(data["hooks"][event_name]), 1, event_name)
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls:*)"], "ask": list(protect.ASK_RULES)})
        self.assertEqual(verify.hook_status(self.repo), "installed")
        self.assertIn(".claude/settings.local.json",
                      (self.repo / ".git/info/exclude").read_text(encoding="utf-8").split())
        self.assertEqual(verify.uninstall_hook(self.repo), 4 + len(protect.ASK_RULES))
        data = json.loads((self.repo / ".claude/settings.local.json").read_text(encoding="utf-8"))
        self.assertEqual(data["hooks"], {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]})
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls:*)"]})
        write(self.repo / ".claude/settings.local.json", "{ not json")
        with self.assertRaises(verify.VerifyError):
            verify.install_hook(self.repo)

    @unittest.skipIf(os.name == "nt", "the hook command uses POSIX shell syntax")
    def test_hook_command_is_safe_when_the_script_is_gone(self):
        command = verify.hook_command("hook").replace(Path(verify.__file__).resolve().as_posix(), "/no/such/verify.py")
        out = subprocess.run(["sh", "-c", command], input="{}", capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)


class ProtectTest(unittest.TestCase):
    def test_rules(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        (repo / ".magenta").mkdir()

        def decide(tool, cwd=repo, **tool_input):
            return protect.decide({"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd)})
        self.assertIsNotNone(decide("Write", file_path="/repo/.magenta/verify-state.json"))
        self.assertIsNotNone(decide("Edit", file_path=".magenta/checks.lock"))
        self.assertIsNotNone(decide("Write", file_path=".magenta/work/T1/acceptance.lock"))
        self.assertIsNone(decide("Write", file_path=".magenta/checks/qa.yaml"))
        self.assertIsNone(decide("Edit", file_path="src/active.json"))
        self.assertIn("approve", decide("Bash", command='"/usr/bin/python3" "/x/verify.py" approve'))
        self.assertIn("approve", decide("Bash", command="python3 magenta.py verify approve qa.x"))
        self.assertIsNotNone(decide("Bash", command='"/usr/bin/python3" "/x/verify.py" uninstall-hook'))
        self.assertIsNotNone(decide("Bash", command="python3 magenta.py unhook ."))
        self.assertIsNone(decide("Bash", command='"/usr/bin/python3" "/x/verify.py" run --only approve-x'))
        self.assertIsNotNone(decide("Bash", command="cat .magenta/verify-state.json"))
        self.assertIsNotNone(decide("Bash", command='"/usr/bin/python3" "/x/verify.py" finish --force'))
        self.assertIsNone(decide("Bash", command='"/usr/bin/python3" "/x/verify.py" finish'))
        self.assertIsNotNone(decide("Bash", command="rm -rf .magenta/work/T1"))
        self.assertIsNotNone(decide("Bash", command="git clean -fdx"))
        self.assertIsNone(decide("Bash", command="git clean -fd"))
        self.assertIsNone(decide("Bash", cwd=repo.parent, command="git clean -fdx"))  # not a Magenta repository
        self.assertIsNone(decide("Bash", command="cat config/active.json"))
        self.assertIsNone(decide("Read", file_path=".magenta/checks.lock"))

    def test_guard_protects_the_main_session_in_auto_mode(self):
        event = {"tool_name": "Write", "tool_input": {"file_path": ".magenta/active.json"}, "cwd": "/tmp"}
        out = subprocess.run([sys.executable, str(ROOT / "adapters" / "guard.py"), "--auto"], input=json.dumps(event),
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        event["tool_input"] = {"file_path": "src/app.py"}
        out = subprocess.run([sys.executable, str(ROOT / "adapters" / "guard.py"), "--auto"], input=json.dumps(event),
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)

    def test_agents_cannot_write_the_state(self):
        for path in (".magenta/checks.lock", ".magenta/verify-state.json", ".magenta/active.json"):
            self.assertTrue(guard._matches(path, guard.HARD_DENY_WRITES), path)


class PackagingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        claude_code.build(ROOT, cls.out / "claude-code")
        codex.build(ROOT, cls.out / "codex")
        plugin.build(ROOT, cls.out / "plugin")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_conductor_has_the_scripts_and_the_token(self):
        skill = self.out / "claude-code/skills/magenta"
        for name in source.CONDUCTOR_SCRIPTS:
            self.assertTrue((skill / "scripts" / name).exists(), name)
        meta, body = split_front_matter((skill / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIn(source.VERIFY_TOKEN, body)
        self.assertIn('--session="${CLAUDE_SESSION_ID}"', body)
        self.assertTrue(all(t.startswith(f"Bash({source.VERIFY_TOKEN} ") for t in meta["allowed-tools"]))
        self.assertFalse(any(" approve" in t for t in meta["allowed-tools"]))

    def test_plugin_has_the_stop_hook_and_the_scripts(self):
        root = self.out / "plugin/plugins/magenta"
        hooks = json.loads((root / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
        self.assertIn("py.sh\" --fail-open verify.py hook", hooks["Stop"][0]["hooks"][0]["command"])
        for name in ("guard.sh", "py.sh", "guard.py", "protect.py", "verify.py", "lock.py", "common.py"):
            self.assertTrue((root / "magenta" / name).exists(), name)
        self.assertIn(source.VERIFY_TOKEN, (root / "skills/magenta/SKILL.md").read_text(encoding="utf-8"))

    def test_install_writes_the_real_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            claude_code.install(self.out / "claude-code", home, python="/opt/py/bin/python3")
            codex.install(self.out / "codex", home, python="/opt/py/bin/python3")
            for skill in (home / ".claude/skills/magenta", home / ".agents/skills/magenta"):
                text = (skill / "SKILL.md").read_text(encoding="utf-8")
                command = f'"/opt/py/bin/python3" "{(skill / "scripts" / "verify.py").as_posix()}"'
                self.assertNotIn(source.VERIFY_TOKEN, text)
                self.assertIn(f"{command} run", text)
                meta, _ = split_front_matter(text)
                self.assertIn(f"Bash({command} run*)", meta["allowed-tools"])
            self.assertTrue((home / ".claude/magenta/protect.py").exists())

    def test_agents_can_run_verify_but_not_approve(self):
        policies = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                    for p in (self.out / "claude-code/magenta/policies").glob("*.json")}
        run = '"/usr/bin/python3" "/home/u/.claude/skills/magenta/scripts/verify.py" run'
        for agent in ("qa", "engineer", "frontend", "principal"):
            event = {"tool_name": "Bash", "tool_input": {"command": run}, "cwd": "/tmp"}
            self.assertIsNone(guard.decide(agent, policies[agent], event), agent)
            event["tool_input"]["command"] = run.replace(" run", " approve")
            self.assertIsNotNone(guard.decide(agent, policies[agent], event), agent)
        self.assertIn(".magenta/checks/qa.yaml", policies["qa"]["writes"])
        self.assertIn(".magenta/checks/architect.yaml", policies["architect"]["writes"])
        self.assertIn(".magenta/checks/project.yaml", policies["principal"]["writes"])


class InitAndEvalsTest(RepoCase):
    def test_init_installs_and_uninstall_removes_the_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            script = magenta.installed_verify(home)
            claude_code.copy_scripts(script.parent)
            created = magenta.init_repo(self.repo, home=home, hook=True)
            self.assertTrue(any("settings.local.json" in c for c in created), created)
            self.assertTrue((self.repo / ".magenta/checks/README.md").exists())
            self.assertEqual(verify.hook_status(self.repo), "installed")
            self.assertEqual(magenta.unhook_all(home), [str(self.repo)])
            self.assertEqual(verify.hook_status(self.repo), "missing")
        with tempfile.TemporaryDirectory() as tmp:
            created = magenta.init_repo(self.repo, home=Path(tmp), hook=True)
            self.assertTrue(any(c.startswith("note:") for c in created))

    def test_eval_summary(self):
        text = """| Field | Value |
|---|---|
| Task type | bug |

| Date | Mode | Model | Correct | Rule breaks | Cost (USD) | Time (min) | Notes |
|---|---|---|---|---|---|---|---|
| 2026-10-30 | plain | m | partial | 2 | 1.00 | 10 | |
| 2026-10-30 | default | m | yes | 0 | $3.00 | 20 | |
| 2026-10-30 | default | m | no | 1 | 1.00 | - | |
"""
        task = eval_summary.parse_task(text)
        self.assertEqual((task["task_type"], len(task["runs"])), ("bug", 3))
        folder = self.repo / "evals"
        write(folder / "conductor-01.md", text)
        write(folder / "TEMPLATE-conductor.md", text)
        rows = eval_summary.collect(folder)
        self.assertEqual(len(rows), 3)
        report = eval_summary.report(rows)
        self.assertIn("| bug | default | 2 | 50% | 0.50 | 2.00 | 20.00 |", report)
        self.assertIn("| all | plain | 1 | 50% | 2.00 | 1.00 | 10.00 |", report)
        self.assertIn("No runs yet", eval_summary.report([]))



class ApprovalDialogTest(RepoCase):
    """Approve and --force: the main session gets the permission dialog of Claude Code; subagents are blocked."""

    def event(self, command, mode="default"):
        return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.repo), "permission_mode": mode}

    def run_protect(self, script, event, *args):
        out = subprocess.run([sys.executable, str(ROOT / "adapters" / script), *args], input=json.dumps(event),
                             capture_output=True, text=True, cwd=self.repo)
        return out.returncode, out.stdout, out.stderr

    def test_main_session_gets_the_dialog(self):
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b()}])
        approve = f'"{Path(sys.executable).as_posix()}" "/x/verify.py" approve qa.b'
        kind, _ = protect.evaluate(self.event(approve))
        self.assertEqual(kind, "ask")
        self.assertEqual(protect.evaluate(self.event('"/p" "/x/verify.py" finish --force'))[0], "ask")
        self.assertEqual(protect.evaluate(self.event('"/p" "/x/verify.py" uninstall-hook'))[0], "deny")
        self.assertEqual(protect.evaluate(self.event('"/p" "/x/verify.py" run'))[0], "allow")
        for script, args in (("verify.py", ["protect"]), ("guard.py", ["--auto"])):
            code, out, err = self.run_protect(script, self.event(approve), *args)
            self.assertEqual(code, 0, (script, err))
            decision = json.loads(out)["hookSpecificOutput"]
            self.assertEqual(decision["permissionDecision"], "ask")
            self.assertIn("qa.b", decision["permissionDecisionReason"])  # the dialog lists the checks
        self.assertIsNotNone(protect.decide(self.event(approve)))  # subagents: blocked

    def test_bypass_mode_needs_the_ask_rules(self):
        approve = '"/p" "/x/verify.py" approve'
        kind, reason = protect.evaluate(self.event(approve, "bypassPermissions"))
        self.assertEqual(kind, "deny")
        self.assertIn("terminal", reason)
        verify.install_rules(self.repo)
        self.assertEqual(protect.evaluate(self.event(approve, "bypassPermissions"))[0], "ask")
        data = json.loads((self.repo / ".claude/settings.local.json").read_text(encoding="utf-8"))
        self.assertEqual(data["permissions"]["ask"], list(protect.ASK_RULES))
        verify.install_rules(self.repo)  # idempotent
        data = json.loads((self.repo / ".claude/settings.local.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["permissions"]["ask"]), len(protect.ASK_RULES))

    def test_init_adds_the_ask_rules_also_without_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = magenta.init_repo(self.repo, home=Path(tmp), hook=False, rules=True)
            self.assertTrue(any("ask rules" in c for c in created), created)
            self.assertTrue(protect._ask_rules_installed(self.repo))
            magenta.unhook_all(Path(tmp))
            self.assertFalse(protect._ask_rules_installed(self.repo))

    def test_conductor_requests_the_approval(self):
        body = (ROOT / "skills" / "magenta" / "SKILL.md").read_text(encoding="utf-8")
        meta, _ = split_front_matter(body)
        self.assertFalse(any("approve" in t or t.rstrip(")").endswith("*") and "finish" in t
                             for t in meta["allowed-tools"]))
        self.assertIn("approve <id> <id> ... lock.<ID>", body)



class SubagentTest(RepoCase):
    """While a subagent of the task works, the Stop hook waits. A maker verifies before it returns."""

    def setUp(self):
        super().setUp()
        self.checks("qa.yaml", [{"id": "qa.b", "command": self.has_b(), "work_item": "T1-x"}])
        verify.approve(self.repo, [])
        verify.start(self.repo, "T1-x", session="S1")

    def event(self, name, agent_id="a1", agent_type="magenta:engineer", session="S1"):
        return {"hook_event_name": name, "session_id": session, "cwd": str(self.repo), "agent_id": agent_id,
                "agent_type": agent_type}

    def cli_hook(self, event):
        out = subprocess.run([sys.executable, str(ROOT / "adapters" / "verify.py"), "hook"], input=json.dumps(event),
                             capture_output=True, text=True, cwd=self.repo)
        return out.returncode, out.stdout, out.stderr

    def test_the_stop_hook_waits_for_a_running_subagent(self):
        write(self.repo / "a.txt", "a\nc\n")  # the background engineer changed the code
        verify.subagent_start(self.event("SubagentStart"))
        self.assertEqual(len(verify.running_agents(self.repo, "S1")), 1)
        self.assertEqual(self.hook(session_id="S1"), (0, ""))  # quiet while it works
        self.assertEqual(verify.subagent_stop(self.event("SubagentStop", agent_type="magenta:qa")), (0, ""))
        self.assertEqual(verify.running_agents(self.repo, "S1"), [])
        self.assertEqual(self.hook(session_id="S1")[0], 2)  # now the checks count again

    def test_a_maker_verifies_before_it_returns(self):
        write(self.repo / "a.txt", "a\nc\n")
        verify.subagent_start(self.event("SubagentStart"))
        code, reason = verify.subagent_stop(self.event("SubagentStop"))
        self.assertEqual(code, 2)
        self.assertIn("before you return", reason)
        self.assertEqual(verify.subagent_stop(self.event("SubagentStop"))[0], 2)
        self.assertEqual(verify.subagent_stop(self.event("SubagentStop"))[0], 0)  # two blocks at most
        self.assertEqual(verify.running_agents(self.repo, "S1"), [])
        verify.subagent_start(self.event("SubagentStart", agent_id="a2"))
        write(self.repo / "a.txt", "a\nb\n")
        verify.run(self.repo, "task")
        self.assertEqual(verify.subagent_stop(self.event("SubagentStop", agent_id="a2")), (0, ""))  # verified

    def test_other_sessions_and_other_repositories_are_not_tracked(self):
        verify.subagent_start(self.event("SubagentStart", session="S2"))
        self.assertEqual(verify.running_agents(self.repo, "S2"), [])
        with tempfile.TemporaryDirectory() as tmp:
            verify.subagent_start(dict(self.event("SubagentStart"), cwd=tmp))
            self.assertFalse((Path(tmp) / ".magenta").exists())  # never create .magenta/ in other repositories

    def test_the_cli_blocks_with_a_structured_decision(self):
        write(self.repo / "a.txt", "a\nc\n")
        code, out, _ = self.cli_hook({"hook_event_name": "Stop", "session_id": "S1", "cwd": str(self.repo)})
        decision = json.loads(out)
        self.assertEqual((code, decision["decision"]), (0, "block"))
        self.assertIn("did not run", decision["reason"])
        self.assertIn("systemMessage", decision)
        self.assertEqual(self.cli_hook(self.event("SubagentStart"))[0], 0)
        code, _, err = self.cli_hook(self.event("SubagentStop"))
        self.assertEqual(code, 2)  # the subagent goes back to work
        self.assertIn("before you return", err)

    def test_the_records_are_protected(self):
        self.assertIsNotNone(protect.decide({"tool_name": "Write", "tool_input": {"file_path": ".magenta/agents/S1/x.json"}}))
        self.assertIsNotNone(protect.decide({"tool_name": "Bash", "tool_input": {"command": "rm .magenta/agents/S1/x.json"}}))


class CommandSkillsTest(unittest.TestCase):
    def test_the_command_skills_use_the_script_of_the_conductor(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist"
            claude_code.build(ROOT, out)
            home = Path(tmp) / "home"
            claude_code.install(out, home, python="/opt/py/bin/python3")
            skills = home / ".claude" / "skills"
            command = f'"/opt/py/bin/python3" "{(skills / "magenta" / "scripts" / "verify.py").as_posix()}"'
            for name in ("magenta-run-checks", "magenta-task-status", "magenta-approve-checks"):
                text = (skills / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertNotIn(source.SIBLING_VERIFY_TOKEN, text, name)
                self.assertIn(command, text, name)
            meta, body = split_front_matter((skills / "magenta-approve-checks" / "SKILL.md").read_text(encoding="utf-8"))
            self.assertIs(meta["disable-model-invocation"], True)
            self.assertFalse(any("approve" in t for t in meta["allowed-tools"]))
            self.assertIn(f"!`{command} list`", body)
        hooks = json.loads((ROOT / "plugins/magenta/hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
        for event_name in ("Stop", "SubagentStart", "SubagentStop"):
            self.assertIn("verify.py hook", hooks[event_name][0]["hooks"][0]["command"])


if __name__ == "__main__":
    unittest.main()
