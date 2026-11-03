"""Benchmark: a plain prompt against /magenta, on hidden tests, for several models."""
import json, os, re, shutil, subprocess, sys, time, concurrent.futures as cf
from pathlib import Path
B = Path(__file__).resolve().parent
TAG = os.environ.get("BENCH_TAG", "")
SRC, FIX, RUNS = B / ("src" + TAG), B / "fixtures", B / ("runs" + TAG)
TASKS = {
 "s1-pagination": ("simple", "Fix the bug: page 2 of paginate returns the wrong items. Follow the docstring."),
 "s2-discount": ("simple", "Discounts are rounded wrong: 15% of 1005 should give 854. Fix apply_discount. Follow the docstring."),
 "s3-slugify": ("simple", "Add a max_length parameter to slugify. Cut at a word boundary, never end with a dash, and never return more than max_length characters. When the first word is longer than max_length, cut that word. Without max_length, keep the current behavior."),
 "s4-email-refactor": ("simple", "Move the duplicated email validation of users.py and newsletter.py into one function validate_email in shop/validation.py. Keep the behavior of each caller exactly, as their docstrings say."),
 "c1-order-totals": ("complex", "Order totals are wrong in several cases (more than one discount code, VAT, free shipping). Fix shop/totals.py so that it follows RULES.md exactly."),
 "c2-rate-limit": ("complex", "Implement the login rate limit in SPEC.md."),
 "c3-csv-import": ("complex", "Implement the product import in SPEC.md."),
 "c4-idempotent-save": ("complex", "Fix the double order on save: implement the rules in SPEC.md."),
 "h1-rounding-trap": ("hard", "VAT prices are rounded down. They must be rounded half up to a whole rial. Fix it."),
 "h2-duplicates-speed": ("hard", "find_duplicates is too slow for large catalogs (100,000 names). Make it fast."),
 "h3-invoice-download": ("hard", "Add download_invoice(user, name) to shop/invoices.py. It returns the bytes of the invoice file."),
 "h4-price-cache": ("hard", "get_price reads the database each time. Add a cache to make it fast."),
 "h5-orders-format": ("hard", "Add a status field (unpaid or paid) to the saved orders."),
 "h6-split-utils": ("hard", "Split shop/utils.py into shop/money.py (format_rials, parse_rials) and shop/text.py (slug, initials)."),
 "h7-user-export": ("held-out", "Add export_users_csv(viewer) to shop/users.py. It returns the users as CSV text with the columns id, name, email, phone."),
 "h8-api-field": ("held-out", "Add the discount of the order to the order response of the API."),
 "h9-catalog-cache": ("held-out", "load_catalog reads and parses the file at each call. Add a cache."),
 "h10-retry-client": ("held-out", "Remote calls fail sometimes with a timeout or a 503. Add retries to shop/http.py call(); use the sleep argument to wait."),
}
NOTE = " Work without questions: nobody can answer them. When the task is done, stop."

def plugin_for(model):
    dst = B / ("plugins" + TAG) / model
    if dst.exists():
        return dst
    shutil.copytree(SRC / "plugins" / "magenta", dst)
    for agent in (dst / "agents").glob("*.md"):
        agent.write_text(re.sub(r"^model: .*$", f"model: {model}", agent.read_text(), count=1, flags=re.M))
    for prot in (dst / "magenta" / "protect.py", dst / "skills" / "magenta" / "scripts" / "protect.py"):
        s = prot.read_text().replace("import json\n", "import json\nimport os\n", 1)
        s = s.replace('''        if human and (human.group(2) in _ASK_WORDS or human.group(2).startswith("--fo")):\n''',
                      '''        if human and human.group(2) == "approve" and os.environ.get("MAGENTA_BENCH_HUMAN") == "approve":\n'''
                      '''            return "allow", ""  # benchmark: the human approves each check that the agents propose\n'''
                      '''        if human and (human.group(2) in _ASK_WORDS or human.group(2).startswith("--fo")):\n''', 1)
        assert "MAGENTA_BENCH_HUMAN" in s
        prot.write_text(s)
    return dst

def sh(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)

def prepare(task, mode, model, k):
    run = RUNS / f"{task}--{mode}--{model}--{k}"
    if run.exists():
        shutil.rmtree(run)
    shutil.copytree(FIX / task, run)
    for c in ("git init -q", "git config user.email b@b.c", "git config user.name bench", "git add -A",
              "git commit -qm start"):
        sh(c, run)
    if mode == "magenta":
        verify = B / ("plugins" + TAG) / model / "magenta" / "verify.py"
        (run / ".magenta" / "checks").mkdir(parents=True)
        (run / ".magenta" / "project-context.md").write_text(
            "# Project Context Profile\n\n- Status: CONFIRMED\n\nPython 3, pytest. Code in shop/, tests in tests/. "
            "Run the tests with `python3 -m pytest -q tests`.\n")
        (run / ".magenta" / "checks" / "project.yaml").write_text(
            'checks:\n  - id: project.tests\n    name: "Unit tests"\n    command: "python3 -m pytest -q tests"\n'
            '    set: quick\n    why: "CI runs it"\n')
        sh("printf '.magenta/\\n' >> .git/info/exclude", run)
        sh([sys.executable, str(verify), "--repo", str(run), "approve"], run)
    return run

def score(task, run):
    hidden = FIX / "hidden" / task
    r = sh(f"PYTHONPATH=. timeout 120 python3 -m pytest -q -p no:cacheprovider {hidden}", run)
    m = re.search(r"(\d+) passed", r.stdout); f = re.search(r"(\d+) failed", r.stdout); e = re.search(r"(\d+) error", r.stdout)
    passed, failed, errors = (int(x.group(1)) if x else 0 for x in (m, f, e))
    total = passed + failed + errors or len(re.findall(r"^def test_", (hidden / "test_hidden.py").read_text(), re.M))
    original = FIX / task / "tests"  # the tests that existed before the task must still pass on the new code
    vis = sh(f"PYTHONPATH=. timeout 120 python3 -m pytest -q -p no:cacheprovider {original}", run)
    def count(folder):
        return sum(len(re.findall(r"^\s*def test_", f.read_text(), re.M)) for f in Path(folder).rglob("test_*.py"))
    return {"hidden_passed": passed, "hidden_total": total, "original_tests_pass": vis.returncode == 0,
            "tests_added": count(run / "tests") - count(original) if (run / "tests").exists() else 0}

def one(task, mode, model, k):
    out = RUNS / f"{task}--{mode}--{model}--{k}.json"
    if out.exists():
        return
    run = prepare(task, mode, model, k)
    prompt = TASKS[task][1] + NOTE
    cmd = ["claude", "-p", "--model", model, "--output-format", "json", "--permission-mode", "bypassPermissions"]
    env = dict(os.environ)
    if mode == "magenta":
        cmd += ["--plugin-dir", str(plugin_for(model))]
        prompt = "/magenta:magenta --auto " + prompt
        env["MAGENTA_BENCH_HUMAN"] = "approve"
        cmd += ["--max-budget-usd", "12"]
    else:
        cmd += ["--max-budget-usd", "4"]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=run, input=prompt, capture_output=True, text=True, env=env,
                           timeout=45 * 60 if mode == "magenta" else 20 * 60)
        data = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {"raw": r.stdout[-2000:], "stderr": r.stderr[-2000:]}
    except subprocess.TimeoutExpired:
        data = {"timeout": True}
    usage = {}
    for name, u in (data.get("modelUsage") or {}).items():
        usage[name] = {k: u.get(k, 0) for k in ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "costUSD")}
    res = {"task": task, "kind": TASKS[task][0], "mode": mode, "model": model, "k": k, "seconds": round(time.time() - t0),
           "cost": data.get("total_cost_usd"), "turns": data.get("num_turns"), "is_error": data.get("is_error"),
           "timeout": data.get("timeout", False), "usage": usage, "result_tail": str(data.get("result", ""))[-600:],
           **score(task, run)}
    res["agents"] = sorted(p.stem for p in (run / ".magenta" / "agents").rglob("*.json")) if mode == "magenta" else []
    res["work_items"] = sorted(p.name for p in (run / ".magenta" / "work").glob("*")) if (run / ".magenta" / "work").exists() else []
    out.write_text(json.dumps(res, indent=1))

if __name__ == "__main__":
    models = sys.argv[1].split(","); modes = sys.argv[2].split(","); tasks = sys.argv[3].split(",") if sys.argv[3] != "all" else list(TASKS)
    reps = int(sys.argv[4]) if len(sys.argv) > 4 else 1; par = int(sys.argv[5]) if len(sys.argv) > 5 else 6
    RUNS.mkdir(exist_ok=True)
    for m in models:
        plugin_for(m)
    jobs = [(t, mo, m, k) for k in range(reps) for m in models for mo in modes for t in tasks]
    with cf.ThreadPoolExecutor(par) as ex:
        for f in cf.as_completed([ex.submit(one, *j) for j in jobs]):
            f.result()
    print("done")
