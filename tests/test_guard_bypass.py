"""Tests for the shell bypasses of the guard and the protect hook (work item 20261030-w1-guard-shell-bypass, S1 to S6).

The policies come from the canonical source in agents/*.md, so each test covers every agent that has the pattern.
"""
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

VERIFY = "/home/u/.claude/plugins/x/skills/magenta/scripts/verify.py"
WORK_ITEM = "20261030-w1-guard-shell-bypass"


class ShellCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = source.load_config(ROOT)
        agents = source.load_agents(ROOT, cfg["agents_enabled"])
        cls.policies = {a: source.policy(a, agents[a]) for a in agents}
        cls.tmp = tempfile.TemporaryDirectory()
        cls.cwd = str(Path(cls.tmp.name).resolve())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def decide(self, agent, command):
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": self.cwd}
        return guard.decide(agent, self.policies[agent], event)

    def protect(self, command):
        return protect.decide({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": self.cwd})

    def agents_with(self, has_pattern):
        agents = sorted(a for a, p in self.policies.items() if any(has_pattern(s) for s in p["shell"]))
        self.assertTrue(agents, "no agent has this pattern, so the test proves nothing")
        return agents

    def assert_denied(self, agents, commands):
        for agent in agents:
            for command in commands:
                with self.subTest(agent=agent, command=command):
                    self.assertIsNotNone(self.decide(agent, command), f"{agent} must not run {command!r}")

    def assert_allowed(self, agents, commands):
        for agent in agents:
            for command in commands:
                with self.subTest(agent=agent, command=command):
                    self.assertIsNone(self.decide(agent, command))


class GitOutputWriteTest(ShellCase):
    """S1: an allowed git read command cannot write a file."""

    def test_git_log_cannot_write_a_file(self):
        self.assert_denied(self.agents_with(lambda p: p.startswith("git log")), [
            "git log -1 --format=x --output=src/Main.py",
            "git log --output src/Main.py",
            'git log -1 "--output=src/Main.py"',
        ])

    def test_git_diff_cannot_write_a_file(self):
        self.assert_denied(self.agents_with(lambda p: p.startswith("git diff")), [
            "git diff --output src/a.py",
            "git diff HEAD~1 --output=src/a.py",
            "git diff-tree -p HEAD --output=src/a.py",
        ])

    def test_git_show_cannot_write_a_file(self):
        self.assert_denied(self.agents_with(lambda p: p.startswith("git show")), [
            "git show HEAD --output=x",
            "git show --output x HEAD",
        ])

    def test_git_format_patch_cannot_write_files(self):
        agents = sorted(a for a in self.policies if self.decide(a, "git format-patch --stdout HEAD~1") is None)
        if not agents:
            self.skipTest("no agent can run git format-patch")
        self.assert_denied(agents, [
            "git format-patch -o out HEAD~1",
            "git format-patch --output-directory out HEAD~1",
            "git format-patch --output-directory=out HEAD~1",
        ])


class VerifyPatternCodeTest(ShellCase):
    """S2: the verify allow pattern runs only the verify script, not extra code before it."""

    def test_inline_code_before_the_verify_path_is_denied(self):
        self.assert_denied(self.agents_with(lambda p: "verify.py" in p), [
            '"python3" -c "import os" "x/verify.py" run',
            '"python3" -c "__import__(\'os\').system(\'python3 adapters/verify.py approve\')" "x/verify.py" run',
            '"python3" -c "import os" "x/verify.py" status',
        ])

    def test_another_script_before_the_verify_path_is_denied(self):
        self.assert_denied(self.agents_with(lambda p: "verify.py" in p), [
            '"python3" "tests/evil.py" "x/verify.py" run',
        ])


class ProtectHumanOnlyTest(ShellCase):
    """S3: the human-only commands stay blocked when the word is quoted or abbreviated."""

    def assert_blocked(self, commands):
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNotNone(self.protect(command), f"only the human runs {command!r}")

    def test_quoted_approve_is_human_only(self):
        self.assert_blocked([
            "python3 /x/verify.py 'approve'",
            'python3 /x/verify.py "approve" qa.w1-git-output-denied',
            "python3 /x/verify.py 'uninstall-hook'",
        ])

    def test_quoted_or_abbreviated_force_is_human_only(self):
        self.assert_blocked([
            "python3 /x/verify.py finish --forc",
            "python3 /x/verify.py finish --fo",
            f"python3 /x/verify.py start {WORK_ITEM} --forc",
            'python3 /x/verify.py finish "--force"',
        ])

    def test_magenta_uninstall_is_human_only(self):
        self.assert_blocked([
            "python3 magenta.py uninstall",
            "python3 magenta.py 'uninstall'",
        ])


class VerifyAbbreviationTest(unittest.TestCase):
    """S4: verify.py rejects an abbreviated option, so `--forc` is not `--force`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True, capture_output=True)

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "adapters" / "verify.py"), "--repo", str(self.repo), *args],
                              cwd=self.repo, capture_output=True, text=True)

    def test_finish_rejects_abbreviated_force(self):
        for option in ("--forc", "--fo"):
            with self.subTest(option=option):
                run = self.verify("finish", option)
                self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                self.assertIn(option, run.stderr)

    def test_finish_accepts_the_full_force_option(self):
        run = self.verify("finish", "--force")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


class QuotedSecretPathTest(ShellCase):
    """S5: a quoted secret path is still a secret path."""

    def test_quoted_secret_paths_are_denied(self):
        self.assert_denied(["architect", "qa"], [
            'git diff --no-index /dev/null ".env"',
            "git diff --no-index /dev/null '.env'",
            "git show HEAD:'secrets.pem'",
            'git show HEAD:"config/.env.prod"',
            "git log -p -- 'app/secrets/key.txt'",
        ])


class GitRunsNoProgramTest(ShellCase):
    """S8: an allowed git command cannot start a program that the agent selects."""

    def test_git_difftool_cannot_run_a_program(self):
        self.assert_denied(self.agents_with(lambda p: p.startswith("git diff")), [
            'git difftool -y -x "touch p" HEAD~1',
            "git difftool --extcmd=sh HEAD~1",
            'git difftool -y --extcmd "sh" HEAD~1',
            "git difftool -yxsh HEAD~1",
        ])

    def test_git_grep_cannot_open_the_files_in_a_program(self):
        self.assert_denied(self.agents_with(lambda p: p.startswith("git grep")), [
            "git grep -Osh x",
            "git grep --open-files-in-pager=sh x",
            "git grep -nOsh x",
        ])


class VerifyRealScriptTest(ShellCase):
    """S9: the verify allow patterns run only a Python interpreter and a verify.py outside the repository."""

    def setUp(self):
        self.repo_tmp = tempfile.TemporaryDirectory()
        self.unresolved = Path(self.repo_tmp.name)
        self.repo = self.unresolved.resolve()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True, capture_output=True)
        for name in ("verify.py", "docs/verify.py", "docs/runbooks/verify.py"):
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text("print('agent code')\n", encoding="utf-8")
        self.cwd = str(self.repo)

    def tearDown(self):
        self.repo_tmp.cleanup()

    def test_verify_py_inside_the_repository_is_denied(self):
        self.assert_denied(self.agents_with(lambda p: "verify.py" in p), [
            '"python3" "docs/runbooks/verify.py" run',
            '"python3" "./verify.py" run',
            f'"python3" "{self.repo.as_posix()}/docs/verify.py" run',
            f'"python3" "{self.unresolved.as_posix()}/docs/verify.py" run',
        ])

    def test_an_interpreter_that_is_not_python_is_denied(self):
        self.assert_denied(self.agents_with(lambda p: "verify.py" in p), [
            '"bash" "/opt/x/verify.py" run',
            '"sh" "/opt/x/skills/magenta/scripts/verify.py" run --set task',
        ])

    def test_python_and_a_verify_py_outside_the_repository_are_allowed(self):
        script = "/opt/x/skills/magenta/scripts/verify.py"
        self.assert_allowed(self.agents_with(lambda p: "verify.py" in p), [
            f'"{python}" "{script}" run --set task' for python in ("python3", "python", "py", "/usr/bin/python3")
        ])


class AllowedCommandsStayAllowedTest(ShellCase):
    """S6 (characterization): the commands that the agents use now stay allowed."""

    def test_git_read_commands_stay_allowed(self):
        self.assert_allowed(self.agents_with(lambda p: p.startswith("git log")), [
            "git log --oneline -5",
            "git log -1 --format=%H",
            "git log --oneline -- docs/output-format.md",
        ])
        self.assert_allowed(self.agents_with(lambda p: p.startswith("git diff")), [
            "git diff HEAD~1 -- src/a.py",
            "git diff --stat HEAD~1",
        ])
        self.assert_allowed(self.agents_with(lambda p: p.startswith("git show")), [
            "git show HEAD:src/a.py",
            "git show --stat HEAD",
        ])

    def test_git_grep_stays_allowed(self):
        self.assert_allowed(self.agents_with(lambda p: p.startswith("git grep")), ["git grep -n TODO -- src"])

    def test_verify_read_commands_stay_allowed(self):
        for sub, args in (("run", " --set task"), ("list", ""), ("status", "")):
            self.assert_allowed(self.agents_with(lambda p, s=sub: f'verify.py" {s}' in p), [
                f'"python3" "{VERIFY}" {sub}{args}',
                f'"C:/Python39/python.exe" "C:/Users/u/.claude/magenta/scripts/verify.py" {sub}{args}',
                f'"/usr/bin/python3" "/Users/John Doe/.claude/magenta/scripts/verify.py" {sub}{args}',
            ])

    def test_conductor_verify_commands_stay_allowed(self):
        for sub, args in (("start", f" {WORK_ITEM} --session abc"), ("finish", ""),
                          ("lock", f" {WORK_ITEM} tests/test_guard_bypass.py")):
            self.assert_allowed(self.agents_with(lambda p, s=sub: f'verify.py" {s}' in p), [
                f'"python3" "{VERIFY}" {sub}{args}',
            ])

    def test_protect_allows_the_normal_verify_and_magenta_commands(self):
        for command in ("python3 /x/verify.py run", "python3 /x/verify.py status", "python3 /x/verify.py list",
                        "python3 /x/verify.py run --set task", f'"python3" "{VERIFY}" run --set task',
                        "python3 /x/verify.py finish", f"python3 /x/verify.py start {WORK_ITEM} --session abc",
                        "python3 /x/verify.py start 20261030-approve-button --session abc",
                        "python3 magenta.py validate", "python3 magenta.py check"):
            with self.subTest(command=command):
                self.assertIsNone(self.protect(command))


if __name__ == "__main__":
    unittest.main()
