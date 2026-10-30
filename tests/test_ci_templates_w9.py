import posixpath
import re
import shlex
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITHUB = ROOT / "ci" / "github-actions.magenta.yml"
GITLAB = ROOT / "ci" / "gitlab-ci.magenta.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
TEMPLATES = (GITHUB, GITLAB)
SHELL_OPERATORS = {"&&", "||", ";", "|", ">", "2>&1"}
RELEASE_TAG = r"\bv\d+\.\d+\.\d+\b"


def _text(path):
    return path.read_text(encoding="utf-8")


def _code_lines(path):
    return [line for line in _text(path).splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _tokens(line):
    try:
        return shlex.split(line, comments=False)
    except ValueError:
        return line.split()


def _normalize(word):
    return re.sub(r"\$\{(\w+)\}", r"$\1", word)


def _clone_lines(path):
    return [line for line in _code_lines(path) if re.search(r"\bgit clone\b", line)]


def _clone_target(line):
    words = _tokens(line[line.index("git clone"):])
    args = []
    for word in words[2:]:
        if word in SHELL_OPERATORS:
            break
        args.append(word)
    return _normalize(args[-1]) if args else ""


def _run_scripts(path):
    lines = _text(path).splitlines()
    scripts = []
    i = 0
    while i < len(lines):
        match = re.match(r"^(\s*(?:-\s+)?)run:\s*(.*)$", lines[i])
        i += 1
        if not match:
            continue
        column = len(match.group(1))
        value = match.group(2).strip()
        if not re.fullmatch(r"[|>][-+0-9]*", value):
            scripts.append(value)
            continue
        body = []
        while i < len(lines) and (not lines[i].strip() or _indent(lines[i]) > column):
            body.append(lines[i])
            i += 1
        scripts.append("\n".join(body))
    return scripts


def _block(lines, start, column):
    body = []
    for line in lines[start + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if _indent(line) <= column:
            break
        body.append(line.strip())
    return body


def _permissions(lines, column):
    for index, line in enumerate(lines):
        match = re.match(r"^( *)permissions:\s*(.*?)\s*(?:#.*)?$", line)
        if match and len(match.group(1)) == column:
            return [match.group(2)] + _block(lines, index, column)
    return None


def _jobs(text):
    section = text.split("\njobs:\n", 1)[1]
    jobs = {}
    for chunk in re.split(r"(?m)^  (?=[A-Za-z0-9_-]+:\s*$)", section):
        if chunk.strip():
            name, _, body = chunk.partition(":")
            jobs[name.strip()] = ["  " + name.strip() + ":"] + body.splitlines()[1:]
    return jobs


def _write_scopes(permissions):
    scopes = set()
    for entry in permissions or []:
        if re.search(r"\bwrite-all\b", entry):
            scopes.add("write-all")
        scopes.update(re.findall(r"([\w-]+):\s*write\b", entry))
    return scopes


class W9S1WritableCloneFolderTest(unittest.TestCase):
    def test_github_template_has_no_opt_path(self):
        self.assertIsNone(re.search(r"/opt\b", _text(GITHUB)), "the GitHub template still uses /opt")

    def test_github_template_clones_magenta_under_runner_temp(self):
        clones = _clone_lines(GITHUB)
        self.assertTrue(clones, "the GitHub template has no git clone")
        text = _text(GITHUB)
        for line in clones:
            target = _clone_target(line)
            with self.subTest(target):
                if "RUNNER_TEMP" in target:
                    continue
                variable = re.match(r"^\$(\w+)", target)
                self.assertIsNotNone(variable, f"the clone target {target!r} is not under $RUNNER_TEMP")
                self.assertRegex(text, rf"(?m)^\s*{variable.group(1)}\s*[:=][^\n]*(RUNNER_TEMP|runner\.temp)",
                                 f"the clone target {target!r} is not under $RUNNER_TEMP")

    def test_magenta_commands_still_run_from_the_clone_folder(self):
        for path in TEMPLATES:
            with self.subTest(path.name):
                targets = {_clone_target(line) for line in _clone_lines(path)}
                scripts = [_normalize(word) for line in _code_lines(path) for word in _tokens(line)
                           if word.endswith("magenta.py")]
                self.assertTrue(scripts, "no magenta.py command")
                for script in scripts:
                    self.assertIn(posixpath.dirname(script), targets, f"{script} is not in the clone folder")


class W9S2PinnedCodeTest(unittest.TestCase):
    def test_each_clone_uses_branch_magenta_ref(self):
        for path in TEMPLATES:
            clones = _clone_lines(path)
            with self.subTest(path.name):
                self.assertTrue(clones, "no git clone")
                for line in clones:
                    self.assertRegex(line, r"--branch[ =][\"']?\$\{?MAGENTA_REF\b", line.strip())

    def test_each_template_gives_magenta_ref_a_release_tag_default(self):
        for path in TEMPLATES:
            with self.subTest(path.name):
                self.assertTrue(any(re.search(r"\bMAGENTA_REF\b.*" + RELEASE_TAG, line) for line in _code_lines(path)),
                                "MAGENTA_REF has no default of the form v<digits>.<digits>.<digits>")

    def test_each_claude_code_install_has_a_version_variable(self):
        for path in TEMPLATES:
            installs = [line for line in _code_lines(path) if "@anthropic-ai/claude-code" in line]
            with self.subTest(path.name):
                self.assertTrue(installs, "no install of @anthropic-ai/claude-code")
                for line in installs:
                    self.assertRegex(line, r"@anthropic-ai/claude-code@[\"']?\$\{?CLAUDE_CODE_VERSION\b", line.strip())

    def test_each_template_documents_claude_code_version(self):
        for path in TEMPLATES:
            with self.subTest(path.name):
                lines = [line for line in _text(path).splitlines()
                         if "CLAUDE_CODE_VERSION" in line and "@anthropic-ai/claude-code" not in line]
                self.assertTrue(lines, "CLAUDE_CODE_VERSION is not defined or documented")

    def test_github_template_maps_the_variables_into_env(self):
        text = _text(GITHUB)
        for name in ("MAGENTA_REF", "CLAUDE_CODE_VERSION"):
            with self.subTest(name):
                self.assertRegex(text, rf"(?m)^\s+{name}:\s*\S", f"{name} is not an env key, so the shell sees it empty")


class W9S3NoExpressionInRunTest(unittest.TestCase):
    def test_no_run_script_contains_an_expression(self):
        scripts = _run_scripts(GITHUB)
        self.assertTrue(scripts, "the GitHub template has no run step")
        for script in scripts:
            with self.subTest(script.strip()[:60]):
                self.assertNotIn("${{", script)

    def test_templates_still_run_the_pr_review(self):
        for path in TEMPLATES:
            with self.subTest(path.name):
                self.assertRegex(_text(path), r"magenta\.py\"? run pr-review [^\n]*--base ")
        self.assertTrue(any("gh pr comment" in script for script in _run_scripts(GITHUB)), "no gh pr comment step")


class W9S4ReleasePermissionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _text(RELEASE)
        cls.jobs = _jobs(cls.text)
        cls.publish = [name for name, lines in cls.jobs.items() if any("gh release" in line for line in lines)]

    def test_top_level_permissions_are_contents_read(self):
        permissions = _permissions(self.text.splitlines(), 0)
        self.assertIsNotNone(permissions, "no top-level permissions")
        self.assertRegex(" ".join(permissions), r"\bcontents:\s*read\b")
        self.assertEqual(_write_scopes(permissions), set())

    def test_only_the_publish_job_has_contents_write(self):
        self.assertEqual(len(self.publish), 1, "exactly one job runs gh release")
        for name, lines in self.jobs.items():
            with self.subTest(name):
                expected = {"contents"} if name in self.publish else set()
                self.assertEqual(_write_scopes(_permissions(lines, 4)), expected)

    def test_publish_still_needs_ci_and_creates_the_release(self):
        self.assertEqual(self.publish, ["publish"])
        publish = "\n".join(self.jobs["publish"])
        self.assertRegex(publish, r"(?m)^    needs:\s*\[?\s*ci\b")
        self.assertIn("gh release create", publish)

    def test_called_ci_workflow_needs_no_write_permission(self):
        self.assertIn("uses: ./.github/workflows/ci.yml", self.text)
        self.assertNotRegex(_text(CI), r"(?m)^\s*[\w-]+:\s*write\b|write-all")


if __name__ == "__main__":
    unittest.main()
