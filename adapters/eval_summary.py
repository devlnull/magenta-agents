"""Eval summary (ADR-0012): compare plain tool use, the Magenta default mode, and team mode.

Each conductor task file in `evals/tasks/` has a "Task type" row and a "Runs" table with these columns:
Date | Mode | Model | Correct | Rule breaks | Cost (USD) | Time (min) | Notes.
Mode is plain, default, or team. Correct is yes, partial, or no.
"""
from __future__ import annotations

from pathlib import Path

MODES = ("plain", "default", "team")
CORRECT = {"yes": 1.0, "y": 1.0, "pass": 1.0, "true": 1.0, "partial": 0.5, "no": 0.0, "n": 0.0, "fail": 0.0,
           "false": 0.0}


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _number(text: str) -> float | None:
    try:
        return float(text.replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def parse_task(text: str) -> dict:
    """Return the task type and the runs (a list of dicts with lower-case column names)."""
    task_type, runs, header = "", [], None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            header = None
            continue
        cells = _cells(line)
        if len(cells) >= 2 and cells[0].lower() == "task type":
            value = cells[1].strip("` ").lower()
            task_type = "" if value.startswith("<") else value
            continue
        low = [c.lower() for c in cells]
        if header is None:
            if "mode" in low and "correct" in low:
                header = low
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue  # the separator row
        row = dict(zip(header, cells))
        if row.get("mode", "").lower() in MODES:
            runs.append(row)
    return {"task_type": task_type or "unknown", "runs": runs}


def collect(folder: Path) -> list[dict]:
    rows = []
    for path in sorted(folder.glob("*.md")):
        if path.name.upper().startswith("TEMPLATE"):
            continue
        task = parse_task(path.read_text(encoding="utf-8"))
        for run in task["runs"]:
            rows.append({"task": path.stem, "task_type": task["task_type"], "mode": run["mode"].lower(),
                         "correct": CORRECT.get(run.get("correct", "").lower()),
                         "rule_breaks": _number(run.get("rule breaks", "")),
                         "cost": _number(run.get("cost (usd)", "")),
                         "minutes": _number(run.get("time (min)", ""))})
    return rows


def _mean(values) -> str:
    values = [v for v in values if v is not None]
    return f"{sum(values) / len(values):.2f}" if values else "-"


def report(rows: list[dict]) -> str:
    if not rows:
        return "No runs yet. Add runs to the conductor tasks in evals/tasks/ (see evals/README.md)."
    lines = ["| Task type | Mode | Runs | Correct | Mean rule breaks | Mean cost (USD) | Mean time (min) |",
             "|---|---|---|---|---|---|---|"]
    groups = sorted({(r["task_type"], r["mode"]) for r in rows}, key=lambda g: (g[0], MODES.index(g[1])))
    groups += [("all", m) for m in MODES if any(r["mode"] == m for r in rows)]
    for task_type, mode in groups:
        part = [r for r in rows if r["mode"] == mode and (task_type == "all" or r["task_type"] == task_type)]
        scored = [r["correct"] for r in part if r["correct"] is not None]
        correct = f"{100 * sum(scored) / len(scored):.0f}%" if scored else "-"
        lines.append(f"| {task_type} | {mode} | {len(part)} | {correct} | {_mean(r['rule_breaks'] for r in part)} | "
                     f"{_mean(r['cost'] for r in part)} | {_mean(r['minutes'] for r in part)} |")
    return "\n".join(lines) + "\n"
