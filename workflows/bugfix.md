## Playbook: bugfix

1. Conductor: write the brief: the symptom, the expected and the actual behavior, the environment, and the evidence (logs and tickets in `UNTRUSTED` blocks).
2. `qa`: reproduce the bug. Write the smallest failing test that shows it, at the lowest level that reproduces it. If QA cannot reproduce it, stop and ask the human for more data.
3. `engineer`: find the root cause with the skill `root-cause-analysis`. For a difficult bug, the conductor runs competing hypotheses (pattern P9): two or three investigators in parallel (`engineer`, `architect`, `qa`), read-only, each tries to prove or disprove one hypothesis.
4. Plan gate (standard lane): the root cause, the fix plan, and the constraint ledger.
5. `engineer`: fix the root cause, not the symptom. Use TDD. The reproduction test must pass. Keep the change small.
6. `qa`: run all tests. Add tests for the edge cases near the root cause. Search for the same defect in similar code. Write `07-qa-report.md`.
7. `principal`: final review with the constraint check. Add `architect` for a structural root cause.
8. Done gate: the root cause, the fix, the tests, the risks, and the follow-ups that prevent the same class of bug.
