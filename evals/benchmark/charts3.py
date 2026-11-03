import json, glob, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
def load(d, mode):
    out = []
    for f in glob.glob(f"{d}/*--{mode}--*.json"):
        r = json.load(open(f))
        r["tok"] = sum(u["inputTokens"] + u["outputTokens"] + u["cacheReadInputTokens"] + u["cacheCreationInputTokens"] for u in r["usage"].values())
        r["rate"] = r["hidden_passed"] / r["hidden_total"]; out.append(r)
    return out
S = {"plain": load("runs", "plain"), "0.14": load("runs", "magenta"), "0.15": load("runs-next2", "magenta")}
C = {"plain": "#2a78d6", "0.14": "#eb6834", "0.15": "#1baf7a"}
NAME = {"plain": "Plain prompt", "0.14": "Magenta 0.14", "0.15": "Magenta 0.15"}
MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-sonnet-5", "claude-haiku-4-5"]
LABEL = {"claude-opus-5-5": "Opus 5.5", "claude-sonnet-5-5": "Sonnet 5.5", "claude-sonnet-5": "Sonnet 5", "claude-haiku-4-5": "Haiku 4.5"}
INK, INK2, GRID, BG = "#1f1f1e", "#5f5e58", "#e4e3de", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.labelcolor": INK2, "axes.titlecolor": INK, "figure.facecolor": BG, "axes.facecolor": BG})
mean = lambda xs: sum(xs) / len(xs)
def panel(ax, groups, getter, fmt, title, ylog=False, ymax=None, off=0.0):
    w = 0.26
    for i, s in enumerate(S):
        xs = [x + (i - 1) * (w + 0.02) for x in range(len(groups))]
        vals = [getter(S[s], g) for g in groups]
        ax.bar(xs, vals, w, color=C[s], zorder=3, label=NAME[s])
        for x, v in zip(xs, vals):
            ax.text(x, v * (1.07 if ylog else 1) + off, fmt(v), ha="center", va="bottom", fontsize=7.8, color=INK)
    ax.set_xticks(range(len(groups))); ax.set_xticklabels([LABEL.get(g, g) for g in groups])
    ax.set_title(title, loc="left", fontsize=11.5); ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=0)
    if ylog: ax.set_yscale("log")
    if ymax: ax.set_ylim(top=ymax)
fig, axs = plt.subplots(2, 2, figsize=(13.5, 9.4))
fig.suptitle("Magenta 0.15 against 0.14 and a plain prompt: 14 tasks, 4 Claude models, hidden tests", fontsize=14, color=INK, x=0.04, ha="left", y=0.985)
fig.text(0.04, 0.947, "One run for each task, model, and version (168 runs). 0.15: direct mode for small tasks, fewer conductor turns, a short conductor skill, and a rule and caller scan by a script.", fontsize=9.3, color=INK2)
by_model = lambda key: (lambda rs, m: mean([r[key] for r in rs if r["model"] == m]))
panel(axs[0, 0], MODELS, lambda rs, m: by_model("rate")(rs, m) * 100, lambda v: f"{v:.0f}%", "Hidden tests passed, by model", ymax=112, off=0.8)
axs[0, 0].set_ylabel("% of hidden tests")
kinds = ["simple", "complex", "hard"]
panel(axs[0, 1], kinds, lambda rs, k: mean([r["rate"] for r in rs if r["kind"] == k]) * 100, lambda v: f"{v:.0f}%", "Hidden tests passed, by difficulty", ymax=112, off=0.8)
axs[0, 1].set_xticklabels(["Simple (4)", "Complex (4)", "Hard: hidden rules (6)"])
panel(axs[1, 0], MODELS, by_model("tok"), lambda v: f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}k", "Tokens for each task, log scale", ylog=True)
axs[1, 0].set_ylim(5e4, 1.5e7); axs[1, 0].yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x/1e6:g}M" if x >= 1e6 else f"{x/1e3:g}k"))
panel(axs[1, 1], MODELS, lambda rs, m: mean([r["cost"] or 0 for r in rs if r["model"] == m]), lambda v: f"${v:.2f}", "Cost for each task (USD)", ymax=1.95, off=0.015)
h, l = axs[0, 0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, loc="upper right", ncol=3, fontsize=10, bbox_to_anchor=(0.985, 0.93))
fig.tight_layout(rect=(0.02, 0, 1, 0.9)); fig.savefig("benchmark-0.15.png", dpi=150); print("ok")
