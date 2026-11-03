"""The benchmark images of the README, made from results/v*.json. release.py publish calls make_all."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

import release as R

PLAIN, MAGENTA = "#3f7fc4", "#c2185b"          # validated pair (dataviz validator, light and dark)
INK, MUTED, GRID, SURFACE = "#1f2328", "#59636e", "#e6e8eb", "#ffffff"
FONT = "Inter" if any("Inter" in f.name for f in font_manager.fontManager.ttflist) else "DejaVu Sans"
plt.rcParams.update({
    "font.family": FONT, "font.size": 11, "text.color": INK, "axes.labelcolor": MUTED, "axes.edgecolor": GRID,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "svg.hashsalt": "magenta", "savefig.dpi": 160,
})
META = {"Software": None, "Creation Time": None}  # the same data gives the same file


def _bars(ax, labels, plain, magenta, fmt, ylim=None, delta=True):
    x = range(len(labels)); w = 0.36
    for off, vals, color, name in ((-w / 2 - 0.01, plain, PLAIN, "Plain prompt"), (w / 2 + 0.01, magenta, MAGENTA, "Magenta")):
        bars = ax.bar([i + off for i in x], vals, w, color=color, label=name, zorder=2)
        ax.bar_label(bars, labels=[fmt(v) for v in vals], padding=3, fontsize=10, color=INK)
    if delta:
        for i, (p, m) in enumerate(zip(plain, magenta)):
            d = m - p
            if abs(d) >= 0.5:
                ax.annotate(f"{d:+.0f} pts", (i, max(p, m)), xytext=(0, 20), textcoords="offset points", ha="center",
                            fontsize=10, fontweight="bold", color=MAGENTA if d > 0 else MUTED)
    ax.set_xticks(list(x), labels)
    ax.tick_params(axis="x", length=0, labelsize=11, labelcolor=INK)
    if ylim:
        ax.set_ylim(*ylim)


def _title(fig, title, sub):
    fig.text(0.03, 0.95, title, fontsize=17, fontweight="bold", va="top")
    fig.text(0.03, 0.885, sub, fontsize=11, color=MUTED, va="top")


def _legend(fig):
    fig.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=PLAIN), plt.Rectangle((0, 0), 1, 1, color=MAGENTA)],
               labels=["Plain prompt", "Magenta"], loc="upper right", bbox_to_anchor=(0.98, 0.84), frameon=False,
               ncol=2, fontsize=11)


def _save(fig, path):
    fig.savefig(path, metadata=META)
    plt.close(fig)


def headline(v, out):
    """Hard tasks for each model: the main result."""
    s = R.summary(v)
    models = v["setup"]["models"]
    hard = lambda mode, m=None: R.stats(R.select(v, mode, model=m, kind="hard"))["hidden"]
    labels = [R.NAMES[m] for m in models] + ["All models"]
    plain = [hard("plain", m) for m in models] + [s["by_kind"]["hard"]["plain"]["hidden"]]
    mag = [hard("magenta", m) for m in models] + [s["by_kind"]["hard"]["magenta"]["hidden"]]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    fig.subplots_adjust(top=0.78, bottom=0.1, left=0.07, right=0.98)
    _bars(ax, labels, plain, mag, lambda x: f"{x:.0f}%", ylim=(0, 115))
    ax.set_ylabel("Hidden tests passed (%)"); ax.set_yticks([0, 25, 50, 75, 100])
    _title(fig, "Hard tasks: Magenta finds the rules that the request does not say",
           f"Hidden tests passed on the hard tasks (security, rounding, stored formats, caches). "
           f"Magenta {v['version']}, {v['setup']['runs_per_task']} runs of each task.")
    _legend(fig)
    _save(fig, out / "headline.png")


def by_kind(v, out):
    s = R.summary(v)["by_kind"]
    kinds = [k for k in R.KINDS if k in s]
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.subplots_adjust(top=0.78, bottom=0.1, left=0.07, right=0.98)
    _bars(ax, [R.KIND_TEXT[k].replace(" (", "\n(") for k in kinds], [s[k]["plain"]["hidden"] for k in kinds],
          [s[k]["magenta"]["hidden"] for k in kinds], lambda x: f"{x:.0f}%", ylim=(0, 115))
    ax.set_ylabel("Hidden tests passed (%)"); ax.set_yticks([0, 25, 50, 75, 100])
    _title(fig, "Quality by kind of task", f"All models. Magenta {v['version']}.")
    _legend(fig)
    _save(fig, out / "by-kind.png")


def by_model(v, out):
    s = R.summary(v)["by_model"]
    models = v["setup"]["models"]
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.subplots_adjust(top=0.78, bottom=0.1, left=0.07, right=0.98)
    _bars(ax, [R.NAMES[m] for m in models], [s[m]["plain"]["hidden"] for m in models],
          [s[m]["magenta"]["hidden"] for m in models], lambda x: f"{x:.0f}%", ylim=(0, 115))
    ax.set_ylabel("Hidden tests passed (%)"); ax.set_yticks([0, 25, 50, 75, 100])
    _title(fig, "Quality by model, all tasks", f"Magenta {v['version']}.")
    _legend(fig)
    _save(fig, out / "by-model.png")


def cost(v, out):
    s = R.summary(v)
    models = v["setup"]["models"]
    labels = [R.NAMES[m] for m in models] + ["All models"]
    plain = [s["by_model"][m]["plain"]["cost"] for m in models] + [s["all"]["plain"]["cost"]]
    mag = [s["by_model"][m]["magenta"]["cost"] for m in models] + [s["all"]["magenta"]["cost"]]
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.subplots_adjust(top=0.78, bottom=0.1, left=0.08, right=0.98)
    _bars(ax, labels, plain, mag, lambda x: f"${x:.2f}", ylim=(0, max(plain + mag) * 1.25), delta=False)
    ax.set_ylabel("API cost for each task (USD)")
    ax.yaxis.set_major_formatter(lambda x, _: f"${x:.2f}")
    _title(fig, "Cost for each task", f"Model API prices, with prompt caching. Magenta {v['version']}.")
    _legend(fig)
    _save(fig, out / "cost.png")


def history(vs, out):
    """Each version on the 14 tasks that all versions ran."""
    rows = []
    for v in vs:
        p = R.stats(R.select(v, "plain", tasks=R.CORE)); m = R.stats(R.select(v, "magenta", tasks=R.CORE))
        rows.append((v["version"], p, m))
    names = [f"v{r[0]}" for r in rows]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.8))
    fig.subplots_adjust(top=0.70, bottom=0.11, left=0.07, right=0.98, wspace=0.28)
    x = list(range(len(rows)))
    a1.plot(x, [r[2]["hidden"] for r in rows], color=MAGENTA, lw=2, marker="o", ms=8, zorder=3)
    a1.plot(x, [r[1]["hidden"] for r in rows], color=PLAIN, lw=2, marker="o", ms=8, ls="--", zorder=3)
    for i, r in enumerate(rows):
        a1.annotate(f"{r[2]['hidden']:.1f}%", (i, r[2]["hidden"]), xytext=(0, 9), textcoords="offset points",
                    ha="center", fontsize=10)
        a1.annotate(f"{r[1]['hidden']:.1f}%", (i, r[1]["hidden"]), xytext=(0, -17), textcoords="offset points",
                    ha="center", fontsize=10, color=MUTED)
    lo = min(min(r[1]["hidden"], r[2]["hidden"]) for r in rows)
    a1.set_ylim(lo - 6, 101); a1.set_xticks(x, names); a1.set_xlim(-0.3, len(x) - 0.7)
    a1.set_title("Hidden tests passed (%)", loc="left", fontsize=12, color=INK)
    w = 0.36
    for off, i, color in ((-w / 2 - 0.01, 1, PLAIN), (w / 2 + 0.01, 2, MAGENTA)):
        bars = a2.bar([j + off for j in x], [r[i]["cost"] for r in rows], w, color=color, zorder=2)
        a2.bar_label(bars, labels=[f"${r[i]['cost']:.2f}" for r in rows], padding=3, fontsize=10)
    a2.set_xticks(x, names); a2.set_title("Cost for each task (USD)", loc="left", fontsize=12, color=INK)
    a2.yaxis.set_major_formatter(lambda v, _: f"${v:.2f}")
    for a in (a1, a2):
        a.tick_params(axis="x", length=0, labelcolor=INK)
    q0, q1, c0, c1 = rows[0][2]["hidden"], rows[-1][2]["hidden"], rows[0][2]["cost"], rows[-1][2]["cost"]
    _title(fig, f"Since v{rows[0][0]}: hidden tests {q0:.1f}% → {q1:.1f}%, cost for each task {(c1 / c0 - 1) * 100:+.0f}%",
           "The 14 tasks that every version ran, with the models of that run.")
    _legend(fig)
    _save(fig, out / "versions.png")


def card(vs, out):
    """A 1280 x 640 image to share (the GitHub social preview)."""
    v = vs[-1]; s = R.summary(v)
    hard = s["by_kind"]["hard"]
    best = max(v["setup"]["models"], key=lambda x: (s["by_model"][x]["magenta"]["hidden"], -s["by_model"][x]["magenta"]["cost"]))
    b = s["by_model"][best]["magenta"]
    fig = plt.figure(figsize=(12.8, 6.4), dpi=100)
    fig.patch.set_facecolor("#15121a")
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 1280); ax.set_ylim(0, 640)
    ax.add_patch(FancyBboxPatch((0, 0), 1280, 10, boxstyle="square", color=MAGENTA))
    ax.text(70, 540, "Magenta Agents", fontsize=40, fontweight="bold", color="white")
    ax.text(70, 488, "Role-based AI agents for Claude Code. Done means the checks pass.", fontsize=18, color="#c9c3d1")
    tiles = [(f"{hard['plain']['hidden']:.0f}% → {hard['magenta']['hidden']:.0f}%", "hidden tests passed\non hard tasks"),
             (f"{b['hidden']:.0f}%", f"hidden tests, {R.NAMES[best]}\n(${b['cost']:.2f} for each task)")]
    if len(vs) > 1:
        first = R.stats(R.select(vs[0], "magenta", tasks=R.CORE))["cost"]
        now = R.stats(R.select(v, "magenta", tasks=R.CORE))["cost"]
        tiles.append((f"−{(1 - now / first) * 100:.0f}%", f"cost for each task\nsince v{vs[0]['version']}"))
    for i, (big, small) in enumerate(tiles):
        x0 = 70 + i * 385
        ax.add_patch(FancyBboxPatch((x0, 120), 350, 270, boxstyle="round,pad=0,rounding_size=18", color="#231d2b"))
        ax.text(x0 + 30, 290, big, fontsize=40 if len(big) < 9 else 33, fontweight="bold", color="#f06292")
        ax.text(x0 + 30, 160, small, fontsize=17, color="#c9c3d1", linespacing=1.4)
    ax.text(70, 50, f"v{v['version']} benchmark: {len(v['setup']['tasks'])} tasks, {len(v['setup']['models'])} Claude models, "
                    f"{v['setup']['runs_per_task']} runs each, hidden tests", fontsize=13, color="#8d8696")
    fig.savefig(out / "card.png", facecolor=fig.get_facecolor(), metadata=META, dpi=100)
    plt.close(fig)


def make_all(vs, out):
    v = vs[-1]
    headline(v, out); by_kind(v, out); by_model(v, out); cost(v, out); card(vs, out)
    if len(vs) > 1:
        history(vs, out)
