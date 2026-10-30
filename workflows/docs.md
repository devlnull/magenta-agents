## Playbook: docs

Use it to write or update documentation without a code change.

1. Conductor: write the brief: the readers, the document type (tutorial, how-to guide, reference, or explanation), and the source of truth (code, ADRs, the expert).
2. `writer`: write or update the documents with the skill `technical-writing`. Copy commands and options from the code. Ask questions instead of guessing.
3. The owner of the subject reviews the facts, read-only: for example `architect` for a design guide, `sre` for an operations guide, `platform` for a deployment guide.
4. Run the Markdown lint and the link check, when the project has them.
5. Done gate.
