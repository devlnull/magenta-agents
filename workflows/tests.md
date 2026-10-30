## Playbook: tests

Use it to add tests, increase useful coverage, fix flaky tests, or make the tests faster.

1. Conductor: write the brief with the goal (for example "cover the order cancel rules" or "remove the flaky test X").
2. `qa`: analyze the risks and the current tests. Select the test levels. For a flaky test, find the cause (time, order, shared state, network, concurrency).
3. `qa`: write the tests. `engineer` changes production code only when a test needs a seam, and only with a small, separate commit.
4. `qa`: run the tests several times to prove that they are stable.
5. `principal` (when CI for the team changes): review. Done gate.
