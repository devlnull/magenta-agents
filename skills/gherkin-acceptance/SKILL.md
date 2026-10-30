---
name: gherkin-acceptance
description: Write acceptance criteria as Gherkin scenarios and black-box acceptance tests against public contracts. Use it in the Three Amigos step and before implementation.
---

# Gherkin acceptance criteria

## Rules

- Each scenario tests one behavior.
- Write the business language of the domain. Do not use class names or internal names.
- Use Given (state), When (one action), Then (observable result).
- Use `Scenario Outline` with `Examples` for boundary values and equivalence classes.
- Each story has at least one happy path, one negative path, and the important edge cases.
- Give each scenario an ID: `AC-<story>-<n>`. The test plan maps each ID to a test.

## Example

```gherkin
Feature: Cancel an order

  Scenario: AC-12-1 Customer cancels an order before shipment
    Given an order "O-1" with the status "PAID"
    When the customer cancels the order "O-1"
    Then the order "O-1" has the status "CANCELLED"
    And a full refund for the order "O-1" is requested

  Scenario Outline: AC-12-2 Cancel is not possible after shipment
    Given an order "O-2" with the status "<status>"
    When the customer cancels the order "O-2"
    Then the request fails with the reason "ORDER_ALREADY_SHIPPED"

    Examples:
      | status    |
      | SHIPPED   |
      | DELIVERED |
```

## Black-box acceptance tests

- Test through the public contract only: HTTP API, events, or UI.
- The tests must compile and fail before the implementation exists.
- Use the test framework and the folder from the project context.
