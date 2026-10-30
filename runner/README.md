# Headless runner (phase 4)

The runner runs fixed workflows without a user interface, for example in CI. It calls existing harnesses as workers. It does not run workflows with human gates; those stay interactive.

## Workflows

| Workflow | Command | Result |
|---|---|---|
| PRD review | `python3 magenta.py run prd-review --repo <repo> --prd <file> [--id <ID>]` | A new work item with `00-request.md` and `01-prd-review.md` |
| PR review panel | `python3 magenta.py run pr-review --repo <repo> --base origin/main [--item <ID>]` | One merged findings report from QA, Architect, and Principal |

Common options: `--budget-usd`, `--max-turns`, `--engine`, `--output <file>`, `--fail-on-blocker` (exit 3), and `--dry-run`.

## Engines and models

Each model profile in `models.yaml` has a `runner` entry, for example `{engine: opencode, model: "openai/<model-id>"}`. The `engines` section has the command template of each engine. To use a new CLI, add a template. You do not need to change code.

## Logs and budget

- Each step appends one line to `.magenta/runs/runs.jsonl`: agent, engine, status, turns, cost, and time.
- The output of each step is in `.magenta/runs/<run-id>-<workflow>/`.
- When the cost reaches `--budget-usd`, the runner stops before the next step.

## CI

- GitLab: `ci/gitlab-ci.magenta.yml`
- GitHub: `ci/github-actions.magenta.yml`

Start in advisory mode (`allow_failure`). Use `--fail-on-blocker` only after the team trusts the panel.

## Gateway

`runner/litellm.example.yaml` shows one gateway for Anthropic, OpenAI, Gemini, Grok, and a self-hosted model.
