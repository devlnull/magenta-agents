---
name: prd-review
description: Review a PRD with a scorecard and give a verdict (GO, GO WITH CHANGES, NEEDS DISCOVERY, NO GO). Use it for each new PRD or feature request.
---

# PRD review

## Scorecard

Give each dimension a score: 0 (missing), 1 (weak), or 2 (good). Give the evidence for each score. The maximum total is 18.

| Dimension | Question |
|---|---|
| Problem | Is the problem clear? Does evidence support it? |
| Users | Are the target users and their job to be done clear? |
| Value | Is the impact measurable: metric, baseline, and target? |
| Alternatives | Did the PRD examine cheaper options? |
| Smallest slice | Is there a small first slice that tests the main assumption? |
| Feasibility | Are the dependencies, the data, and the constraints known? |
| Risks | Does the PRD list the value, usability, feasibility, and viability risks? |
| Testability | Are the acceptance criteria testable? |
| Urgency | Is the cost of delay clear? |

## Verdict rules

Apply the first rule that matches:

1. **NO GO.** Evidence shows that the problem is not real, that the value is lower than the cost, or that the PRD conflicts with the strategy.
2. **NEEDS DISCOVERY.** The evidence for Problem or Value is missing (score 0).
3. **GO WITH CHANGES.** The total is less than 15, or another dimension has the score 0.
4. **GO.** All other cases.

## Optional prioritization

RICE = Reach × Impact × Confidence ÷ Effort. Use it only when the PRD gives the numbers, or mark each number as `ASSUMPTION:`.

## Output

Use the PRD review template from the skill `magenta-templates`.
