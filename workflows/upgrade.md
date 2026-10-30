## Playbook: upgrade

1. Conductor: write the brief: the dependency, the current and the target version, and the reason (security, support, features).
2. `engineer`: read the release notes and the migration guide. List the breaking changes that affect the project, with file references.
3. `architect` (major version or breaking change): assess the impact on the structure and the contracts.
4. `qa`: list the tests that cover the affected areas. Add tests where the coverage is missing.
5. Plan gate (standard lane).
6. `engineer`: upgrade in small steps. Fix the deprecations. Do not mix the upgrade with other changes.
7. `qa`: run all tests. Compare the behavior and, for runtime upgrades, the performance.
8. `principal`: final review with the rollback plan and the constraint check. Done gate.
