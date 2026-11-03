"""The driver model (ADR-0016): each task type has a driver and a different checker, and the conductor keeps the
process."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters"))

import source  # noqa: E402

ROUTING = (ROOT / "workflows" / "routing.md").read_text(encoding="utf-8")
CONDUCTOR = (ROOT / "skills" / "magenta" / "SKILL.md").read_text(encoding="utf-8")


def table(heading):
    part = ROUTING.split(f"### {heading}\n", 1)[1].split("\n### ", 1)[0]
    rows = [r for r in part.splitlines() if r.startswith("| ") and not r.startswith("|---")]
    return [[c.strip() for c in r.strip("|").split("|")] for r in rows[1:]]


class DriverTableTest(unittest.TestCase):
    def setUp(self):
        self.agents = set(source.load_config(ROOT)["agents_enabled"])
        self.drivers = {}
        for types, driver, checker in table("Driver"):
            for task_type in re.split(r",\s*", types):
                first = re.match(r"`([a-z-]+)`", checker)
                self.drivers[task_type] = (driver.strip("`"), first.group(1) if first else checker)

    def test_each_task_type_has_one_driver_and_another_checker(self):
        task_types = {row[0] for row in table("Task types")}
        self.assertEqual(set(self.drivers), task_types)
        for task_type, (driver, checker) in self.drivers.items():
            with self.subTest(task_type=task_type):
                self.assertIn(driver, self.agents)
                self.assertNotEqual(driver, checker)
                self.assertTrue(checker in self.agents or "lenses" in checker or "owner" in checker, checker)

    def test_the_expected_drivers(self):
        expected = {"tests": "qa", "design": "architect", "incident": "sre", "reliability": "sre",
                    "security": "security", "data": "database", "infrastructure": "platform", "docs": "writer",
                    "bug": "principal", "feature": "principal", "performance": "principal"}
        for task_type, driver in expected.items():
            self.assertEqual(self.drivers[task_type][0], driver, task_type)

    def test_the_protections_are_written(self):
        for text in ("The driver keeps the owners.", "An incident is mitigated first.", "One domain.", "Small tasks have no plan step.", "The conductor keeps the process.",
                     "Evidence can change the driver.", "`--driver none`", "The checker is another role, without extra steps."):
            self.assertIn(text, ROUTING)


class ConductorTest(unittest.TestCase):
    def test_the_conductor_selects_the_driver(self):
        self.assertIn("[--driver <role>]", CONDUCTOR)
        self.assertIn("**The plan of the driver**", CONDUCTOR)
        self.assertIn("## Domain questions", CONDUCTOR)
        self.assertIn("Do not ask the human about the driver", CONDUCTOR)

    def test_all_agents_get_the_driver_rule_and_the_templates_have_the_driver(self):
        rules = (ROOT / "rules" / "70-driver.md").read_text(encoding="utf-8")
        self.assertIn("Do not grow the scope yourself", rules)
        self.assertIn("- Driver:", (ROOT / "templates" / "brief.md").read_text(encoding="utf-8"))
        self.assertIn("## Domain decisions", (ROOT / "templates" / "plan.md").read_text(encoding="utf-8"))
        for agent in sorted((ROOT / "plugins" / "magenta" / "agents").glob("*.md")):
            self.assertIn("Rule: driver", agent.read_text(encoding="utf-8"), agent.name)


if __name__ == "__main__":
    unittest.main()
