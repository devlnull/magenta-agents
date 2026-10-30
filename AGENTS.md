# Working in the magenta-agents repository

This repository is the canonical source of the Magenta agents (RFC-0001, option C).

## Rules for changes

1. Edit the canonical source only: `agents/`, `rules/`, `skills/`, `templates/`, `workflows/`, `models.yaml`, `magenta.yaml`.
2. Do not edit `dist/`. The build generates it.
3. Keep the source tool-neutral. Tool-specific logic goes into `adapters/`.
4. Write all prose in ASD-STE100 style: short sentences, active voice, one instruction in each sentence.
5. Draw all diagrams in Mermaid, inside the Markdown file.
6. Each file in a work item has one owner agent. Do not give one path to two agents.
7. Record each durable decision as an ADR in `docs/adr/`.

## Commands

```bash
python3 magenta.py validate          # check the source
python3 -m unittest discover -s tests  # run the tests
python3 magenta.py build             # generate dist/claude-code
python3 magenta.py install           # install into ~/.claude
```

After a change to the rules, the agents, or the model mapping, run the evals (`evals/README.md`).

## More commands (phases 2 to 5)

```bash
python3 magenta.py install --target opencode   # or codex, or gemini
python3 magenta.py lock <repo> <work-item>       # human, after the acceptance tests are reviewed
python3 magenta.py check-lock <repo> <work-item>
python3 magenta.py run prd-review --repo <repo> --prd <file>
python3 magenta.py run pr-review --repo <repo> --base origin/main
python3 magenta.py metrics <repo> [<repo> ...]
MAGENTA_DIST=/tmp/dist python3 magenta.py build  # build somewhere else
```
