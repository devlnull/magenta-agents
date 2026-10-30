## Lane: lite

Use it for a bug fix or a small change in one module, with low risk, that is easy to revert.

1. `principal`: triage, select the lane, write `04-plan.md` with one task.
2. `qa`: for a bug, write a test that reproduces it, and its check. The conductor locks the test, and the human approves the check.
3. `engineer` or `frontend`: fix with TDD. Run verify until all checks pass.
4. `qa`: quick check: run verify. Write `07-qa-report.md`.
5. `principal`: review (rollback and observability only). Write `07-review.md`.
6. Gate 3, merge (human).
