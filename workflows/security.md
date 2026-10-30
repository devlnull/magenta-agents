## Playbook: security

1. Conductor: write the brief. Put the vulnerability report or the scanner output in an `UNTRUSTED` block. Do not copy secrets.
2. `principal`: make a threat model with the skill `threat-model-stride` for the affected flow. Rate the risk.
3. `architect`: find the structural cause (trust boundaries, authorization model, data exposure).
4. `qa`: write a test that proves the vulnerability (safely, in the test environment only).
5. Plan gate (full lane for money, personal data, or authentication flows).
6. `engineer`: fix with TDD. Do not log sensitive data.
7. `qa`: verify the fix and the related abuse cases. `principal`: final review with the constraint check.
8. Done gate. The human decides the disclosure and the release.
