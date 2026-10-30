# Evals

Evals tell us if a change to the rules, the prompts, or the model mapping makes an agent better or worse (RFC-0001, section 12).

## Target

Five golden tasks for each advisor agent: PM, Architect, Principal, and QA.

## Make a golden task

1. Copy `tasks/TEMPLATE.md` to `tasks/<agent>-<nn>-<slug>.md`.
2. Use a real, closed case: a past PRD, a past design decision, a closed bug, or a merged pull request.
3. Prepare a snapshot of the repository at the commit before the result, without the later history. Then the agent cannot find the answer in `git log`:
   `mkdir /tmp/eval-<id> && git -C <repo> archive <commit> | tar -x -C /tmp/eval-<id>`
4. Write the expected result: what a senior human found or decided.
5. Do not put confidential data in this repository. Keep the snapshot path and the expected result in a private location if necessary.

## Run a golden task (manual)

1. Open Claude Code in the snapshot folder.
2. Give the agent the task prompt from the task file, for example `@magenta-qa ...`.
3. Score the output with the rubric of the agent (`rubrics/<agent>.md`). Score each criterion 0, 1, or 2.
4. Record the score, the model profile, the turns, and the date in the task file.

The headless runner (`runner/`) can run the task prompt without a session.

## Compare the modes (ADR-0012)

These evals tell us if the conductor helps on daily tasks, and when team mode is worth its cost. Use real, closed cases: bugs, performance work, refactors, and small features.

1. Copy `tasks/TEMPLATE-conductor.md` to `tasks/conductor-<nn>-<slug>.md`. Write the task type, the hidden check, and the constraints.
2. Prepare a fresh snapshot for each run (step 3 above). Each run starts from the same commit.
3. Run the same task prompt in three modes, with the same model:
   - **plain:** the tool without Magenta. Give only the task prompt.
   - **default:** `/magenta <task prompt>`.
   - **team:** `/magenta --team <task prompt>`.
4. Score each run:
   - **Correct:** run the hidden check, and read the result. Write yes, partial, or no.
   - **Rule breaks:** count the constraints that the result breaks. A changed test or a weakened check counts as a rule break.
   - **Cost and time:** use `/cost` in Claude Code, or the summary of the runner.
5. Add one row for each run to the "Runs" table of the task.
6. Run `python3 magenta.py eval-summary` to compare the modes for each task type.

Decision rules (defaults; change them when the data shows a better rule):

- Keep the default mode when it is at least as correct as plain mode, with fewer rule breaks, at less than twice the cost.
- Keep a team trigger for a task type only when team mode is more correct than the default mode for that task type.
- Run each task at least three times in each mode before you decide. Model results change from run to run.

## When to run

- After each change to `rules/`, `agents/`, `skills/`, or `models.yaml`.
- Before you change a model profile to a new model.
