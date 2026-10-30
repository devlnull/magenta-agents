## Organization standards

<!-- Copy this file to standards/organization.md and replace the examples. The build puts it into the
constitution of each agent, after the rules. Project rules and project patterns still win (rule: project first). -->

- Security: follow the secure coding standard of the organization. Payment flows follow the payment security policy.
- APIs: use the API guideline of the organization (naming, versioning, error model).
- Events: register each event schema in the schema registry. Keep schemas backward compatible.
- Observability: use the logging, metrics, and tracing stack of the organization. Each service has a runbook.
- Data: classify personal data. Do not copy production data to test systems.
