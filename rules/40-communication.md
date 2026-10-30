## Rule: communication

- Write in ASD-STE100 style: short sentences, active voice, one instruction in each sentence.
- Draw all diagrams in Mermaid, inside the Markdown file. Do not use images or ASCII art.
- Use the template of the artifact from the skill `magenta-templates`. Keep each artifact short. Link to details.
- Start each artifact with a header: work item, step, owner agent, status, and the inputs with their commit SHA (`git rev-parse --short HEAD`).
- An agent without a shell gets the commit SHA from the brief.
- End each artifact with a handoff note: done, open, next owner, and what to check.
- In your final message, give: status (DONE, BLOCKED, or NEEDS-HUMAN), the files that you wrote, and your questions for the human.
