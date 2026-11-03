# Results: 0.12.0 compared with 0.13.0 (2026-11-03)

Model: `claude-sonnet-5-5` (conductor and judge). 26 scenarios, 3 runs of each scenario for each version (78 pairs). Total cost of all rounds: about 26 USD.

## Final version (0.13.0)

| Measure | 0.12.0 | 0.13.0 |
|---|---|---|
| Judge: wins | 27 (35%) | **42 (54%)** (9 ties) |
| Judge: average score | 6.72 | **7.31** |
| Right owner of the domain decisions | 58 of 78 | **75 of 78** |
| A required agent is missing | 0 | 0 |
| An agent that the task does not need | 3 | 3 |
| Questions to the human before "done" (average) | 3.92 | **2.99** |
| Agents in the team (average) | 4.03 | 3.82 |
| Cost of the planning step | 3.66 USD | 3.83 USD |

## The rounds

The first form of the driver model was not good enough. Each round fixed the problems that the judge found:

| Round | Change | Wins 0.13 / 0.12 / tie | Average score 0.12 → 0.13 |
|---|---|---|---|
| 1 | The first driver model (20 scenarios × 2) | 21 / 11 / 8 | 6.47 → 7.20 |
| 2 | Signal precedence (CVE → security, index → data, incident → SRE); the Architect always drives a design; an ADR uses the standard lane | 27 / 9 / 4 | 6.45 → 7.22 |
| 3 | 6 new scenarios (26 × 2); the lead is the driver in the lite lane; QA stays for test thresholds | 26 / 17 / 9 | 6.75 → 7.19 |
| 4 | No extra review steps (the checker is a lens; plan review only in the full lane); no plan document when the driver is the lead; the driver keeps the owners of the files (26 × 3) | 38 / 27 / 13 | 6.71 → 7.23 |
| 5 | A design is done by review, not by checks; SRE checks a load test (26 × 3, final) | **42 / 27 / 9** | 6.72 → **7.31** |

## By scenario (final version, 3 runs)

| Scenario | 0.13 wins | 0.12 wins | Ties |
|---|---|---|---|
| s01 cart rounding tests | 3 | 0 | 0 |
| s02 order event contract | 3 | 0 | 0 |
| s03 flaky CI test | 2 | 0 | 1 |
| s04 double order bug | 2 | 1 | 0 |
| s05 endpoint p95 | 0 | 1 | 2 |
| s06 slow query and index | 1 | 2 | 0 |
| s07 cross-domain feature | 2 | 1 | 0 |
| s08 rename a config key | 2 | 1 | 0 |
| s09 CVE upgrade | 3 | 0 | 0 |
| s10 scope growth (`--auto`) | 1 | 2 | 0 |
| s11 LCP on mobile | 2 | 1 | 0 |
| s12 ADR for sessions | 1 | 2 | 0 |
| s13 noisy alerts | 1 | 1 | 1 |
| s14 backfill of 50M rows | 2 | 1 | 0 |
| s15 incident 5xx | 2 | 1 | 0 |
| s16 README option | 2 | 1 | 0 |
| s17 mutation testing in CI | 2 | 1 | 0 |
| s18 `--driver qa` | 3 | 0 | 0 |
| s19 investigation | 2 | 1 | 0 |
| s20 auth refactor | 0 | 1 | 2 |
| s21 Spring Boot 3 upgrade | 0 | 3 | 0 |
| s22 k6 load test | 0 | 1 | 2 |
| s23 dashboard and alerts | 2 | 1 | 0 |
| s24 Docker build speed | 2 | 0 | 1 |
| s25 login rate limit | 1 | 2 | 0 |
| s26 test suite speed | 1 | 2 | 0 |

## Findings

- The driver model gives the domain decisions to the right role much more often (75 of 78, not 58), with fewer questions to the human.
- The largest gains: test strategy (s01), design (s02), CVE (s09), incident (s15), and the `--driver` choice (s18).
- Only one scenario loses in all 3 runs: s21, the major framework upgrade. 0.12.0 adds an Architect review of the plan; 0.13.0 uses the lenses only in the standard lane. Candidate rule: a major version upgrade gets an Architect review of the plan.
- A 2-to-1 result is within the noise of 3 runs. Use 5 runs or more before a decision about one scenario.
