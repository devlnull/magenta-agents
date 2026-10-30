---
name: technical-writing
description: Write and update documentation in ASD-STE100 style, with the correct document type (tutorial, how-to, reference, explanation), tested examples, and Mermaid diagrams. Use it for each documentation change.
---

# Technical writing

## Document types

Keep one type in each page. Mixed types are hard to use.

| Type | The reader wants to | Content |
|---|---|---|
| Tutorial | learn by doing | One path that works, from start to a result |
| How-to guide | do a task | Steps for one task, with the prerequisites |
| Reference | look up a fact | Complete and exact lists: commands, options, fields, errors |
| Explanation | understand | Concepts, reasons, and trade-offs |

## ASD-STE100 rules (the most important ones)

1. Write short sentences: a maximum of 20 words in procedures and 25 words in descriptions.
2. Use the active voice.
3. Write one instruction in each sentence. Use the imperative: "Run the command."
4. Use one word for one meaning. Do not change the term for the same thing.
5. Use simple verbs: "use", not "utilize"; "start", not "initiate".
6. Do not use "it" or "this" when the reader cannot see what they refer to.
7. Write numbered steps for a procedure. Write a table for a comparison.
8. Put a warning or a caution before the step that it is about.

## Examples and facts

- Copy commands, options, and output from the code or from a real run. Do not invent them.
- Use example values that are clearly examples (`example.com`, `<your-repo>`).
- Never copy secrets, internal hostnames, or customer data.

## Diagrams

Draw diagrams in Mermaid inside the Markdown file. Keep one idea in each diagram. Render the diagram (`mmdc -i file.mmd -o file.svg`) to find syntax errors.

## Changelog and release notes

- Follow [Keep a Changelog](https://keepachangelog.com): sections Added, Changed, Deprecated, Removed, Fixed, Security, under "Unreleased".
- Write for the user: what changed for them, and what they must do.

## Checks

Propose documentation checks to the Principal for `project.yaml`, for example `npx markdownlint-cli2 "**/*.md"` and a link check (`lychee docs/`).
