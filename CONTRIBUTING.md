# Contributing

Thank you for your help. This guide shows how to change Magenta and how to send the change.

## Set up

Requirements: Python 3.9 or later and git. Magenta uses only the Python standard library.

```bash
git clone https://github.com/devlnull/magenta-agents.git && cd magenta-agents
python3 magenta.py validate
python3 -m unittest discover -s tests
```

## How the repository works

Magenta is "agents as code". You edit the canonical source. The build generates the files of each tool. See [docs/architecture.md](docs/architecture.md).

| Edit | Do not edit |
|---|---|
| `agents/`, `rules/`, `skills/`, `templates/`, `workflows/`, `adapters/`, `magenta.yaml`, `models.yaml` | `dist/` and `plugins/` (generated) |

After a change, run `python3 magenta.py build`. It also updates the committed plugin. CI fails if the plugin is not current (`python3 magenta.py check`).

## Rules for changes

1. **Tool-neutral source.** Logic for one tool goes into `adapters/`.
2. **ASD-STE100 style** for all prose, also the prompts of the agents: short sentences, active voice, one instruction in each sentence. Clear text helps the people and the models.
3. **Mermaid** for all diagrams, inside the Markdown file. No images, no ASCII art.
4. **One owner for each file.** Each artifact and each checks file has one owner agent. `magenta.py validate` checks this.
5. **Decisions as ADRs.** Record each durable decision in `docs/adr/` with the next number.
6. **Tests.** Add or change tests in `tests/` for each change of behavior. Tests run on macOS, Linux, and Windows, with Python 3.9 and 3.13.
7. **Evals.** After a change to the rules, the agents, the skills, or the model mapping, run the evals ([evals/README.md](evals/README.md)).
8. **Changelog.** Add a line under "Unreleased" in [CHANGELOG.md](CHANGELOG.md).

## Send a change

1. Open an issue first for a large change, so that we can agree on the approach.
2. Make a branch. Keep the change small and focused.
3. Run `python3 magenta.py validate`, `python3 magenta.py build`, `python3 magenta.py check`, and the tests.
4. Open a pull request. Fill in the template.

## Release

Maintainers follow [docs/releasing.md](docs/releasing.md).

## Code of conduct

This project follows the [code of conduct](CODE_OF_CONDUCT.md).
