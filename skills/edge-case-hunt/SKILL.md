---
name: edge-case-hunt
description: Find edge cases systematically with test design techniques and domain checklists. Use it for each story before the test plan is final.
---

# Edge-case hunt

## Techniques

1. Boundary values: minimum, maximum, just inside, just outside, zero, empty, null.
2. Equivalence classes: one representative for each valid and invalid class.
3. Decision tables: combinations of conditions and their results.
4. State transitions: each valid transition, and each invalid transition from each state.
5. Pairwise combinations for many parameters.

## Distributed-system checklist

- Concurrency: two requests change the same entity at the same time.
- Idempotency: the same request or event arrives two times.
- Retries and timeouts: the remote call is slow, fails, or succeeds after the timeout.
- Partial failure: step 1 succeeds and step 2 fails.
- Events out of order, late, or duplicate.
- Backward compatibility of APIs and event schemas.

## Business checklist

- Money: rounding, currency, negative amounts, refunds larger than the payment.
- Time: time zones, calendars (for example Jalali and Gregorian), daylight saving, end of month, end of year.
- Limits and quotas: exactly at the limit, one over the limit.
- Permissions: each role, and a user without access.
- Localization: RTL text, Persian and Arabic digits, long text.
- Data: missing optional fields, very large inputs, special characters.

## Output

A table: ID, edge case, technique or checklist item, risk (HIGH, MEDIUM, LOW), and the test or the accepted gap.
