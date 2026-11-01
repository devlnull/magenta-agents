"""The guard modes (standard and strict), container options, and nested repositories in a git workspace."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))

import guard  # noqa: E402
import source  # noqa: E402


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ModeCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = source.load_config(ROOT)
        agents = source.load_agents(ROOT, cfg["agents_enabled"])
        cls.policies = {a: source.policy(a, agents[a]) for a in agents}

    def setUp(self):
        self.env = mock.patch.dict(os.environ)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("MAGENTA_GUARD", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.cwd)], check=True)
        (self.cwd / ".magenta").mkdir()

    def write_file(self, agent, path, cwd=None):
        event = {"tool_name": "Write", "tool_input": {"file_path": str(path)}, "cwd": str(cwd or self.cwd)}
        return guard.decide(agent, self.policies[agent], event)

    def shell(self, agent, command, cwd=None):
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd or self.cwd)}
        return guard.decide(agent, self.policies[agent], event)

    def policy(self, data):
        write(self.cwd / ".magenta" / "policy.json", json.dumps(data))

    def lock(self, *files):
        write(self.cwd / ".magenta" / "work" / "1-x" / "acceptance.lock",
              json.dumps({"patterns": list(files), "files": {f: "0" * 64 for f in files}}))


class StandardWritesTest(ModeCase):
    def test_the_code_is_free(self):
        for agent in ("engineer", "qa", "principal", "sre", "architect"):
            with self.subTest(agent=agent):
                self.assertIsNone(self.write_file(agent, "src/Payment/Save.php"))
        self.assertIsNone(self.write_file("engineer", "tests/Unit/SomeTest.php"))  # not locked

    def test_the_process_files_keep_their_owners(self):
        self.assertIn("cannot write", self.write_file("engineer", ".magenta/checks/qa.yaml"))
        self.assertIn("cannot write", self.write_file("qa", ".magenta/checks/project.yaml"))
        self.assertIsNone(self.write_file("principal", ".magenta/checks/project.yaml"))
        self.assertIsNone(self.write_file("qa", ".magenta/work/1-x/05-test-plan.md"))
        for name in (".magenta/policy.json", ".claude/settings.local.json", ".git/config"):
            with self.subTest(name=name):
                self.assertIn("Only the human", self.write_file("principal", name))

    def test_the_explicit_denies_of_a_role_stay(self):
        self.assertIn("another role owns it", self.write_file("engineer", "docs/adr/0009-x.md"))
        self.assertIn("another role owns it", self.write_file("engineer", "Dockerfile"))
        self.assertIn("another role owns it", self.write_file("engineer", ".github/workflows/ci.yml"))

    def test_makers_cannot_write_a_locked_test(self):
        self.lock("tests/Unit/Payment/SaveTest.php")
        self.assertIn("sealed", self.write_file("engineer", "tests/Unit/Payment/SaveTest.php"))
        self.assertIn("sealed", self.write_file("frontend", "tests/Unit/Payment/SaveTest.php"))
        self.assertIsNone(self.write_file("qa", "tests/Unit/Payment/SaveTest.php"))  # its owner
        self.assertIsNone(self.write_file("engineer", "tests/Unit/Payment/OtherTest.php"))

    def test_secrets_stay_blocked(self):
        for name in (".env", ".ssh/id_rsa", "deploy/id_ed25519", "certs/app.p12", ".netrc"):
            with self.subTest(name=name):
                self.assertIn("secret", self.write_file("engineer", name))


class StrictModeTest(ModeCase):
    def test_policy_json_selects_strict(self):
        self.policy({"guard": "strict"})
        self.assertIn("cannot write", self.write_file("principal", "src/Payment/Save.php"))
        self.assertIn("cannot run", self.shell("engineer", "curl http://localhost:8080/health"))

    def test_the_environment_wins_and_an_unknown_mode_is_strict(self):
        self.policy({"guard": {"mode": "standard"}})
        os.environ["MAGENTA_GUARD"] = "strict"
        self.assertIsNotNone(self.write_file("principal", "src/A.php"))
        os.environ["MAGENTA_GUARD"] = "relaxed"
        self.assertIsNotNone(self.write_file("principal", "src/A.php"))
        os.environ.pop("MAGENTA_GUARD")
        self.assertIsNone(self.write_file("principal", "src/A.php"))


class StandardShellTest(ModeCase):
    def test_normal_commands_run(self):
        for command in ("curl http://localhost:8080/health", "composer dump-autoload", "php -l src/A.php",
                        "grep -rn PaymentSave src", "git checkout -b feat/x", "git commit -m wip",
                        f"docker run --rm -v {self.cwd.as_posix()}:/app -w /app php:8.3-cli php vendor/bin/phpunit"):
            with self.subTest(command=command):
                self.assertIsNone(self.shell("engineer", command))

    def test_dangerous_commands_are_blocked(self):
        for command in ("git push origin main", "git reset --hard HEAD~1", "git stash", "git checkout -- src",
                        "git restore src/A.php", "git clean -fd", "rm -rf build", "kubectl get pods",
                        "gh pr create", "terraform plan", "sudo ls", "pip install requests", "docker rm -f app"):
            with self.subTest(command=command):
                self.assertIsNotNone(self.shell("engineer", command))

    def test_a_human_pattern_allows_a_dangerous_command(self):
        self.policy({"engineer": {"shell": ["gh pr view*"]}})
        self.assertIsNone(self.shell("engineer", "gh pr view 12"))
        self.assertIsNotNone(self.shell("engineer", "gh pr create"))

    def test_human_only_files_cannot_be_named(self):
        for command in ("sed -i s/a/b/ .magenta/policy.json", "cat .claude/settings.local.json",
                        "cp x .git/hooks/pre-commit"):
            with self.subTest(command=command):
                self.assertIn("Only the human", self.shell("engineer", command))

    def test_an_agent_without_shell_has_no_shell(self):
        self.assertIn("no shell", self.shell("product-manager", "ls"))

    def test_the_inline_code_and_operator_rules_stay(self):
        self.assertIsNotNone(self.shell("engineer", "php -r 'echo 1'"))
        self.assertIsNotNone(self.shell("engineer", "ls; rm -rf src"))


class ContainerTest(ModeCase):
    def run_in_docker(self, options):
        return self.shell("engineer", f"docker run --rm {options} php:8.3-cli php vendor/bin/phpunit")

    def test_mounts_outside_the_project_are_blocked(self):
        home = Path(self.tmp.name).resolve().parent
        self.assertIn("outside the project", self.run_in_docker(f"-v {home.as_posix()}:/h"))
        self.assertIn("outside the project", self.run_in_docker("-v /:/host"))
        self.assertIn("outside the project", self.run_in_docker("--mount type=bind,source=/,target=/host"))
        self.assertIn("outside the project", self.run_in_docker(f"--volume={home.as_posix()}:/h:ro"))

    def test_host_options_and_the_docker_socket_are_blocked(self):
        self.assertIn("--privileged", self.run_in_docker("--privileged"))
        self.assertIn("host", self.run_in_docker("--pid host"))
        self.assertIn("container socket", self.run_in_docker("-v /var/run/docker.sock:/var/run/docker.sock"))

    def test_project_mounts_and_named_volumes_are_allowed(self):
        self.assertIsNone(self.run_in_docker(f"-v {self.cwd.as_posix()}:/app -w /app"))
        self.assertIsNone(self.run_in_docker("-v ./src:/app/src"))
        self.assertIsNone(self.run_in_docker("-v cache:/root/.composer"))
        self.assertIn("secret", self.run_in_docker("-v ./.ssh:/s"))

    def test_the_application_that_holds_the_package_and_the_human_mounts(self):
        app = Path(self.tmp.name).resolve() / "app"
        package = app / "vendor" / "shop" / "omc"
        package.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(app)], check=True)
        subprocess.run(["git", "init", "-q", str(package)], check=True)
        command = f"docker run --rm -v {app.as_posix()}:/app -w /app php:8.3-cli php vendor/bin/phpunit"
        self.assertIsNone(self.shell("engineer", command, cwd=package))
        shared = tempfile.TemporaryDirectory()
        self.addCleanup(shared.cleanup)
        other = Path(shared.name).resolve()
        command = f"docker run --rm -v {other.as_posix()}:/shared php:8.3-cli php vendor/bin/phpunit"
        self.assertIsNotNone(self.shell("engineer", command))
        self.policy({"mounts": [other.as_posix()]})
        self.assertIsNone(self.shell("engineer", command))

    def test_a_secret_inside_the_container_is_blocked(self):
        command = f"docker run --rm -v {self.cwd.as_posix()}:/app php:8.3-cli php /app/.ssh/id_rsa"
        self.assertIn("secret", self.shell("engineer", command))


class NestedRepositoryTest(ModeCase):
    """The session starts in an application (a git repository). The Magenta repository is a package in vendor/."""

    def setUp(self):
        super().setUp()
        self.package = self.cwd / "vendor" / "shopping" / "omc"
        (self.package / ".magenta" / "checks").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.package)], check=True)
        (self.cwd / ".magenta").rmdir()  # the application itself is not a Magenta repository

    def test_the_human_only_files_of_the_package_are_protected(self):
        for name in (".magenta/policy.json", ".magenta/checks.lock", ".claude/settings.local.json"):
            with self.subTest(name=name):
                self.assertIn("Only the human", self.write_file("engineer", self.package / name))
        self.assertIn("cannot write", self.write_file("engineer", self.package / ".magenta/checks/qa.yaml"))

    def test_the_owners_write_their_files_in_the_package(self):
        self.assertIsNone(self.write_file("principal", self.package / ".magenta/checks/project.yaml"))
        self.assertIsNone(self.write_file("qa", self.package / ".magenta/checks/qa.yaml"))
        self.assertIsNone(self.write_file("qa", self.package / "tests/Unit/XTest.php"))
        os.environ["MAGENTA_GUARD"] = "strict"
        self.assertIsNone(self.write_file("qa", self.package / "tests/Unit/XTest.php"))
        self.assertIsNotNone(self.write_file("qa", self.package / "src/X.php"))

    def test_the_policy_of_the_package_applies(self):
        write(self.package / ".magenta" / "policy.json", json.dumps({"guard": "strict"}))
        self.assertIsNotNone(self.write_file("principal", self.package / "src/X.php"))
        self.assertIsNone(self.write_file("principal", self.cwd / "src/X.php"))  # the application: standard


if __name__ == "__main__":
    unittest.main()
