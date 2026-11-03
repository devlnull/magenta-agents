"""Chart for 0.16: plain prompt against Magenta 0.16, 3 runs, 2 models."""
import json, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
S = json.load(open("all-0.16.json"))
def avg(rs, f): return sum(f(r) for r in rs) / len(rs) if rs else 0
groups = [("Sonnet 5.5", "claude-sonnet-5-5", None), ("Haiku 4.5", "claude-haiku-4-5", None)] + \
         [(k.capitalize(), None, k) for k in ("simple", "complex", "hard", "held-out")] + [("All", None, None)]
sel = lambda rs, m, k: [r for r in rs if (m is None or r["model"] == m) and (k is None or r["kind"] == k)]
fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
x = range(len(groups)); w = 0.38
for i, (mode, c) in enumerate((("plain", "#8a8f98"), ("0.16", "#c2185b"))):
    v = [avg(sel(S[mode], m, k), lambda r: r["rate"]) * 100 for _, m, k in groups]
    b = ax[0].bar([j + (i - .5) * w for j in x], v, w, label="Plain prompt" if mode == "plain" else "Magenta 0.16", color=c)
    ax[0].bar_label(b, fmt="%.0f", fontsize=8)
    t = [avg(sel(S[mode], m, None), lambda r: r["cost"] or 0) for _, m, _ in groups[:2]] + [avg(S[mode], lambda r: r["cost"] or 0)]
    b2 = ax[1].bar([j + (i - .5) * w for j in range(3)], t, w, color=c, label="Plain prompt" if mode == "plain" else "Magenta 0.16")
    ax[1].bar_label(b2, fmt="$%.3f", fontsize=8)
ax[0].set_xticks(list(x), [g[0] for g in groups]); ax[0].set_ylim(60, 105); ax[0].set_ylabel("Hidden tests passed (%)")
ax[0].set_title("Quality (18 tasks × 3 runs)"); ax[0].legend(loc="lower left")
ax[1].set_xticks(range(3), ["Sonnet 5.5", "Haiku 4.5", "All"]); ax[1].set_ylabel("Cost for each task (USD)"); ax[1].set_title("Cost")
ax[1].set_ylim(0, 0.18); ax[1].legend(loc="upper left")
fig.suptitle("Magenta 0.16 against a plain prompt"); fig.tight_layout(); fig.savefig("benchmark-0.16.png", dpi=130)
