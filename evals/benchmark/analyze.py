import json, glob, collections
R = [json.load(open(f)) for f in sorted(glob.glob("runs/*.json"))]
for r in R:
    r["tok"] = sum(u["inputTokens"] + u["outputTokens"] + u["cacheReadInputTokens"] + u["cacheCreationInputTokens"] for u in r["usage"].values())
    r["out"] = sum(u["outputTokens"] for u in r["usage"].values())
    r["fresh"] = sum(u["inputTokens"] + u["cacheCreationInputTokens"] for u in r["usage"].values())
    r["rate"] = r["hidden_passed"] / r["hidden_total"]; r["full"] = r["hidden_passed"] == r["hidden_total"]
json.dump(R, open("all.json", "w"))
MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-sonnet-5", "claude-haiku-4-5"]
def agg(rs):
    n = len(rs)
    return dict(n=n, rate=sum(r["rate"] for r in rs)/n*100, full=sum(r["full"] for r in rs), cost=sum(r["cost"] or 0 for r in rs),
                tok=sum(r["tok"] for r in rs)/n, out=sum(r["out"] for r in rs)/n, sec=sum(r["seconds"] for r in rs)/n,
                tests=sum(r["tests_added"] for r in rs)/n, orig=sum(r["original_tests_pass"] for r in rs))
print("model kind mode | n | hidden% | all-pass | cost$ | tokens/run | out/run | sec/run | tests added | original ok")
for m in MODELS:
    for kind in ("simple", "complex", "hard", "all"):
        for mode in ("plain", "magenta"):
            rs = [r for r in R if r["model"] == m and r["mode"] == mode and (kind == "all" or r["kind"] == kind)]
            a = agg(rs)
            print(f"{m[7:]:11} {kind:7} {mode:7} | {a['n']} | {a['rate']:5.1f} | {a['full']}/{a['n']} | {a['cost']:6.2f} | {a['tok']/1000:7.0f}k | {a['out']/1000:5.1f}k | {a['sec']:4.0f} | {a['tests']:4.1f} | {a['orig']}/{a['n']}")
print()
for mode in ("plain", "magenta"):
    a = agg([r for r in R if r["mode"] == mode]); print(mode, {k: round(v, 2) for k, v in a.items()})
print("\nhard tasks, each run:")
for r in R:
    if r["kind"] == "hard":
        print(f"{r['task']:20} {r['mode'][:3]} {r['model'][7:]:11} {r['hidden_passed']}/{r['hidden_total']} ${r['cost'] or 0:.2f} {r['tok']/1000:.0f}k")
