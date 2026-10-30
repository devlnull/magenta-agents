# Rubric: Software Engineer

Score each criterion: 0 (no), 1 (partly), 2 (yes).

1. All tests pass, including the locked acceptance tests, and `check-lock` passes.
2. For a bug: the agent first wrote a test that reproduces the bug.
3. The diff stays inside the scope of the task. It is small compared with the real human fix.
4. The code follows the patterns of the module (no foreign patterns, no new dependency without a CDR).
5. Error handling, idempotency, and concurrency are correct where the task needs them.
6. The hot paths have a stated complexity or a measurement.
7. The implementation notes are complete and honest about what is not done.
