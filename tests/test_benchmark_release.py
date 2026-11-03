"""The release benchmark: the results, the images, and the README block agree."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "evals" / "benchmark"
sys.path.insert(0, str(BENCH))
import release  # noqa: E402


def check(version):
    return subprocess.run([sys.executable, str(BENCH / "release.py"), "check", version], capture_output=True, text=True)


class ReleaseBenchmarkTest(unittest.TestCase):
    def test_newest_results_are_published(self):
        newest = release.versions()[-1]["version"]
        r = check(newest)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_missing_version_fails(self):
        r = check("99.0.0")
        self.assertEqual(r.returncode, 1)
        self.assertIn("results/v99.0.0.json is missing", r.stdout)

    def test_results_are_complete_and_public(self):
        for path in sorted((BENCH / "results").glob("v*.json")):
            v = json.loads(path.read_text())
            self.assertEqual(path.stem, "v" + v["version"])
            text = path.read_text()
            for private in ("/tmp/", "/Users/", "/home/", "result_tail"):
                self.assertNotIn(private, text, path.name)
            s = release.summary(v)
            self.assertEqual(s, v["summary"], path.name)
            for mode in ("plain", "magenta"):
                self.assertEqual(s["all"][mode]["runs"],
                                 len(v["setup"]["tasks"]) * len(v["setup"]["models"]) * v["setup"]["runs_per_task"])

    def test_tasks_have_a_description(self):
        tasks = {t["id"] for t in json.loads((BENCH / "tasks.json").read_text())}
        self.assertEqual(tasks, set(release.versions()[-1]["setup"]["tasks"]))

    def test_stats(self):
        runs = [{"k": 0, "hidden_passed": 1, "hidden_total": 2, "original_tests_pass": True, "tokens": 10, "cost": 0.1,
                 "seconds": 4},
                {"k": 1, "hidden_passed": 2, "hidden_total": 2, "original_tests_pass": False, "tokens": 30, "cost": 0.3,
                 "seconds": 6}]
        s = release.stats(runs)
        self.assertEqual((s["hidden"], s["spread"], s["all_passed"], s["old_tests_kept"], s["tokens"]),
                         (75.0, 25.0, 1, 1, 20))


if __name__ == "__main__":
    unittest.main()
