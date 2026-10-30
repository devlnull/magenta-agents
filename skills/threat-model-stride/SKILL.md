---
name: threat-model-stride
description: Make a short STRIDE threat model for a flow with money, personal data, or authentication. Use it in the full lane and for security-sensitive changes.
---

# STRIDE threat model

1. Draw the data flow in Mermaid: actors, processes, data stores, and trust boundaries.
2. For each element that crosses a trust boundary, examine the six threats:
   - **S**poofing: can someone act as another user or service?
   - **T**ampering: can someone change data in transit or at rest?
   - **R**epudiation: can a user deny an action? Is there an audit log?
   - **I**nformation disclosure: can data leak (logs, errors, responses)?
   - **D**enial of service: can someone exhaust a resource?
   - **E**levation of privilege: can someone get more rights?
3. For each threat, give the risk (HIGH, MEDIUM, LOW) and the mitigation.
4. List the threats without a mitigation. Only a human can accept them.
