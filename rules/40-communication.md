## Rule: communication

- Write in ASD-STE100 style: short sentences, active voice, one instruction in each sentence.
- Draw all diagrams in Mermaid, inside the Markdown file. Do not use images or ASCII art.
- Use the template of the artifact from the skill `magenta-templates`. Keep each artifact short. Link to details.
- Start each artifact with a header: work item, step, owner agent, status, and the inputs with their commit SHA (`git rev-parse --short HEAD`).
- An agent without a shell gets the commit SHA from the brief.
- End each artifact with a handoff note: done, open, next owner, and what to check.
- End your work with one Result block. The conductor reads only this block, so put all that the task needs in it, and nothing else:

```text
## Result
Status: DONE | BLOCKED | NEEDS-HUMAN
Summary: what you found or did, for the task, in three sentences at most
Changes: the files that you wrote or changed, and the commits (or "none")
Evidence: the last verify result, the test results, or the measurements (or "none")
Findings: one line for each finding: ID, severity (BLOCKER, MAJOR, MINOR), statement, file:line (or "none")
Needs the human: the question, the options, and your recommendation (only for NEEDS-HUMAN)
```

- Your output contract tells what goes in the Summary and the Findings for your role.
- Do not report internal steps: test locks, the verify state, hook messages, guard blocks that you solved, retries, or the tools that you used.
