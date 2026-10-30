"""Magenta headless runner (RFC-0001, option C layer 3).

It runs fixed workflows without a user interface. It calls existing harnesses as workers (for example
`claude -p` or `opencode run`). It keeps the state, the budget, and a JSONL log. It does not run
workflows with human gates: those stay interactive.

Workflows:
  prd-review   create a work item from a PRD file and run the Product Manager.
  pr-review    run QA, Architect, and Principal reviewers on a diff in parallel, then merge the findings.
"""
from __future__ import annotations

import concurrent.futures as futures
import datetime as dt
import json
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import source

_LOG_LOCK = threading.Lock()

HEADLESS_NOTE = ("You run headless. Nobody can answer questions now. Do not wait for a human. "
                 "Put your questions and assumptions in your output.")


class RunError(Exception):
    pass


@dataclass
class StepResult:
    step: str
    agent: str
    engine: str
    model: str | None
    returncode: int
    text: str
    cost_usd: float | None
    turns: int | None
    duration_s: float
    status: str


@dataclass
class Run:
    root: Path
    repo: Path
    workflow: str
    budget_usd: float | None = None
    max_turns: int = 40
    engine_override: str | None = None
    dry_run: bool = False
    timeout_s: int = 1800
    executor: object = None  # for tests: callable(cmd, cwd, timeout) -> (returncode, stdout)
    run_id: str = field(default_factory=lambda: dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6])
    results: list = field(default_factory=list)

    def __post_init__(self):
        self.cfg = source.load_config(self.root)
        self.run_dir = self.repo / ".magenta" / "runs" / f"{self.run_id}-{self.workflow}"
        self.run_dir.mkdir(parents=True, exist_ok=True)

    # ----- engines -----
    def engine_for(self, agent_id: str) -> tuple[str, str | None]:
        agents = source.load_agents(self.root, [agent_id])
        profile_name = agents[agent_id]["meta"]["magenta"]["model_profile"]
        profile = self.cfg["profiles"].get(profile_name) or {}
        runner = profile.get("runner") or {"engine": "claude"}
        engine = self.engine_override or runner.get("engine", "claude")
        model = runner.get("model") if not self.engine_override else None
        if model and "<" in str(model):
            model = None
        return engine, model

    def command(self, engine: str, agent_id: str, model: str | None, prompt: str) -> list[str]:
        template = self.cfg["engines"].get(engine)
        if not template:
            raise RunError(f"engine {engine!r} is not in models.yaml (engines)")
        values = {"prompt": prompt, "agent": f"magenta-{agent_id}", "model": model or "", "max_turns": str(self.max_turns)}
        cmd: list[str] = []
        for item in template:
            if "{model}" in item and not model:
                if cmd and cmd[-1].startswith("-"):
                    cmd.pop()  # drop the flag of the missing value
                continue
            cmd.append(item.format(**values))
        return cmd

    # ----- execution -----
    def spent(self) -> float:
        return sum(r.cost_usd or 0.0 for r in self.results)

    def over_budget(self) -> bool:
        return self.budget_usd is not None and self.spent() >= self.budget_usd

    def run_step(self, step: str, agent_id: str, prompt: str) -> StepResult:
        engine, model = self.engine_for(agent_id)
        cmd = self.command(engine, agent_id, model, prompt + "\n\n" + HEADLESS_NOTE)
        start = time.monotonic()
        if self.dry_run:
            code, out = 0, json.dumps({"result": f"(dry run) {' '.join(cmd[:2])} ... --agent magenta-{agent_id}"})
        elif self.executor:
            code, out = self.executor(cmd, self.repo, self.timeout_s)
        else:
            try:
                exe = shutil.which(cmd[0])
                if exe is None:
                    raise FileNotFoundError(cmd[0])
                proc = subprocess.run([exe] + cmd[1:], cwd=self.repo, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=self.timeout_s)
                code, out = proc.returncode, (proc.stdout if proc.stdout.strip() else proc.stderr)
            except FileNotFoundError:
                code, out = 127, f"the command {cmd[0]!r} is not installed"
            except subprocess.TimeoutExpired:
                code, out = 124, f"timeout after {self.timeout_s} s"
        text, cost, turns, is_error = parse_output(out)
        status = "OK" if code == 0 and not is_error else "FAILED"
        result = StepResult(step, agent_id, engine, model, code, text, cost, turns,
                            round(time.monotonic() - start, 1), status)
        self.results.append(result)
        self.log(result, cmd)
        (self.run_dir / f"{step}.md").write_text(text + "\n", encoding="utf-8")
        return result

    def log(self, r: StepResult, cmd: list[str]) -> None:
        entry = {"run_id": self.run_id, "workflow": self.workflow, "step": r.step, "agent": r.agent,
                 "engine": r.engine, "model": r.model, "command": cmd[0] if cmd else None,
                 "returncode": r.returncode, "status": r.status, "cost_usd": r.cost_usd, "turns": r.turns,
                 "duration_s": r.duration_s, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        with _LOG_LOCK, (self.repo / ".magenta" / "runs" / "runs.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def parse_output(out: str) -> tuple[str, float | None, int | None, bool]:
    """Read Claude Code JSON (one object) or OpenCode JSON events (one object on each line)."""
    out = out.strip()
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            return (str(data.get("result") or ""), _num(data.get("total_cost_usd")), data.get("num_turns"),
                    bool(data.get("is_error")))
    except ValueError:
        pass
    texts, cost, events = [], 0.0, 0
    for line in out.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        events += 1
        texts += _collect(event, "text")
        cost += sum(_num(c) or 0.0 for c in _collect(event, "cost"))
    if events:
        return "\n".join(t for t in texts if isinstance(t, str)).strip(), (cost or None), None, False
    return out, None, None, False


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect(obj, key):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and not isinstance(v, (dict, list)):
                found.append(v)
            else:
                found += _collect(v, key)
    elif isinstance(obj, list):
        for v in obj:
            found += _collect(v, key)
    return found


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "item"


# ----- workflows -----
def prd_review(run: Run, prd_file: Path, item_id: str | None = None) -> dict:
    if run.over_budget():
        raise RunError("the budget is reached: no agent runs")
    prd_text = prd_file.read_text(encoding="utf-8")
    item_id = item_id or dt.datetime.now().strftime("%Y%m%d%H%M")
    folder = run.repo / ".magenta" / "work" / f"{item_id}-{_slug(prd_file.stem)}"
    if (folder / "state.yaml").exists():
        raise RunError(f"the work item {item_id} already exists: {folder.relative_to(run.repo).as_posix()}")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "00-request.md").write_text(
        f"# Request\n\nSource: {prd_file.name}\nDate: {dt.date.today()}\n\n```UNTRUSTED\n{prd_text.strip()}\n```\n",
        encoding="utf-8")
    (folder / "state.yaml").write_text(
        f"work_item: {folder.name}\nlane: undecided\nstep: prd-review\nrun_id: {run.run_id}\n", encoding="utf-8")
    rel = folder.relative_to(run.repo).as_posix()
    result = run.run_step("prd-review", "product-manager",
                          f"Work item: {rel}. Review the PRD in {rel}/00-request.md. "
                          f"Write {rel}/01-prd-review.md with the PRD review template.")
    written = (folder / "01-prd-review.md").exists()
    report = (folder / "01-prd-review.md").read_text(encoding="utf-8") if written else result.text
    status = "OK" if result.status == "OK" and (written or run.dry_run) else "FAILED"
    return {"status": status, "work_item": rel, "report": report}


REVIEWERS = {
    "qa": "tests, edge cases, and coverage of the acceptance criteria",
    "architect": "structure, boundaries, contracts, data ownership, and the conventions of the project",
    "principal": "operability, security, resilience, and production readiness",
}


def pr_review(run: Run, base: str, item: str | None = None) -> dict:
    diff = subprocess.run(["git", "diff", f"{base}...HEAD"], cwd=run.repo, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if diff.returncode != 0:
        raise RunError(f"git diff failed: {diff.stderr.strip()}")
    if not diff.stdout.strip():
        return {"status": "OK", "report": "No changes between the base and HEAD."}
    if run.over_budget():
        return {"status": "BUDGET_EXCEEDED", "report": ""}
    diff_path = run.run_dir / "diff.patch"
    diff_path.write_text(diff.stdout, encoding="utf-8")
    rel_diff = diff_path.relative_to(run.repo).as_posix()
    context = f" The related work item is .magenta/work/{item}*." if item else ""
    def review(agent_id):
        return run.run_step(f"review-{agent_id}", agent_id,
                            f"Review the change in {rel_diff} (git diff {base}...HEAD). Read the changed files for "
                            f"context.{context} Focus on: {REVIEWERS[agent_id]}. This is a read-only review: do not "
                            "write or change any file. Return a findings table in your final message with the columns: "
                            "Severity (BLOCKER, MAJOR, MINOR, NIT), File:line, Finding, Risk, Fix.")
    with futures.ThreadPoolExecutor(max_workers=len(REVIEWERS)) as pool:
        results = list(pool.map(review, REVIEWERS))
    if run.over_budget():
        report = "\n\n".join(f"## {r.agent}\n\n{r.text}" for r in results)
        return {"status": "BUDGET_EXCEEDED", "report": report}
    files = ", ".join((run.run_dir / f"review-{a}.md").relative_to(run.repo).as_posix() for a in REVIEWERS)
    merged = run.run_step("merge", "principal",
                          f"Merge the review findings in these files into one report: {files}. Remove duplicates. "
                          "Keep the most severe severity. Sort by severity. Start with a one-line verdict: "
                          "APPROVED or CHANGES REQUESTED, and the count of BLOCKER and MAJOR findings. "
                          "Do not write files. Return the report in your final message.")
    status = "OK" if all(r.status == "OK" for r in results + [merged]) else "FAILED"
    return {"status": status, "report": merged.text}


def summary(run: Run) -> str:
    lines = [f"Run {run.run_id} ({run.workflow})", "", "| Step | Agent | Engine | Status | Turns | Cost (USD) | Time (s) |",
             "|---|---|---|---|---|---|---|"]
    for r in run.results:
        cost = f"{r.cost_usd:.3f}" if r.cost_usd is not None else "-"
        lines.append(f"| {r.step} | {r.agent} | {r.engine} | {r.status} | {r.turns or '-'} | {cost} | {r.duration_s} |")
    lines.append(f"\nTotal cost: {run.spent():.3f} USD" + (f" of a budget of {run.budget_usd} USD" if run.budget_usd else ""))
    return "\n".join(lines)
