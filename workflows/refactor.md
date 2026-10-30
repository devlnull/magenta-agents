## Playbook: refactor (improvement)

1. Conductor: write the brief: the reason (readability, duplication, coupling, tech debt), the scope, and how to measure the improvement (for example complexity, duplication, dependency rules).
2. `architect`: describe the target structure and the steps. Write a fitness function when the target is a structural rule.
3. `qa`: write characterization tests that lock the current behavior of the scope (skill `safe-refactoring`).
4. Plan gate (standard lane).
5. `engineer`: refactor in small steps. Each step keeps all tests green. Keep refactoring commits separate from behavior changes. No behavior change in this playbook.
6. `qa`: run all tests and the characterization tests. Compare the behavior.
7. `principal`: final review with the constraint check. Confirm that the improvement is measurable.
8. Done gate.
