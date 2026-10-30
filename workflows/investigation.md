## Playbook: investigation

Use it for a question or an analysis without a change.

1. Conductor: write the question and what a good answer contains. A work item is not necessary, unless the human asks for one.
2. Select only the experts that the question needs. Run them in parallel, read-only, each with a clear sub-question. Examples: `engineer` traces the code; `architect` explains the structure and the decisions; `qa` examines the tests and the risks; `principal` examines operations.
3. Conductor: merge the answers. Remove duplicates. Mark disagreements and give the evidence of each side.
4. Report: the answer, the evidence (file and line, command output), the confidence, and the open questions. If a change is useful, propose the task type and the playbook for it. Do not change code.
