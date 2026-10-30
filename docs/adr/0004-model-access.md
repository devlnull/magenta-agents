# ADR-0004: One model vendor first; design for more vendors and self-hosted models

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-30 |
| Decider | AMQ |
| Source | [RFC-0001, section 8](../rfc/RFC-0001-magenta-agents.md#8-model-strategy) |

## Context

AMQ wants each agent to use its own model. AMQ has access to models from Anthropic, OpenAI, Google (Gemini), and xAI (Grok). Some code can need a self-hosted model. A change of vendor must not need a change in the agent files.

## Decision

1. From day 1, agents name a model profile, never a vendor model (RFC-0001, 8.1). One file, `models.yaml`, maps the profiles to models.
2. Phases 1 and 2: all profiles map to Anthropic models in Claude Code.
3. Phase 3: add OpenAI, Gemini, and Grok models. The first use is the `reviewer-alt` profile, for QA and for the final review. Evals select the model for each role.
4. Self-hosted: the `local-private` profile points to an OpenAI-compatible endpoint (for example vLLM or Ollama). Use it when the code policy requires it, or when evals show that it is good enough for a role.
5. Headless runs send all calls through one gateway (for example LiteLLM). It gives one place for keys, budgets, logs, and fallbacks.

## Consequences

- Good: a vendor change is a one-line change. Independent review with a different model family. A path for confidential code.
- Bad: more evals, one set for each mapping. More keys and costs to manage.
- Follow-up: track the cost for each vendor and each agent. The runner logs tokens and cost for each step (phase 4).
