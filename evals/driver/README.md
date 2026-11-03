# Driver evaluation (ADR-0016)

This evaluation compares the conductor of 0.12.0 (the conductor decides the domain questions) with the conductor of 0.13.0 (a driver role decides them). It tests the decisions and the plan of the conductor, not a full run of the task.

## Method

1. `scenarios.json` has 26 requests. Each one has the repository facts, the task type, the expected decision owner, the agents that must and must not be in the team, and the key points of a senior human.
2. `run.py` gives each request to headless Claude Code (`claude -p`, no tools) with the conductor skill and the routing of one version. The model returns the intake decisions and the plan as JSON. Each request runs 3 times for each version.
3. A judge (the same headless Claude Code) gets the request, the key points, and the two plans in a random order (A and B), without the version names. It scores each plan from 1 to 10 for the probable final result: correct and safe, the right experts and depth, and no wasted work or scope growth.
4. `final.py` counts the results.

Run it:

```bash
mkdir -p ver/v12 ver/v13
git show v0.12.0:skills/magenta/SKILL.md > ver/v12/SKILL.md
git show v0.12.0:workflows/routing.md > ver/v12/routing.md
cp ../../skills/magenta/SKILL.md ../../workflows/routing.md ver/v13/
python3 run.py 3 v13      # 3 runs of each scenario; about 15 USD
python3 final.py v13 3
```

## Limits

- The plan is not the result. A full run on a real repository is the next step (see `evals/README.md`, "Compare the modes").
- The judge is a model of the same family as the conductor. The order of the plans is random, and the judge does not see the version.
- The key points are the view of one senior engineer.
