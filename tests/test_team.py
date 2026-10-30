"""Tests for the extended team (ADR-0013): roles, file ownership, and safe shell rules."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))

import guard  # noqa: E402
import source  # noqa: E402

NEW_ROLES = ("sre", "platform", "security", "database", "writer")


class TeamTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = source.load_config(ROOT)
        cls.agents = source.load_agents(ROOT, cfg["agents_enabled"])
        cls.policies = {a: source.policy(a, cls.agents[a]) for a in cls.agents}

    def decide(self, agent, tool, **tool_input):
        return guard.decide(agent, self.policies[agent], {"tool_name": tool, "tool_input": tool_input, "cwd": "/tmp/repo"})

    def can_write(self, agent, path):
        return self.decide(agent, "Write", file_path=path) is None

    def can_run(self, agent, command):
        return self.decide(agent, "Bash", command=command) is None

    def test_new_roles_are_enabled(self):
        for role in NEW_ROLES:
            self.assertIn(role, self.agents)

    def test_pipelines_and_infrastructure_belong_to_platform(self):
        for path in (".github/workflows/ci.yml", "Dockerfile", "services/api/Dockerfile", "infra/main.tf",
                     "charts/api/values.yaml", "k8s/deployment.yaml", "monitoring/alerts.rules.yml"):
            self.assertTrue(self.can_write("platform", path), path)
            self.assertFalse(self.can_write("engineer", path), path)
            self.assertFalse(self.can_write("frontend", path), path)
        self.assertFalse(self.can_write("platform", "src/main/java/App.java"))
        self.assertTrue(self.can_write("frontend", "src/components/charts/Bar.tsx"))  # not the root charts/ folder

    def test_platform_never_touches_live_systems(self):
        self.assertTrue(self.can_run("platform", "terraform validate"))
        self.assertTrue(self.can_run("platform", "hadolint Dockerfile"))
        for command in ("terraform apply", "terraform plan", "kubectl apply -f k8s/", "helm upgrade api charts/api",
                        "docker push registry/app:1", "git push origin main"):
            self.assertFalse(self.can_run("platform", command), command)
        self.assertFalse(self.can_write("platform", "infra/prod.tfvars"))
        self.assertIsNotNone(self.decide("platform", "Read", file_path="infra/terraform.tfstate"))

    def test_scanner_rules_belong_to_security(self):
        for path in (".trivyignore", ".semgrep.yml", ".gitleaks.toml"):
            self.assertTrue(self.can_write("security", path), path)
            self.assertFalse(self.can_write("engineer", path), path)
            self.assertFalse(self.can_write("platform", path), path)
        self.assertTrue(self.can_run("security", "gitleaks dir --redact ."))
        self.assertFalse(self.can_run("security", "gitleaks dir ."))  # secrets would show
        self.assertFalse(self.can_write("security", "src/main/java/App.java"))

    def test_checker_roles_write_only_their_checks_file(self):
        for role, own in (("sre", "sre"), ("security", "security"), ("database", "database")):
            self.assertTrue(self.can_write(role, f".magenta/checks/{own}.yaml"), role)
            self.assertFalse(self.can_write(role, ".magenta/checks/qa.yaml"), role)
        for maker in ("platform", "writer"):
            self.assertFalse(self.can_write(maker, ".magenta/checks/project.yaml"), maker)

    def test_database_plans_and_the_engineer_writes_migrations(self):
        migration = "src/main/resources/db/migration/V12__add_postal_code.sql"
        self.assertTrue(self.can_write("database", ".magenta/work/20261030-x/03-data.md"))
        self.assertFalse(self.can_write("database", migration))
        self.assertTrue(self.can_write("engineer", migration))

    def test_docs_ownership(self):
        self.assertTrue(self.can_write("writer", "docs/guide.md"))
        self.assertTrue(self.can_write("writer", "README.md"))
        self.assertTrue(self.can_write("writer", "CHANGELOG.md"))
        for path in ("docs/adr/0001-x.md", "docs/runbooks/api.md", "src/app.py"):
            self.assertFalse(self.can_write("writer", path), path)
        self.assertTrue(self.can_write("sre", "docs/runbooks/api.md"))
        self.assertFalse(self.can_write("engineer", "docs/postmortems/2026-10-30.md"))

    def test_routing_knows_the_new_roles(self):
        routing = (ROOT / "workflows" / "routing.md").read_text(encoding="utf-8")
        for task_type in ("| infrastructure |", "| reliability |", "| data |", "| docs |"):
            self.assertIn(task_type, routing)
        for lens in ("| SRE |", "| Security |", "| Database |"):
            self.assertIn(lens, routing)
        for playbook in ("infrastructure", "reliability", "docs"):
            self.assertTrue((ROOT / "workflows" / f"{playbook}.md").exists(), playbook)


if __name__ == "__main__":
    unittest.main()
