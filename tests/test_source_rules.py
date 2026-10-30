import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))

import guard
import source

SPECIALISTS = (r"\bSRE\b", r"(?i)\bsecurity\b", r"(?i)\bdatabase\b")
TEAM_ALIASES = {"pm": "product-manager", "product manager": "product-manager", "front-end": "frontend",
                "technical writer": "writer", "site reliability engineer": "sre"}


def read_lines(relative):
    return (ROOT / relative).read_text(encoding="utf-8").splitlines()


def section(relative, heading):
    lines = read_lines(relative)
    level = len(heading.split(" ")[0])
    start = next((i for i, line in enumerate(lines) if line.startswith(heading)), None)
    if start is None:
        raise AssertionError(f"{relative}: the heading {heading!r} is missing")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"#{1,%d} " % level, lines[i])), len(lines))
    return lines[start + 1:end]


def table_rows(lines):
    rows = []
    for line in lines:
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().split("|")[1:-1]]
        if cells and not set("".join(cells)) <= set("-: "):
            rows.append(cells)
    return rows[1:]


def row(rows, first):
    found = [r for r in rows if r[0] == first]
    if not found:
        raise AssertionError(f"the table has no row {first!r}")
    return found[0]


def numbered_steps(lines):
    blocks, current = [], None
    for line in lines:
        match = re.match(r"(\d+[a-z]?)\.\s", line)
        if match:
            current = [match.group(1), line]
            blocks.append(current)
        elif current is not None and line.startswith((" ", "\t")) and line.strip():
            current.append(line)
        else:
            current = None
    return [(block[0], "\n".join(block[1:])) for block in blocks]


def team_ids(cell):
    ids = set()
    for name in re.split(r",|\bor\b|\band\b", cell):
        name = TEAM_ALIASES.get(name.strip().strip(".").lower(), name.strip().strip(".").lower())
        if name.endswith(" engineer"):
            name = name[:-len(" engineer")]
        if name:
            ids.add(TEAM_ALIASES.get(name, name))
    return ids


class W6FullReadinessStepTest(unittest.TestCase):
    def test_full_lane_names_the_final_review_step_of_the_standard_lane(self):
        final = [n for n, text in numbered_steps(read_lines("workflows/standard.md"))
                 if "`principal`: final review" in text]
        self.assertEqual(len(final), 1, "standard.md must have one step '`principal`: final review'")
        readiness = [line for line in read_lines("workflows/full.md") if "Step" in line and "readiness" in line]
        self.assertTrue(readiness, "full.md must name the step of the readiness review")
        for line in readiness:
            self.assertEqual(re.findall(r"Step (\d+[a-z]?)\b", line), [final[0]], line)


class W6StandardLanePrdForFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.lines = read_lines("workflows/standard.md")
        self.steps = numbered_steps(self.lines)

    def test_prd_review_and_gate_1_apply_to_features_only(self):
        for needle in ("PRD review", "Gate 1"):
            texts = [text for _, text in self.steps if needle in text]
            self.assertTrue(texts, f"standard.md has no step with {needle!r}")
            for text in texts:
                with self.subTest(step=text):
                    self.assertIn("feature", text.lower())

    def test_database_writes_the_data_plan_before_the_design_gate(self):
        data = [i for i, line in enumerate(self.lines) if "03-data.md" in line]
        self.assertTrue(data, "standard.md must name 03-data.md")
        gate2 = [i for i, line in enumerate(self.lines) if re.match(r"\d+[a-z]?\.\s", line) and "Gate 2" in line]
        self.assertTrue(gate2, "standard.md has no Gate 2 step")
        line = self.lines[data[0]]
        self.assertIn("`database`", line)
        self.assertTrue(data[0] < gate2[0] or "Gate 2" in line, line)

    def test_security_sre_and_writer_can_join(self):
        text = "\n".join(self.lines)
        for name in ("`security`", "`sre`", "`writer`"):
            with self.subTest(agent=name):
                self.assertIn(name, text)


class W6TemplatesAndLedgersNameTheNewRolesTest(unittest.TestCase):
    def assert_specialists(self, text):
        for pattern in SPECIALISTS:
            with self.subTest(pattern=pattern):
                self.assertRegex(text, pattern)

    def test_brief_template_lists_every_routing_task_type(self):
        types = [r[0] for r in table_rows(section("workflows/routing.md", "### Task types"))]
        self.assertTrue(types)
        line = next((line for line in read_lines("templates/brief.md") if "Task type:" in line), "")
        words = set(re.findall(r"[a-z][a-z-]*", line))
        for task_type in types:
            with self.subTest(task_type=task_type):
                self.assertIn(task_type, words)

    def test_plan_template_ledger_names_the_specialists(self):
        self.assert_specialists("\n".join(section("templates/plan.md", "## Constraint ledger")))

    def test_routing_ledger_has_specialist_rows(self):
        rows = table_rows(section("workflows/routing.md", "### Constraint ledger"))
        self.assert_specialists("\n".join(r[0] for r in rows))

    def test_principal_step_4a_names_the_specialists(self):
        line = next((line for line in read_lines("agents/principal.md") if line.startswith("4a.")), "")
        self.assertTrue(line, "principal.md has no step 4a")
        self.assert_specialists(line)


class W6DocsListTheTeamTest(unittest.TestCase):
    def assert_names_every_enabled_agent(self, relative):
        text = "\n".join(read_lines(relative))
        for agent in source.load_config(ROOT)["agents_enabled"]:
            with self.subTest(doc=relative, agent=agent):
                self.assertRegex(text, rf"magenta[:-]{re.escape(agent)}\b")

    def test_onboarding_names_every_enabled_agent(self):
        self.assert_names_every_enabled_agent("docs/onboarding.md")

    def test_guide_names_every_enabled_agent(self):
        self.assert_names_every_enabled_agent("docs/guide.md")

    def test_guide_core_teams_of_security_and_incident_match_routing(self):
        routing = table_rows(section("workflows/routing.md", "### Task types"))
        guide = table_rows(section("docs/guide.md", "## Task types"))
        for task_type in ("security", "incident"):
            with self.subTest(task_type=task_type):
                expected = set(re.findall(r"`([a-z-]+)`", row(routing, task_type)[3]))
                self.assertEqual(team_ids(row(guide, task_type)[-1]), expected)


class W6ReviewPanelLensesTest(unittest.TestCase):
    def test_routing_review_rows_name_the_specialist_lenses(self):
        task_row = row(table_rows(section("workflows/routing.md", "### Task types")), "review")
        mode_row = row(table_rows(section("workflows/routing.md", "### Modes")), "review")
        text = " ".join(task_row + mode_row)
        for pattern in (r"(?i)\bsre\b", r"(?i)\bsecurity\b", r"(?i)\bdatabase\b"):
            with self.subTest(pattern=pattern):
                self.assertRegex(text, pattern)

    def test_pr_review_names_the_specialist_reviewers(self):
        text = "\n".join(read_lines("workflows/pr-review.md"))
        for name in ("`security`", "`sre`", "`database`"):
            with self.subTest(agent=name):
                self.assertIn(name, text)


class W6GatesTest(unittest.TestCase):
    def state_gates(self):
        text = "\n".join(read_lines("templates/state.yaml"))
        return set(re.findall(r"^\s+([a-z][a-z-]*):\s*\{", text, re.M))

    def test_state_template_has_checks_plan_and_done_gates(self):
        self.assertTrue({"checks", "plan", "done"} <= self.state_gates(), self.state_gates())

    def test_lite_lane_gates_agree_with_routing(self):
        lite = row(table_rows(section("workflows/routing.md", "### Lanes")), "lite")[-1]
        routing_gates = {name.lower() for name in re.findall(r"([A-Za-z-]+) gate\b", lite)}
        configured = set(source.load_config(ROOT)["lanes"]["lite"]["gates"])
        self.assertEqual(configured, routing_gates)

    def test_every_lane_gate_is_in_the_state_template(self):
        for lane, spec in source.load_config(ROOT)["lanes"].items():
            with self.subTest(lane=lane):
                self.assertTrue(set(spec["gates"]) <= self.state_gates(), spec["gates"])


class W6SpecialistTestRequestsGoToQaTest(unittest.TestCase):
    def test_step_3_gives_the_specialist_test_requests_to_qa_before_the_lock(self):
        lines = section("skills/magenta/SKILL.md", "## Step 3")
        requests = [i for i, line in enumerate(lines) if "test request" in line.lower()]
        self.assertTrue(requests, "Step 3 must name the test requests of the specialists")
        lock = [i for i, line in enumerate(lines) if 'verify.py" lock' in line]
        self.assertTrue(lock, "Step 3 has no lock command")
        self.assertLess(requests[0], lock[0])
        self.assertRegex(lines[requests[0]], r"QA|`qa`")


class _GuardCase(unittest.TestCase):
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

    def assert_allowed(self, agent, commands):
        for command in commands:
            with self.subTest(agent=agent, command=command):
                self.assertIsNone(self.decide(agent, command))

    def assert_denied(self, agent, commands):
        for command in commands:
            with self.subTest(agent=agent, command=command):
                self.assertIsNotNone(self.decide(agent, command), f"{agent} must not run {command!r}")


class W7QaTestCommandsTest(_GuardCase):
    def test_qa_runs_the_test_commands_of_the_supported_stacks(self):
        self.assert_allowed("qa", [
            './gradlew :api:test --tests "*X"',
            "mvn -pl api test",
            "yarn test",
            "pnpm test",
            "vendor/bin/phpunit",
            "php artisan test",
            "cargo test",
            "make test",
            "python -m pytest",
            "python3 -m unittest",
            "python3 -m unittest discover -s tests",
        ])

    def test_qa_commits_its_tests(self):
        self.assert_allowed("qa", [
            "git add tests/test_orders.py",
            'git commit -m "Add the acceptance tests"',
        ])


class W7SreLintCommandsTest(_GuardCase):
    def test_sre_runs_the_lint_and_validate_commands(self):
        self.assert_allowed("sre", [
            "terraform fmt -check",
            "terraform init -backend=false",
            "terraform validate",
            "tflint",
            "checkov -d .",
            "shellcheck install.sh",
            "docker compose config",
        ])

    def test_sre_cannot_change_live_infrastructure(self):
        self.assert_denied("sre", [
            "terraform apply",
            "terraform apply -auto-approve",
            "terraform plan",
            "terraform plan -out=tfplan",
            "terraform destroy",
        ])


class W7PmCommitShaTest(_GuardCase):
    def test_rules_say_that_the_brief_gives_the_sha_to_agents_without_a_shell(self):
        lines = [line for line in read_lines("rules/40-communication.md")
                 if "SHA" in line and "brief" in line.lower() and "without a shell" in line.lower()]
        self.assertTrue(lines, "rules/40-communication.md must say that the brief gives the commit SHA "
                               "to agents without a shell")

    def test_product_manager_still_has_no_shell(self):
        self.assertEqual(self.policies["product-manager"]["shell"], [])
        self.assert_denied("product-manager", ["git rev-parse --short HEAD"])


class W7EngineerPythonStdlibTest(_GuardCase):
    def test_engineer_runs_the_unittest_commands(self):
        self.assert_allowed("engineer", [
            "python3 -m unittest",
            "python3 -m unittest discover -s tests",
            "python3 -m unittest tests.test_team",
        ])


class W7NoNewBypassTest(_GuardCase):
    def test_shell_operators_stay_denied(self):
        self.assert_denied("sre", [
            "terraform validate; terraform apply",
            "terraform validate && terraform apply",
            "tflint | tee report.txt",
            "terraform validate > out.txt",
            "checkov -d . $(touch x)",
        ])
        self.assert_denied("qa", [
            "python3 -m unittest; git push",
            "yarn test && git push origin main",
        ])
        self.assert_denied("engineer", [
            "python3 -m unittest; rm -rf src",
            "python3 -m unittest | tee out.txt",
        ])

    def test_git_output_options_stay_denied(self):
        for agent in ("qa", "sre"):
            self.assert_denied(agent, [
                "git log --output=x",
                "git log -1 --format=x --output=src/Main.py",
                "git diff --output=x",
            ])

    def test_sre_does_not_rewrite_files_or_reach_a_backend(self):
        self.assert_denied("sre", [
            "terraform fmt",
            "terraform fmt -recursive",
            "terraform init",
            "docker compose up -d",
        ])

    def test_qa_cannot_push_or_publish(self):
        self.assert_denied("qa", [
            "git push origin main",
            "npm publish",
            "cargo publish",
        ])


if __name__ == "__main__":
    unittest.main()
