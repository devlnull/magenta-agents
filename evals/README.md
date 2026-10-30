# Evals

Evals tell us if a change to the rules, the prompts, or the model mapping makes an agent better or worse (RFC-0001, section 12).

## Phase 1 target

Five golden tasks for each advisor agent: PM, Architect, Principal, and QA.

## Make a golden task

1. Copy `tasks/TEMPLATE.md` to `tasks/<agent>-<nn>-<slug>.md`.
2. Use a real, closed case: a past PRD, a past design decision, a closed bug, or a merged pull request.
3. Prepare a snapshot of the repository at the commit before the result, without the later history. Then the agent cannot find the answer in `git log`:
   `mkdir /tmp/eval-<id> && git -C <repo> archive <commit> | tar -x -C /tmp/eval-<id>`
4. Write the expected result: what a senior human found or decided.
5. Do not put confidential data in this repository. Keep the snapshot path and the expected result in a private location if necessary.

## Run a golden task (manual, phase 1)

1. Open Claude Code in the snapshot folder.
2. Give the agent the task prompt from the task file, for example `@magenta-qa ...`.
3. Score the output with the rubric of the agent (`rubrics/<agent>.md`). Score each criterion 0, 1, or 2.
4. Record the score, the model profile, the turns, and the date in the task file.

Phase 4 automates this with the runner and an LLM judge.

## When to run

- After each change to `rules/`, `agents/`, `skills/`, or `models.yaml`.
- Before you change a model profile to a new model.
