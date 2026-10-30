import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))

import guard  # noqa: E402
import source  # noqa: E402
from common import parse_yaml, split_front_matter  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

LITERAL_CASES = [
    ("inner indentation", "code: |\n  def f():\n      return 1\nnext: 2\n",
     {"code": "def f():\n    return 1\n", "next": 2}),
    ("final newline", "a: |\n  x\n  y\nb: 1\n", {"a": "x\ny\n", "b": 1}),
    ("clip keeps one newline", "a: |\n  x\n\n\nb: 1\n", {"a": "x\n", "b": 1}),
    ("inner empty line", "a: |\n  x\n\n  y\n", {"a": "x\n\ny\n"}),
    ("hash is content", "a: |\n  x # not a comment\n", {"a": "x # not a comment\n"}),
    ("list item map", "checks:\n  - id: a\n    command: |\n      echo a\n        echo b\n    why: w\n",
     {"checks": [{"id": "a", "command": "echo a\n  echo b\n", "why": "w"}]}),
    ("strip keeps indentation", "a: |-\n  x\n    y\nb: 1\n", {"a": "x\n  y", "b": 1}),
]
LITERAL_STILL_WORKS = [
    ("strip flat", "a: |-\n  x\n  y\n", {"a": "x\ny"}),
]
FOLDED_CASES = [
    ("one empty line", "a: >-\n  one\n  two\n\n  three\n", {"a": "one two\nthree"}),
    ("two empty lines", "a: >-\n  one\n\n\n  two\nb: 1\n", {"a": "one\n\ntwo", "b": 1}),
]
FOLDED_STILL_WORKS = [
    ("no empty line", "a: >-\n  one\n  two\nb: 1\n", {"a": "one two", "b": 1}),
]
COMMENT_CASES = [
    ("apostrophe in map value", "command: echo it's #1\n", {"command": "echo it's"}),
    ("apostrophe in list item", "- echo it's #1\n- b\n", ["echo it's", "b"]),
    ("apostrophe then next key", "a: don't stop # note\nb: 2\n", {"a": "don't stop", "b": 2}),
    ("double quote inside plain value", 'a: 6" pipe # note\n', {"a": '6" pipe'}),
]
COMMENT_STILL_WORKS = [
    ("double-quoted hash", 'a: "x # y"  # note\n', {"a": "x # y"}),
    ("single-quoted escape", "a: 'it''s #1'  # note\n", {"a": "it's #1"}),
    ("hash without space", "a: x#y\n", {"a": "x#y"}),
    ("apostrophe in comment", "a: x # it's\n", {"a": "x"}),
]
CRLF_FRONT_MATTER = "name: x\r\ndescription: >-\r\n  one\r\n  two\r\n"
CRLF_META = {"name": "x", "description": "one two"}

COPY_SKIP = (".git", "dist", "plugins", ".claude-plugin", ".magenta", "evals", "__pycache__")


def _validate_copy(edit=None):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "src"
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(*COPY_SKIP))
        if edit:
            edit(root)
        env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        env.pop("MAGENTA_DIST", None)
        return subprocess.run([sys.executable, str(root / "magenta.py"), "validate"], cwd=str(root),
                              capture_output=True, text=True, env=env, timeout=60)


def _add_write(agent, glob):
    def edit(root):
        path = root / "agents" / f"{agent}.md"
        text = path.read_text(encoding="utf-8")
        assert "  writes:\n" in text, path
        path.write_text(text.replace("  writes:\n", f'  writes:\n    - "{glob}"\n', 1), encoding="utf-8")
    return edit


def _append(rel, line):
    def edit(root):
        path = root / rel
        path.write_text(path.read_text(encoding="utf-8") + f"\n{line}\n", encoding="utf-8")
    return edit


class _ParserCases(unittest.TestCase):
    def assert_cases(self, cases):
        for name, text, expected in cases:
            with self.subTest(name):
                self.assertEqual(parse_yaml(text), expected)


class W4S1LiteralBlockTest(_ParserCases):
    def test_literal_block_keeps_relative_indentation_and_final_newline(self):
        self.assert_cases(LITERAL_CASES)

    def test_literal_strip_block_still_works(self):
        self.assert_cases(LITERAL_STILL_WORKS)


class W4S2FoldedBlockTest(_ParserCases):
    def test_folded_block_keeps_empty_line_as_newline(self):
        self.assert_cases(FOLDED_CASES)

    def test_folded_block_without_empty_line_still_works(self):
        self.assert_cases(FOLDED_STILL_WORKS)


class W4S3CommentAfterApostropheTest(_ParserCases):
    def test_comment_after_apostrophe_is_dropped(self):
        self.assert_cases(COMMENT_CASES)

    def test_quoted_values_and_comments_still_work(self):
        self.assert_cases(COMMENT_STILL_WORKS)


class W4S4CrlfFrontMatterTest(unittest.TestCase):
    def test_crlf_front_matter_is_accepted(self):
        meta, body = split_front_matter(f"---\r\n{CRLF_FRONT_MATTER}---\r\n# Body\r\n")
        self.assertEqual(meta, CRLF_META)
        self.assertEqual(body.splitlines(), ["# Body"])

    def test_crlf_front_matter_without_body_is_accepted(self):
        meta, body = split_front_matter("---\r\nname: x\r\n---\r\n")
        self.assertEqual(meta, {"name": "x"})
        self.assertEqual(body.strip(), "")

    def test_lf_front_matter_still_works(self):
        self.assertEqual(split_front_matter("---\nname: x\n---\n# Body\n"), ({"name": "x"}, "# Body\n"))

    def test_missing_front_matter_still_fails(self):
        with self.assertRaises(ValueError):
            split_front_matter("# Body\r\n")


class W4S5PyYamlCrossCheckTest(unittest.TestCase):
    def test_ci_installs_pyyaml_in_a_job_that_runs_the_unit_tests(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        jobs = re.split(r"(?m)^  (?=[A-Za-z0-9_-]+:\s*$)", text.split("\njobs:\n", 1)[1])
        self.assertTrue(any(re.search(r"pip install[^\n]*\bpyyaml\b", job, re.I) and "unittest" in job
                            for job in jobs), "no CI job installs pyyaml and runs the unit tests")

    def test_pyyaml_cross_check_covers_the_checks_template(self):
        segments = []
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            if path.name == Path(__file__).name:
                continue
            text = path.read_text(encoding="utf-8")
            segments += [ast.get_source_segment(text, node) or "" for node in ast.walk(ast.parse(text))
                         if isinstance(node, ast.ClassDef)]
        cross_checks = [s for s in segments if "safe_load" in s]
        self.assertTrue(cross_checks, "no test class calls yaml.safe_load")
        self.assertTrue(any("checks.yaml" in s for s in cross_checks),
                        "the PyYAML cross-check does not cover templates/checks.yaml")

    @unittest.skipIf(yaml is None, "PyYAML is not installed")
    def test_expected_values_agree_with_pyyaml(self):
        for name, text, expected in (LITERAL_CASES + LITERAL_STILL_WORKS + FOLDED_CASES + FOLDED_STILL_WORKS
                                     + COMMENT_CASES + COMMENT_STILL_WORKS
                                     + [("crlf front matter", CRLF_FRONT_MATTER, CRLF_META)]):
            with self.subTest(name):
                self.assertEqual(yaml.safe_load(text), expected)


class W5S1OverlappingWriteGlobsTest(unittest.TestCase):
    def test_validate_passes_on_the_unchanged_source(self):
        run = _validate_copy()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("Validation passed.", run.stdout)

    def test_validate_fails_when_non_maker_globs_overlap(self):
        for glob in ("docs/**", "docs/adr/decisions/**"):
            with self.subTest(glob):
                run = _validate_copy(_add_write("product-manager", glob))
                self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn("product-manager", run.stdout)

    def test_validate_fails_on_wildcard_under_magenta_checks(self):
        run = _validate_copy(_add_write("product-manager", ".magenta/checks/pm-*.yaml"))
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("product-manager", run.stdout)


class W5S2UnknownSkillReferencesTest(unittest.TestCase):
    def test_validate_finds_unknown_skill_in_skills_a_and_b(self):
        for line, unknown in (("Use the skills `tdd-cycle` and `no-such-skill-zz`.", "no-such-skill-zz"),
                              ("Use the skills `no-such-skill-xx` and `tdd-cycle`.", "no-such-skill-xx")):
            with self.subTest(line):
                run = _validate_copy(_append("workflows/bugfix.md", line))
                self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn(unknown, run.stdout)

    def test_validate_finds_unknown_prefixed_skill_name(self):
        run = _validate_copy(_append("workflows/bugfix.md", "Read `magenta-no-such-skill-yy` first."))
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("no-such-skill-yy", run.stdout)


class _Policies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = source.load_config(ROOT)
        cls.agents = source.load_agents(ROOT, cfg["agents_enabled"])
        cls.policies = {a: source.policy(a, cls.agents[a]) for a in cls.agents}
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def can_write(self, agent, path):
        event = {"tool_name": "Write", "tool_input": {"file_path": path}, "cwd": self.tmp.name}
        return guard.decide(agent, self.policies[agent], event) is None

    def writers(self, path):
        return {agent for agent in self.policies if self.can_write(agent, path)}


class W5S3NestedPlatformPathsTest(_Policies):
    def test_platform_writes_nested_k8s_manifest(self):
        self.assertTrue(self.can_write("platform", "services/a/k8s/x.yaml"))

    def test_makers_cannot_write_nested_k8s_manifest(self):
        for maker in ("engineer", "frontend"):
            self.assertFalse(self.can_write(maker, "services/a/k8s/x.yaml"), maker)

    def test_root_k8s_manifest_still_belongs_to_platform(self):
        self.assertEqual(self.writers("k8s/x.yaml"), {"platform"})


class W5S4SingleOwnerPathsTest(_Policies):
    def test_only_sre_writes_root_runbooks(self):
        self.assertEqual(self.writers("runbooks/a.md"), {"sre"})

    def test_only_architect_writes_docs_architecture(self):
        self.assertEqual(self.writers("docs/architecture/x.md"), {"architect"})

    def test_only_platform_writes_dockerignore(self):
        for path in (".dockerignore", "svc/.dockerignore"):
            self.assertEqual(self.writers(path), {"platform"}, path)

    def test_docs_runbooks_still_belong_to_sre(self):
        self.assertEqual(self.writers("docs/runbooks/api.md"), {"sre"})


class W5S5CdrAndBriefWriterTest(_Policies):
    def test_principal_writes_the_brief(self):
        self.assertTrue(self.can_write("principal", ".magenta/work/W/00-brief.md"))

    def test_principal_still_writes_decisions(self):
        self.assertTrue(self.can_write("principal", ".magenta/work/W/decisions/cdr-1.md"))

    def test_deviation_rule_says_makers_return_the_cdr_text(self):
        text = " ".join((ROOT / "rules" / "20-deviation-protocol.md").read_text(encoding="utf-8").split()).lower()
        self.assertIn("maker", text)
        self.assertIn("return the cdr text", text)


if __name__ == "__main__":
    unittest.main()
