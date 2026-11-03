import json, collections, sys
from pathlib import Path
NEW = sys.argv[1]; K = int(sys.argv[2]); SC = json.loads(Path("scenarios.json").read_text())
O = Path("out"); res = collections.Counter(); per = {}; sc = {"v12": [], NEW: []}; cost = collections.Counter()
own = collections.Counter(); qs = collections.Counter(); ags = collections.Counter(); miss = collections.Counter(); extra = collections.Counter()
for s in SC:
    per[s["id"]] = collections.Counter()
    for k in range(K):
        j = json.loads((O / f"judge-{NEW}-{s['id']}-{k}.json").read_text())
        res[j["result"]] += 1; per[s["id"]][j["result"]] += 1
        sc["v12"].append(j["v12_score"]); sc[NEW].append(j["v13_score"]); cost["judge"] += j.get("cost", 0)
        for v in ("v12", NEW):
            d = json.loads((O / f"plan-{v}-{s['id']}-{k}.json").read_text()); p = d["plan"]; cost[v] += d["cost"]
            a = {x["agent"] for x in p.get("agents", [])} | {x.get("owner") for x in p.get("plan_steps", [])}
            own[v] += (p.get("decision_owner") or "none") in s["owner"].split("|")
            qs[v] += len(p.get("questions_to_human", [])); ags[v] += len({x["agent"] for x in p.get("agents", [])})
            miss[v] += any(m not in a for m in s["must"]); extra[v] += bool(set(s["not"]) & a)
n = len(SC) * K
print(f"runs per version: {n}; judge: {dict(res)}")
for v in ("v12", NEW):
    print(f"{v}: judge avg {sum(sc[v])/n:.2f}; right decision owner {own[v]}/{n}; missing required agent {miss[v]}; "
          f"unneeded agent {extra[v]}; questions avg {qs[v]/n:.2f}; agents avg {ags[v]/n:.2f}; cost ${cost[v]:.2f}")
print("judge cost", round(cost["judge"], 2))
for k, c in per.items():
    w = "v13" if c["v13"] > c["v12"] else ("v12" if c["v12"] > c["v13"] else "even")
    print(f"{k:28} v13 {c['v13']}  v12 {c['v12']}  tie {c['tie']}  -> {w}")
