## Workflow: design review (Design Review Board)

Use it for one-way-door decisions.

1. `architect` writes the options and the trade-off matrix in `03-design.md`.
2. `principal` starts these critics in parallel, each as a new subagent with a clean context and read-only work: `product-manager` (value and scope), `qa` (testability and risk), `engineer` (feasibility and effort), and `architect` in a second instance as a devil's advocate.
3. Each critic returns: the top three risks, the preferred option, and one question. Each critic returns its result in its final message. It does not write files.
4. `principal` writes a synthesis decision note in `decisions/`.
5. The human decides. `architect` records the result in an ADR.
