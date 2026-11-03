import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
R = json.load(open("all.json"))
MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-sonnet-5", "claude-haiku-4-5"]
LABEL = {"claude-opus-5-5": "Opus 5.5", "claude-sonnet-5-5": "Sonnet 5.5", "claude-sonnet-5": "Sonnet 5", "claude-haiku-4-5": "Haiku 4.5"}
C = {"plain": "#2a78d6", "magenta": "#eb6834"}; NAME = {"plain": "Plain prompt", "magenta": "Magenta (multi-agent)"}
INK, INK2, GRID, BG = "#1f1f1e", "#5f5e58", "#e4e3de", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK, "figure.facecolor": BG, "axes.facecolor": BG})
def sel(**kw): return [r for r in R if all(r[k] == v for k, v in kw.items())]
def mean(xs): return sum(xs) / len(xs) if xs else 0
def style(ax):
    ax.spines[["top", "right", "left"]].set_visible(False); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    ax.tick_params(length=0)
def bars(ax, groups, vals, fmt, ylog=False, ratio=False, off=0.8):
    w = 0.38; xs = range(len(groups))
    for i, mode in enumerate(("plain", "magenta")):
        pos = [x + (i - 0.5) * (w + 0.03) for x in xs]
        b = ax.bar(pos, [vals[g][mode] for g in groups], w, color=C[mode], label=NAME[mode], zorder=3)
        for p, g in zip(pos, groups):
            v = vals[g][mode]; ax.text(p, v * (1.08 if ylog else 1) + (0 if ylog else off), fmt(v), ha="center", va="bottom", fontsize=8.5, color=INK)
    if ratio:
        for x, g in zip(xs, groups):
            k = vals[g]["magenta"] / vals[g]["plain"]
            ax.text(x, ax.get_ylim()[0] if not ylog else vals[g]["plain"] * 0, "", ha="center")
            ax.annotate(f"×{k:.1f}", (x, 0), xytext=(0, -30), textcoords="offset points", ha="center", fontsize=9, color=INK2)
    ax.set_xticks(list(xs)); ax.set_xticklabels(groups); style(ax)
    if ylog: ax.set_yscale("log")

fig, axs = plt.subplots(2, 2, figsize=(13, 9.2))
fig.suptitle("Plain prompt vs Magenta (multi-agent): 14 coding tasks, 4 Claude models, hidden tests", fontsize=14, color=INK, x=0.04, ha="left", y=0.985)
fig.text(0.04, 0.945, "One run for each task, model, and mode (112 runs). Magenta: /magenta --auto, the agents on the same model, the human approval simulated.",
         fontsize=9.5, color=INK2)
# 1 pass rate by model
g = [LABEL[m] for m in MODELS]
v = {LABEL[m]: {mo: mean([r["rate"] for r in sel(model=m, mode=mo)]) * 100 for mo in ("plain", "magenta")} for m in MODELS}
ax = axs[0, 0]; bars(ax, g, v, lambda x: f"{x:.0f}%"); ax.set_ylim(0, 115); ax.set_title("Hidden tests passed (all 14 tasks)", loc="left", fontsize=11.5)
ax.set_ylabel("% of hidden tests")
h, l = ax.get_legend_handles_labels(); fig.legend(h, l, frameon=False, loc="upper right", ncol=2, fontsize=10, bbox_to_anchor=(0.98, 0.955))
# 2 pass rate by tier
tiers = [("simple", "Simple (4)"), ("complex", "Complex (4)"), ("hard", "Hard: hidden rules (6)")]
v = {lab: {mo: mean([r["rate"] for r in sel(kind=t, mode=mo)]) * 100 for mo in ("plain", "magenta")} for t, lab in tiers}
ax = axs[0, 1]; bars(ax, [l for _, l in tiers], v, lambda x: f"{x:.0f}%"); ax.set_ylim(0, 115)
ax.set_title("Hidden tests passed, by task difficulty (all models)", loc="left", fontsize=11.5)
# 3 tokens per run
v = {LABEL[m]: {mo: mean([r["tok"] for r in sel(model=m, mode=mo)]) for mo in ("plain", "magenta")} for m in MODELS}
ax = axs[1, 0]; bars(ax, g, v, lambda x: f"{x/1e6:.1f}M" if x >= 1e6 else f"{x/1e3:.0f}k", ylog=True)
ax.set_ylim(5e4, 2e7); ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x/1e6:g}M" if x >= 1e6 else f"{x/1e3:g}k"))
ax.set_title("Tokens for each task (input + output + cache), log scale", loc="left", fontsize=11.5)
for x, m in enumerate(g):
    ax.text(x, 1.3e7, f"×{v[m]['magenta']/v[m]['plain']:.0f}", ha="center", fontsize=10, color=INK, fontweight="bold")
# 4 cost per task
v = {LABEL[m]: {mo: mean([r["cost"] or 0 for r in sel(model=m, mode=mo)]) for mo in ("plain", "magenta")} for m in MODELS}
ax = axs[1, 1]; bars(ax, g, v, lambda x: f"${x:.2f}", ylog=False, off=0.02); ax.set_ylim(0, 2.1)
ax.set_title("Cost for each task (USD)", loc="left", fontsize=11.5)
for x, m in enumerate(g):
    ax.text(x, 1.95, f"×{v[m]['magenta']/v[m]['plain']:.0f}", ha="center", fontsize=10, color=INK, fontweight="bold")
fig.tight_layout(rect=(0.02, 0, 1, 0.93)); fig.savefig("benchmark-summary.png", dpi=150)

# Figure 2: tokens for each task, small multiples by model
tasks = sorted({r["task"] for r in R}, key=lambda t: ("shc".index(t[0]), t))
fig, axs = plt.subplots(1, 4, figsize=(15, 7.5), sharey=True)
fig.suptitle("Tokens for each task and model (log scale). Blue: plain prompt. Orange: Magenta.", fontsize=13, color=INK, x=0.03, ha="left")
for ax, m in zip(axs, MODELS):
    for i, mode in enumerate(("plain", "magenta")):
        ys = [y + (0.2 if mode == "plain" else -0.2) for y in range(len(tasks))]
        xs = [sel(model=m, mode=mode, task=t)[0]["tok"] for t in tasks]
        ax.barh(ys, xs, 0.36, color=C[mode], zorder=3, label=NAME[mode])
    for y, t in enumerate(tasks):
        rp, rm = sel(model=m, mode="plain", task=t)[0], sel(model=m, mode="magenta", task=t)[0]
        mark = lambda r: "" if r["full"] else " ✗"
        ax.text(rm["tok"] * 1.1, y - 0.2, f"{rm['tok']/1e6:.1f}M{mark(rm)}", va="center", fontsize=7.5, color=INK)
        ax.text(rp["tok"] * 1.1, y + 0.2, f"{rp['tok']/1e3:.0f}k{mark(rp)}", va="center", fontsize=7.5, color=INK)
    ax.set_xscale("log"); ax.set_xlim(5e4, 4e7); ax.set_title(LABEL[m], loc="left", fontsize=11.5)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x/1e6:g}M" if x >= 1e6 else f"{x/1e3:g}k"))
    ax.spines[["top", "right"]].set_visible(False); ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=0)
axs[0].set_yticks(range(len(tasks))); axs[0].set_yticklabels(tasks); axs[0].invert_yaxis()
axs[0].legend(frameon=False, loc="lower left", fontsize=8.5, bbox_to_anchor=(0, -0.13))
fig.text(0.03, 0.015, "✗ = not all hidden tests pass.  s = simple, c = complex, h = hard (hidden rules in the repository).", fontsize=9, color=INK2)
fig.tight_layout(rect=(0, 0.03, 1, 0.95)); fig.savefig("benchmark-tokens-per-task.png", dpi=150)
print("ok")
