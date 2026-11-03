import os, json, glob, collections, statistics as st
def load(d, mode):
    out = []
    for f in glob.glob(f"{d}/*--{mode}--*.json"):
        r = json.load(open(f))
        r["tok"] = sum(u["inputTokens"] + u["outputTokens"] + u["cacheReadInputTokens"] + u["cacheCreationInputTokens"] for u in r["usage"].values())
        r["rate"] = r["hidden_passed"] / r["hidden_total"]; r["full"] = r["hidden_passed"] == r["hidden_total"]; out.append(r)
    return out
# The published runs: plain in runs-016, Magenta 0.16 in runs-016c. A new run with BENCH_TAG=016 writes both to runs-016.
S = {"plain": load("runs-016", "plain"), "0.16": load(os.environ.get("RUNS_016", "runs-016"), "magenta")}
json.dump(S, open("all-0.16.json", "w"))
def row(rs):
    n = len(rs); reps = collections.defaultdict(list)
    for r in rs: reps[r["k"]].append(r["rate"])
    sd = st.pstdev([sum(v)/len(v)*100 for v in reps.values()])
    return f"{sum(r['rate'] for r in rs)/n*100:5.1f}% ±{sd:3.1f} | all {sum(r['full'] for r in rs):3}/{n:3} | {sum(r['tok'] for r in rs)/n/1e3:5.0f}k | ${sum(r['cost'] or 0 for r in rs)/n:.3f} | {sum(r['seconds'] for r in rs)/n:3.0f}s | orig {sum(r['original_tests_pass'] for r in rs)}/{n}"
for m in ("claude-sonnet-5-5", "claude-haiku-4-5", None):
    for kind in ("simple", "complex", "hard", "held-out", None):
        print(f"{(m or 'ALL')[-10:]:10} {kind or 'all':8} " + "  ||  ".join(f"{k}: {row([r for r in v if (m is None or r['model']==m) and (kind is None or r['kind']==kind)])}" for k, v in S.items()))
    print()
c = collections.defaultdict(list)
for r in S["0.16"]: c[(r["task"], r["model"][7:12])].append(f"{r['hidden_passed']}/{r['hidden_total']}")
print({k: v for k, v in sorted(c.items()) if any(x.split('/')[0] != x.split('/')[1] for x in v)})
