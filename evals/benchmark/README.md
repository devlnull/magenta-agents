# Benchmark: plain prompt against Magenta (2026-11-03)

14 coding tasks in small Python repositories, 4 Claude models, 2 modes, one run each (112 runs). The score is a set of hidden tests that the agent never sees.

- **Simple (4):** a pagination bug, discount rounding, a slugify option, an email validation refactor.
- **Complex (4):** order totals by a rules file, a login rate limit, a CSV import, an idempotent order save.
- **Hard (6):** each one has a rule that is not in the prompt but in the repository: a refund that must round down, a docstring contract under a speed target, a security file for a download, an architecture rule against stale cache reads, old file formats that must stay readable, and a public API that must not break.

Modes: **plain** is `claude -p "<task>"`. **magenta** is `claude -p "/magenta:magenta --auto <task>"` with the plugin 0.14.0, all agents on the same model, a prepared repository (confirmed profile, approved project check), and a simulated human who approves the checks that the agents propose.

![summary](benchmark-summary.png)
![tokens](benchmark-tokens-per-task.png)

| Model | Hidden tests, plain | Hidden tests, Magenta | All passed, plain / Magenta | Tokens for each task, plain / Magenta | Cost for each task, plain / Magenta |
|---|---|---|---|---|---|
| Opus 5.5 | 100% | 100% | 14 / 14 | 152k / 1.6M (×11) | $0.16 / $1.62 (×10) |
| Sonnet 5.5 | 97% | 100% | 13 / 14 | 155k / 815k (×5) | $0.07 / $0.40 (×6) |
| Sonnet 5 | 93% | 95% | 12 / 13 | 341k / 4.3M (×13) | $0.16 / $1.72 (×11) |
| Haiku 4.5 | 83% | 86% | 8 / 7 | 360k / 3.8M (×11) | $0.07 / $0.74 (×10) |
| **All** | **93.5%** | **95.3%** | **47 / 48 of 56** | 252k / 2.6M (×10) | $0.11 / $1.12 (×10) |

By difficulty (all models): simple 98% → 93%, complex 99% → 99%, hard 86% → 94%.

Other measures: tests left in the repository for each task: 1.0 (plain) against 11.5 (Magenta). Old tests broken: 2 runs (plain) against 1 (Magenta). Time for each task: 24 s against 321 s. Output tokens for each task: 2.1k against 30k. Total cost of the benchmark: about 70 USD.

## Findings

1. On clear, small tasks, Magenta gives no gain and costs about 10 times more. Opus 5.5 passed all tasks in both modes.
2. On hard tasks with hidden rules, Magenta gives +8 points: Haiku 4.5 68% → 88%, Sonnet 5 85% → 89%, Sonnet 5.5 93% → 100% (it found the security rules of the download). Opus 5.5: 100% in both modes.
3. On simple tasks, Magenta with Haiku 4.5 was worse (93% → 72%): the long process is too much for the small model.
4. Magenta leaves about 11 new tests for each task, and a work item with the checks. The hidden tests do not measure this value.

## Limits

- One run for each cell: one task can change a result by several points.
- Small repositories and tasks that one person wrote. Real repositories have more hidden rules.
- Headless runs, `bypassPermissions`, and a simulated approval.
- Tokens include the cached system prompt and the cached context, so the counts are high also for the plain runs.

## Run it again

```bash
tar -xf fixtures.tar                  # the tasks and the hidden tests
mkdir src && git -C <magenta-agents> archive v0.14.0 | tar -x -C src
python3 bench.py claude-opus-5-5,claude-sonnet-5-5 plain,magenta all 1 6
python3 analyze.py && python3 charts.py
```

# Magenta 0.15 (2026-11-03)

![0.15](benchmark-0.15.png)

0.15 changes: direct mode for small tasks (the conductor does the work itself, with the project checks), `verify begin`, `gate`, and `close` (fewer conductor turns), a conductor skill of 15 KB in place of 34 KB, a one-line result when all checks pass, and `verify context` (a script that finds the rule files and the callers of the changed functions, with no model tokens). Same tasks, same models, one run each.

| | Plain prompt | Magenta 0.14 | Magenta 0.15 |
|---|---|---|---|
| Hidden tests passed | 93.4% | 95.3% | **96.3%** |
| Tasks with all hidden tests passed | 47 of 56 | 48 of 56 | **50 of 56** |
| Old tests still pass | 54 of 56 | 55 of 56 | **56 of 56** |
| Tokens for each task | 252k | 2.64M | **836k** (−68%) |
| Cost for each task | $0.11 | $1.12 | **$0.40** (−64%) |
| Time for each task | 24 s | 321 s | **106 s** |

By model (hidden tests, 0.14 → 0.15; tokens saved): Opus 5.5 100% → 100% (−59%), Sonnet 5.5 100% → 97% (−71%; one security task raised `PermissionError` where the rule says `ValueError`), Sonnet 5 95% → 98% (−59%), Haiku 4.5 86% → 90% (−82%). By difficulty: simple 93% → 97%, complex 99% → 99%, hard 94% → 94%. The conductor selected direct mode in 34 of 56 runs.
