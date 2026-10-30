---
name: write-rfc
description: Write a design for a work item, as a short design note (standard lane) or a full RFC (full lane), with options, trade-offs, contracts, NFR budgets, and Mermaid diagrams.
---

# Write a design note or an RFC

## Select the form

- Standard lane: a design note. Maximum two pages.
- Full lane: an RFC. Two or three options are mandatory.

## Design note sections

1. Context and scope (link the stories).
2. Proposed design, with one Mermaid diagram.
3. Contracts: API, events, data ownership.
4. NFR budgets with numbers.
5. Risks and open questions.
6. Decisions: each one with a mark, one-way door or two-way door.

## RFC sections

1. Summary.
2. Context, goals, and non-goals.
3. Options (two or three), each with a diagram.
4. Trade-off matrix (skill `tradeoff-matrix`) and the recommendation.
5. Contracts and data ownership.
6. NFR budgets.
7. Migration and rollout plan (incremental steps, exit criteria).
8. Fitness functions.
9. Risks, objections, and open questions.
10. Decisions that need an ADR.

## Rules

- Use the RFC or design note template from the skill `magenta-templates`.
- Follow the stack and the patterns of the project context.
- Each number has a source or the label `ASSUMPTION:`.
