## Workflow: pull request review panel

Use it for a pull request or a local diff.

1. `principal` gets the diff (`git diff <base>...HEAD`) and the related work item, if one exists.
2. `principal` starts three reviewers in parallel, read-only, each with a clean context:
   - `qa`: tests, edge cases, and acceptance criteria coverage.
   - `architect`: structure, boundaries, contracts, and conventions.
   - `principal` (a new instance): operability, security, and production readiness.
3. Each reviewer returns findings with severity, file and line, risk, and fix in its final message.
4. `principal` merges the findings into one report, removes duplicates, and writes `07-review.md` if a work item exists. If not, it gives the report in the conversation.

The conductor can run this panel directly for the task type "review". Each reviewer also checks the constraint ledger of the related work item, if one exists.
