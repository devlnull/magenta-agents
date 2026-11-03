import json, random, subprocess, sys, concurrent.futures as cf
from pathlib import Path
UP = Path(__file__).parent / "ver"
HERE = Path(__file__).parent
OUT = HERE / "out"; OUT.mkdir(exist_ok=True)
SC = json.loads((HERE / "scenarios.json").read_text())
REPEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 2

SCHEMA = """Output only one JSON object, no other text, with these keys:
"task_type": string, "mode": "default"|"team", "lane": "lite"|"standard"|"full",
"decision_owner": the role that writes the plan and decides the domain questions (for example when the tests are enough, which option): "conductor" or an agent id,
"checker": the agent id that reviews the work of the decision owner, or null,
"agents": [{"agent": id, "part": "lead"|"checks"|"lens"|"plan"|"review"|"other"}],
"questions_to_human": [questions that you ask the human before the work is done, except the approval of the checks],
"plan_steps": [{"step": short text, "owner": agent id or "conductor"}],
"done_definition": [the checks that define done],
"out_of_scope": [what you do not do in this task]"""

def plan_prompt(version, s):
    skill = (UP / version / "SKILL.md").read_text()
    routing = (UP / version / "routing.md").read_text()
    return (f"You are Claude Code with the skill below loaded (the Magenta conductor). Do not use tools. "
            f"Simulate only the intake and the planning for the request: decide what the skill tells you to decide, "
            f"and give the plan that you and the agents would follow. Follow the skill and the routing exactly.\n\n"
            f"<skill>\n{skill}\n</skill>\n\n<routing>\n{routing}\n</routing>\n\n"
            f"Repository facts: {s['context']}\n\nThe request of the user:\n{s['request']}\n\n{SCHEMA}")

def claude(prompt):
    r = subprocess.run(["claude", "-p", "--output-format", "json", "--max-turns", "1", "--tools", ""],
                       input=prompt, capture_output=True, text=True, timeout=600)
    d = json.loads(r.stdout)
    return d.get("result", ""), d.get("total_cost_usd", 0), list((d.get("modelUsage") or {}).keys())

def parse(text):
    a, b = text.find("{"), text.rfind("}")
    return json.loads(text[a:b + 1])

def plan_job(version, s, k):
    f = OUT / f"plan-{version}-{s['id']}-{k}.json"
    if f.exists():
        return
    for attempt in range(3):
        try:
            text, cost, models = claude(plan_prompt(version, s))
            f.write_text(json.dumps({"plan": parse(text), "cost": cost, "models": models}, indent=1))
            return
        except Exception as e:
            err = str(e)
    f.write_text(json.dumps({"error": err}))

JUDGE = """You are a principal software engineer. Two plans for the same task follow. Judge which plan will most likely
give the best final result for the human: a correct and safe result, the right experts, the right depth for the
risk, and no wasted work or scope growth. Use the expert key points. Do not prefer a plan for its length.
Output only JSON: {"score_a": 1-10, "score_b": 1-10, "winner": "A"|"B"|"tie", "reason": one sentence}."""

def judge_job(s, k):
    f = OUT / f"judge-{NEW}-{s['id']}-{k}.json"
    if f.exists():
        return
    try:
        p12 = json.loads((OUT / f"plan-v12-{s['id']}-{k}.json").read_text())["plan"]
        p13 = json.loads((OUT / f"plan-{NEW}-{s['id']}-{k}.json").read_text())["plan"]
    except Exception as e:
        f.write_text(json.dumps({"error": str(e)})); return
    flip = random.Random(f"{s['id']}{k}").random() < 0.5
    a, b = (p13, p12) if flip else (p12, p13)
    prompt = (f"{JUDGE}\n\nTask: {s['request']}\nRepository facts: {s['context']}\nExpert key points: "
              + "; ".join(s["points"]) + f"\n\nPlan A:\n{json.dumps(a, indent=1)}\n\nPlan B:\n{json.dumps(b, indent=1)}")
    for attempt in range(3):
        try:
            text, cost, models = claude(prompt)
            j = parse(text)
            v13 = "A" if flip else "B"
            j.update(flip=flip, v13_score=j["score_a"] if flip else j["score_b"],
                     v12_score=j["score_b"] if flip else j["score_a"],
                     result="v13" if j["winner"] == v13 else ("tie" if j["winner"] == "tie" else "v12"), cost=cost)
            f.write_text(json.dumps(j, indent=1)); return
        except Exception as e:
            err = str(e)
    f.write_text(json.dumps({"error": err}))

NEW = sys.argv[2] if len(sys.argv) > 2 else "v13"

if __name__ == "__main__":
    jobs = [(v, s, k) for s in SC for v in ("v12", NEW) for k in range(REPEATS)]
    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda j: plan_job(*j), jobs))
    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda j: judge_job(*j), [(s, k) for s in SC for k in range(REPEATS)]))
    print("done")
