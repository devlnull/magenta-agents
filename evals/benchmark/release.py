"""The release benchmark of Magenta: a plain prompt against /magenta, on tasks with hidden tests.

Each release keeps its results in results/v<version>.json. The images in docs/assets/benchmark/ and the
benchmark block of the main README come from these files. The release workflow runs `check` and fails
when the results of the tag are missing or the images or the README block are not current.

    python3 release.py run 0.17.0                 # run the benchmark of the working tree (about 1 hour)
    python3 release.py run 0.17.0 --ref v0.17.0   # or of a tag
    python3 release.py collect 0.17.0             # write results/v0.17.0.json from the runs
    python3 release.py publish                    # make the images and update the README blocks
    python3 release.py check 0.17.0               # what the release workflow runs (no network, no API key)

`run` needs the Claude Code CLI with a login or an API key. The other commands need only Python 3 and,
for `publish`, matplotlib.
"""
import argparse, collections, datetime, hashlib, json, os, re, shutil, statistics, subprocess, sys
from pathlib import Path

B = Path(__file__).resolve().parent
ROOT = B.parent.parent
RESULTS = B / "results"
ASSETS = ROOT / "docs" / "assets" / "benchmark"
README = ROOT / "README.md"
MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-sonnet-5", "claude-haiku-4-5"]
NAMES = {"claude-opus-5-5": "Opus 5.5", "claude-sonnet-5-5": "Sonnet 5.5", "claude-sonnet-5": "Sonnet 5",
         "claude-haiku-4-5": "Haiku 4.5"}
KINDS = ["simple", "complex", "hard", "held-out"]
KIND_TEXT = {"simple": "Simple tasks", "complex": "Complex tasks (a spec)", "hard": "Hard tasks (hidden rules)",
             "held-out": "Held-out tasks"}
CORE = ["s1-pagination", "s2-discount", "s3-slugify", "s4-email-refactor", "c1-order-totals", "c2-rate-limit",
        "c3-csv-import", "c4-idempotent-save", "h1-rounding-trap", "h2-duplicates-speed", "h3-invoice-download",
        "h4-price-cache", "h5-orders-format", "h6-split-utils"]  # the 14 tasks of every version since 0.14
KEEP = ("task", "kind", "mode", "model", "k", "hidden_passed", "hidden_total", "original_tests_pass",
        "tests_added", "tokens", "cost", "seconds", "turns", "agents")


# ---------------------------------------------------------------- data

def tokens(r):
    if "tok" in r:
        return r["tok"]
    return sum(u.get(k, 0) for u in (r.get("usage") or {}).values()
               for k in ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens"))


def compact(r):
    out = {k: r.get(k) for k in KEEP if k != "tokens"}
    out["tokens"] = tokens(r)
    out["mode"] = "plain" if r["mode"] == "plain" else "magenta"
    out["agents"] = len(r.get("agents") or [])
    out["cost"] = round(r.get("cost") or 0, 5)
    return out


def load_runs(folder, mode):
    return [json.loads(p.read_text()) for p in sorted(Path(folder).glob(f"*--{mode}--*.json"))]


def versions():
    def key(p):
        return tuple(int(x) for x in p.stem[1:].split("."))
    return [json.loads(p.read_text()) for p in sorted(RESULTS.glob("v*.json"), key=key)]


def stats(runs):
    """The summary of a list of runs."""
    n = len(runs)
    if not n:
        return None
    per_rep = collections.defaultdict(list)
    for r in runs:
        per_rep[r["k"]].append(r["hidden_passed"] / r["hidden_total"])
    reps = [sum(v) / len(v) * 100 for v in per_rep.values()]
    return {
        "runs": n,
        "hidden": round(sum(r["hidden_passed"] / r["hidden_total"] for r in runs) / n * 100, 1),
        "spread": round(statistics.pstdev(reps), 1) if len(reps) > 1 else 0.0,
        "all_passed": sum(r["hidden_passed"] == r["hidden_total"] for r in runs),
        "old_tests_kept": sum(bool(r["original_tests_pass"]) for r in runs),
        "tokens": round(sum(r["tokens"] for r in runs) / n),
        "cost": round(sum(r["cost"] for r in runs) / n, 4),
        "seconds": round(sum(r["seconds"] for r in runs) / n),
    }


def select(v, mode, model=None, kind=None, tasks=None):
    return [r for r in v["runs"] if r["mode"] == mode and (model is None or r["model"] == model)
            and (kind is None or r["kind"] == kind) and (tasks is None or r["task"] in tasks)]


def summary(v, tasks=None):
    s = {"all": {}, "by_model": {}, "by_kind": {}}
    for mode in ("plain", "magenta"):
        s["all"][mode] = stats(select(v, mode, tasks=tasks))
        for m in v["setup"]["models"]:
            s["by_model"].setdefault(m, {})[mode] = stats(select(v, mode, model=m, tasks=tasks))
        for k in KINDS:
            got = stats(select(v, mode, kind=k, tasks=tasks))
            if got:
                s["by_kind"].setdefault(k, {})[mode] = got
    return s


# ---------------------------------------------------------------- commands

def cmd_run(a):
    tag = "-v" + a.version
    src = B / ("src" + tag)
    if src.exists():
        shutil.rmtree(src)
    src.mkdir()
    ref = a.ref or "HEAD"
    if a.ref is None and subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "plugins"],
                                        capture_output=True, text=True).stdout.strip():
        sys.exit("plugins/ has changes that are not committed. Commit them or give --ref.")
    archive = subprocess.run(["git", "-C", str(ROOT), "archive", ref], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(src)], input=archive.stdout, check=True)
    if not (B / "fixtures").exists():
        subprocess.run(["tar", "-xf", str(B / "fixtures.tar"), "-C", str(B)], check=True)
    env = dict(os.environ, BENCH_TAG=tag)
    subprocess.run([sys.executable, str(B / "bench.py"), a.models, "plain,magenta", "all", str(a.runs), str(a.jobs)],
                   cwd=B, env=env, check=True)
    print(f"Done. Next: python3 release.py collect {a.version}")


def cmd_collect(a):
    plain = Path(a.plain or B / f"runs-v{a.version}")
    magenta = Path(a.magenta or B / f"runs-v{a.version}")
    runs = [compact(r) for r in load_runs(plain, "plain")] + [compact(r) for r in load_runs(magenta, "magenta")]
    if a.models:
        runs = [r for r in runs if r["model"] in a.models.split(",")]
    if not runs:
        sys.exit(f"No runs in {plain} or {magenta}.")
    models = [m for m in MODELS if any(r["model"] == m for r in runs)]
    tasks = sorted({r["task"] for r in runs})
    reps = max(r["k"] for r in runs) + 1
    v = {"version": a.version, "date": a.date or datetime.date.today().isoformat(),
         "setup": {"models": models, "tasks": tasks, "runs_per_task": reps,
                   "fixtures_sha256": hashlib.sha256((B / "fixtures.tar").read_bytes()).hexdigest()[:16],
                   "note": a.note or ""},
         "runs": sorted(runs, key=lambda r: (r["mode"], r["model"], r["task"], r["k"]))}
    missing = [(t, mo, m, k) for t in tasks for mo in ("plain", "magenta") for m in models for k in range(reps)
               if not any(r["task"] == t and r["mode"] == mo and r["model"] == m and r["k"] == k for r in runs)]
    if missing and not a.allow_missing:
        sys.exit(f"{len(missing)} runs are missing, for example {missing[:3]}. Run them, or use --allow-missing.")
    v["summary"] = summary(v)
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"v{a.version}.json"
    out.write_text(json.dumps(v, indent=1) + "\n")
    s = v["summary"]["all"]
    print(f"{out.relative_to(ROOT)}: plain {s['plain']['hidden']}% ${s['plain']['cost']}, "
          f"magenta {s['magenta']['hidden']}% ${s['magenta']['cost']} ({len(runs)} runs)")


def readme_block(vs):
    v = vs[-1]
    s = v["summary"]
    hard = s["by_kind"]["hard"]
    lines = [
        f"Measured on Magenta {v['version']} ({v['date']}): {len(v['setup']['tasks'])} coding tasks with hidden tests, "
        f"{len(v['setup']['models'])} Claude models, {v['setup']['runs_per_task']} runs of each task. "
        "The same model does the same task with a plain prompt and with `/magenta`.",
        "",
        '<p align="center"><img src="docs/assets/benchmark/headline.png" alt="Hidden tests passed on hard tasks, '
        'a plain prompt against Magenta, for each model" width="860"></p>',
        "",
        "| | Plain prompt | Magenta |",
        "|---|---:|---:|",
    ]
    for kind in KINDS:
        if kind in s["by_kind"]:
            p, m = s["by_kind"][kind]["plain"], s["by_kind"][kind]["magenta"]
            bold = lambda x, y: (f"**{x:.1f}%**" if x > y else f"{x:.1f}%")
            lines.append(f"| {KIND_TEXT[kind]} | {bold(p['hidden'], m['hidden'])} | {bold(m['hidden'], p['hidden'])} |")
    p, m = s["all"]["plain"], s["all"]["magenta"]
    lines += [
        f"| **All tasks** | {p['hidden']:.1f}% | **{m['hidden']:.1f}%** |" if m["hidden"] >= p["hidden"]
        else f"| **All tasks** | **{p['hidden']:.1f}%** | {m['hidden']:.1f}% |",
        f"| Old tests still pass | {p['old_tests_kept']} of {p['runs']} | {m['old_tests_kept']} of {m['runs']} |",
        f"| Cost for each task | ${p['cost']:.3f} | ${m['cost']:.3f} |",
        "",
        f"**Where Magenta helps:** tasks where the repository has rules that the request does not say "
        f"(hard tasks: {hard['plain']['hidden']:.0f}% → {hard['magenta']['hidden']:.0f}%), and smaller models. "
        "**Where it does not:** small, clear tasks with a strong model. There, a plain prompt is as good and cheaper.",
    ]
    best = max(v["setup"]["models"], key=lambda x: (s["by_model"][x]["magenta"]["hidden"], -s["by_model"][x]["magenta"]["cost"]))
    b = s["by_model"][best]["magenta"]
    lines += ["", f"**Best value:** {NAMES[best]} with Magenta passed {b['hidden']:.0f}% of the hidden tests "
              f"({b['all_passed']} of {b['runs']} runs with all hidden tests passed) at ${b['cost']:.2f} for each task."]
    if len(vs) > 1:
        lines += ["", '<p align="center"><img src="docs/assets/benchmark/versions.png" alt="Quality and cost '
                  'of each Magenta version" width="860"></p>']
    lines += ["", "The tasks, the method, the limits, and the raw results: [evals/benchmark](evals/benchmark/README.md)."]
    return "\n".join(lines)


def scenario_table(v):
    tasks = json.loads((B / "tasks.json").read_text())
    rows = ["| Task | Kind | What the hidden tests check | Plain | Magenta |", "|---|---|---|---:|---:|"]
    for t in tasks:
        p, m = stats(select(v, "plain", tasks=[t["id"]])), stats(select(v, "magenta", tasks=[t["id"]]))
        if not p or not m:
            continue
        rows.append(f"| `{t['id']}` | {t['kind']} | {t['checks']} | {p['hidden']:.0f}% | {m['hidden']:.0f}% |")
    return "\n".join(rows)


def replace_block(text, name, body):
    start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    if start not in text:
        raise SystemExit(f"The marker {start} is missing.")
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{start}\n{body}\n{end}{tail}"


def expected_docs(vs):
    return {
        README: replace_block(README.read_text(), "benchmark", readme_block(vs)),
        B / "README.md": replace_block((B / "README.md").read_text(), "scenarios", scenario_table(vs[-1])),
    }


def cmd_publish(a):
    vs = versions()
    if not vs:
        sys.exit("No results in results/.")
    import charts_release  # matplotlib only here
    ASSETS.mkdir(parents=True, exist_ok=True)
    charts_release.make_all(vs, ASSETS)
    for path, text in expected_docs(vs).items():
        path.write_text(text)
    stamp = {"version": vs[-1]["version"], "results_sha256": digest(vs)}
    (ASSETS / "stamp.json").write_text(json.dumps(stamp, indent=1) + "\n")
    print(f"Images in {ASSETS.relative_to(ROOT)}, README blocks updated for {vs[-1]['version']}.")


def digest(vs):
    h = hashlib.sha256()
    for p in sorted(RESULTS.glob("v*.json")):
        h.update(p.name.encode() + p.read_text(encoding="utf-8").replace("\r\n", "\n").encode())
    return h.hexdigest()[:16]


def cmd_check(a):
    problems = []
    vs = versions()
    if not (RESULTS / f"v{a.version}.json").exists():
        problems.append(f"evals/benchmark/results/v{a.version}.json is missing. Run the release benchmark "
                        f"(evals/benchmark/release.py run {a.version}, then collect and publish).")
    if vs:
        stamp = ASSETS / "stamp.json"
        got = json.loads(stamp.read_text()) if stamp.exists() else {}
        if got.get("results_sha256") != digest(vs):
            problems.append("The benchmark images are older than the results. Run: python3 evals/benchmark/release.py publish")
        for path, text in expected_docs(vs).items():
            if path.read_text() != text:
                problems.append(f"The benchmark block of {path.relative_to(ROOT)} is not current. Run: "
                                "python3 evals/benchmark/release.py publish")
        if vs[-1]["version"] != a.version and not problems:
            problems.append(f"The newest results are for {vs[-1]['version']}, not {a.version}.")
    if problems:
        print("\n".join("- " + p for p in problems))
        sys.exit(1)
    print(f"The benchmark of {a.version} is present and current.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the benchmark (needs the Claude Code CLI)")
    r.add_argument("version"); r.add_argument("--ref")
    r.add_argument("--models", default=",".join(MODELS)); r.add_argument("--runs", type=int, default=3)
    r.add_argument("--jobs", type=int, default=6)
    c = sub.add_parser("collect", help="write results/v<version>.json from the runs")
    c.add_argument("version"); c.add_argument("--plain"); c.add_argument("--magenta"); c.add_argument("--models")
    c.add_argument("--date"); c.add_argument("--note"); c.add_argument("--allow-missing", action="store_true")
    sub.add_parser("publish", help="make the images and update the README blocks")
    k = sub.add_parser("check", help="fail when the results of a version are missing or not published")
    k.add_argument("version")
    a = p.parse_args()
    {"run": cmd_run, "collect": cmd_collect, "publish": cmd_publish, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
