"""Metrics (RFC-0001, section 12): read the run logs and the work items of repositories."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from common import YamlError, parse_yaml


def collect(repos: list[Path]) -> dict:
    data = {"runs": [], "items": []}
    for repo in repos:
        log = repo / ".magenta" / "runs" / "runs.jsonl"
        if log.exists():
            for line in log.read_text(encoding="utf-8").splitlines():
                try:
                    entry = json.loads(line)
                    entry["repo"] = repo.name
                    data["runs"].append(entry)
                except ValueError:
                    continue
        work = repo / ".magenta" / "work"
        for folder in sorted(p for p in work.iterdir() if p.is_dir()) if work.is_dir() else []:
            item = {"repo": repo.name, "item": folder.name, "lane": "?", "gates": {}, "review": None,
                    "retro": (folder / "08-retro.md").exists(), "locked": (folder / "acceptance.lock").exists()}
            try:
                state = parse_yaml((folder / "state.yaml").read_text(encoding="utf-8")) or {}
                item["lane"] = state.get("lane") or "?"
                item["gates"] = {k: (v or {}).get("status") for k, v in (state.get("gates") or {}).items()
                                 if isinstance(v, dict)}
            except (OSError, YamlError):
                pass
            review = folder / "07-review.md"
            if review.exists():
                m = re.search(r"\b(APPROVED|CHANGES REQUESTED)\b", review.read_text(encoding="utf-8"))
                item["review"] = m.group(1) if m else "?"
            data["items"].append(item)
    return data


def report(data: dict) -> str:
    runs, items = data["runs"], data["items"]
    out = ["# Magenta metrics", ""]
    out += ["## Work items", "", f"Total: {len(items)}", ""]
    by_lane = defaultdict(int)
    for i in items:
        by_lane[i["lane"]] += 1
    out += ["| Lane | Work items |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(by_lane.items())]
    out += ["", "| Repository | Work item | Lane | Gates approved | Lock | Final review | Retro |", "|---|---|---|---|---|---|---|"]
    for i in items:
        approved = sum(1 for s in i["gates"].values() if s == "approved")
        out.append(f"| {i['repo']} | {i['item']} | {i['lane']} | {approved}/{len(i['gates'])} | "
                   f"{'yes' if i['locked'] else 'no'} | {i['review'] or '-'} | {'yes' if i['retro'] else 'no'} |")
    out += ["", "## Headless runs", "", f"Steps: {len(runs)}", ""]
    groups = defaultdict(lambda: {"steps": 0, "failed": 0, "cost": 0.0, "turns": 0, "time": 0.0})
    for r in runs:
        g = groups[(r.get("workflow"), r.get("agent"), r.get("engine"))]
        g["steps"] += 1
        g["failed"] += 0 if r.get("status") == "OK" else 1
        g["cost"] += r.get("cost_usd") or 0.0
        g["turns"] += r.get("turns") or 0
        g["time"] += r.get("duration_s") or 0.0
    out += ["| Workflow | Agent | Engine | Steps | Failed | Cost (USD) | Turns | Time (s) |", "|---|---|---|---|---|---|---|---|"]
    for (wf, agent, engine), g in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        out.append(f"| {wf} | {agent} | {engine} | {g['steps']} | {g['failed']} | {g['cost']:.3f} | {g['turns']} | {g['time']:.0f} |")
    total = sum(g["cost"] for g in groups.values())
    out += ["", f"Total cost of headless runs: {total:.3f} USD"]
    return "\n".join(out) + "\n"
