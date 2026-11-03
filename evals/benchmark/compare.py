import json, glob, collections
def load(d, mode):
    out = {}
    for f in glob.glob(f"{d}/*--{mode}--*.json"):
        r = json.load(open(f))
        r["tok"] = sum(u["inputTokens"] + u["outputTokens"] + u["cacheReadInputTokens"] + u["cacheCreationInputTokens"] for u in r["usage"].values())
        r["out"] = sum(u["outputTokens"] for u in r["usage"].values())
        r["rate"] = r["hidden_passed"] / r["hidden_total"]; r["full"] = r["hidden_passed"] == r["hidden_total"]
        out[(r["task"], r["model"])] = r
    return out
import sys
P, M0, M1 = load("runs", "plain"), load("runs", "magenta"), load(sys.argv[1] if len(sys.argv) > 1 else "runs-next", "magenta")
keys = sorted(set(M1) & set(M0) & set(P))
MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-sonnet-5", "claude-haiku-4-5"]
def agg(D, ks):
    n = len(ks)
    return dict(rate=sum(D[k]["rate"] for k in ks)/n*100, full=sum(D[k]["full"] for k in ks), tok=sum(D[k]["tok"] for k in ks)/n,
                cost=sum(D[k]["cost"] or 0 for k in ks)/n, sec=sum(D[k]["seconds"] for k in ks)/n, out=sum(D[k]["out"] for k in ks)/n,
                tests=sum(D[k]["tests_added"] for k in ks)/n, orig=sum(D[k]["original_tests_pass"] for k in ks))
print("pairs", len(keys))
for label, ks in [("ALL", keys)] + [(m, [k for k in keys if k[1] == m]) for m in MODELS] + \
        [(t, [k for k in keys if P[k]["kind"] == t]) for t in ("simple", "complex", "hard")]:
    if not ks: continue
    a, b, c = agg(P, ks), agg(M0, ks), agg(M1, ks)
    print(f"{label:18} n={len(ks):2} | hidden% plain {a['rate']:5.1f}  mag0.14 {b['rate']:5.1f}  mag-next {c['rate']:5.1f} | full {a['full']}/{b['full']}/{c['full']}"
          f" | tok {a['tok']/1e3:5.0f}k {b['tok']/1e3:6.0f}k {c['tok']/1e3:6.0f}k ({(1-c['tok']/b['tok'])*100:+.0f}% saved) | cost ${a['cost']:.2f} ${b['cost']:.2f} ${c['cost']:.2f}"
          f" | sec {a['sec']:.0f} {b['sec']:.0f} {c['sec']:.0f} | tests {b['tests']:.1f}->{c['tests']:.1f} | orig ok {a['orig']}/{b['orig']}/{c['orig']}")
print()
for k in keys:
    a, b, c = P[k], M0[k], M1[k]
    if a["full"] != c["full"] or b["full"] != c["full"]:
        print("diff", k, "plain", a["hidden_passed"], "m0", b["hidden_passed"], "m1", c["hidden_passed"], "/", a["hidden_total"])
