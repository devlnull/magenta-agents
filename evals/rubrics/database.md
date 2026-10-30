# Rubric: Database Engineer

Score each criterion: 0 (no), 1 (partly), 2 (yes).

1. The migration plan keeps the service online: expand and contract, no blocking locks for the table size.
2. The old and the new code work with each schema state.
3. Each step has a verification and a rollback. One-way steps go to the human.
4. Backfills run in batches, are idempotent, and can resume.
5. Query recommendations use real plans, and state the cost on writes.
6. The checks cover the migration (lint, up and down) and the hot queries.
