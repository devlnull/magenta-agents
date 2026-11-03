import json, collections
from pathlib import Path
SC = json.loads(Path("scenarios.json").read_text()); O = Path("out"); K = 3
need = {s["id"]: ("qa" in s["must"]) for s in SC}
notq = {s["id"]: ("qa" in s["not"]) for s in SC}
res = collections.Counter(); sc = collections.Counter(); cost = collections.Counter(); per = {}
stat = {v: collections.Counter() for v in ("v13e", "v14")}
for s in SC:
    per[s["id"]] = collections.Counter(); row = {}
    for k in range(K):
        j = json.loads((O / f"judge-v14-vs-v13e-{s['id']}-{k}.json").read_text())
        r = {"v13": "v14", "v12": "v13e", "tie": "tie"}[j["result"]]
        res[r] += 1; per[s["id"]][r] += 1; sc["v13e"] += j["v12_score"]; sc["v14"] += j["v13_score"]
        for v in ("v13e", "v14"):
            d = json.loads((O / f"plan-{v}-{s['id']}-{k}.json").read_text()); p = d["plan"]; cost[v] += d["cost"]
            agents = [x["agent"] for x in p.get("agents", [])]
            a = set(agents) | {x.get("owner") for x in p.get("plan_steps", [])}
            qa_parts = sum(1 for x in p.get("agents", []) if x["agent"] == "qa")
            qa_steps = sum(1 for x in p.get("plan_steps", []) if x.get("owner") == "qa")
            st = stat[v]; st["runs"] += 1; st["qa"] += "qa" in a; st["qa_parts"] += qa_parts; st["qa_steps"] += qa_steps
            st["steps"] += len(p.get("plan_steps", [])); st["agents"] += len(set(agents))
            if need[s["id"]] and "qa" not in a: st["qa_missing_when_needed"] += 1
            if notq[s["id"]] and "qa" in a: st["qa_when_not_needed"] += 1
            if not need[s["id"]] and "qa" in a: st["qa_optional_used"] += 1
            if not need[s["id"]]: st["optional_runs"] += 1
n = len(SC) * K
print("judge:", dict(res), " avg v13e %.2f  v14 %.2f" % (sc["v13e"] / n, sc["v14"] / n))
for v, st in stat.items():
    print(v, f"QA in {st['qa']}/{st['runs']}; QA when the scenario needs it: missing {st['qa_missing_when_needed']}; "
          f"QA in scenarios where it is optional: {st['qa_optional_used']}/{st['optional_runs']}; QA where not wanted {st['qa_when_not_needed']}; "
          f"QA parts {st['qa_parts']/n:.2f}, QA steps {st['qa_steps']/n:.2f}, all steps {st['steps']/n:.2f}, agents {st['agents']/n:.2f}; plan cost ${cost[v]:.2f}")
for k, c in per.items():
    w = max(("v14", "v13e"), key=lambda x: c[x]) if c["v14"] != c["v13e"] else "even"
    print(f"{k:28} need_qa={'Y' if need[k] else 'n'}  v14 {c['v14']}  v13e {c['v13e']}  tie {c['tie']}  -> {w}")
