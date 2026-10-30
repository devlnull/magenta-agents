# Conductor task: <nn>-<slug>

| Field | Value |
|---|---|
| Task type | <bug, performance, improvement, feature, tests, upgrade, incident, security, design, review, or investigation> |
| Source case | <link to the closed bug, the merged pull request, or the incident> |
| Snapshot | <repository and commit before the fix, without the later history> |
| Hidden check | <a command or a test that only the scorer runs. It passes when the result is correct.> |
| Constraints | <the rules that the result must keep: ADRs, boundaries, contracts, thresholds, conventions> |

## Task prompt

```text
<the exact request, as you type it after /magenta (plain mode: the same text, without /magenta)>
```

## Expected result

<the fix or the decision of the senior human; the key points that a good result has>

## Runs

Mode: plain (the tool without Magenta), default (`/magenta <task>`), or team (`/magenta --team <task>`).
Correct: yes, partial, or no (the hidden check, and the review of the scorer).
Rule breaks: the number of constraints that the result breaks, including changed tests and changed checks.

| Date | Mode | Model | Correct | Rule breaks | Cost (USD) | Time (min) | Notes |
|---|---|---|---|---|---|---|---|
