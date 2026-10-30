## Lane: lite

Use it for a bug fix or a small change in one module, with low risk, that is easy to revert.

1. `principal`: triage, select the lane, write `04-plan.md` with one task.
2. `engineer` or `frontend`: fix with TDD. For a bug, first write a test that reproduces it.
3. `qa`: quick check. Write `07-qa-report.md`.
4. `principal`: review (rollback and observability only). Write `07-review.md`.
5. Gate 3, merge (human).
