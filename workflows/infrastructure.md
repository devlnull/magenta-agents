## Playbook: infrastructure

Use it for CI/CD pipelines, container files, Kubernetes manifests, Helm charts, and infrastructure as code.

1. Conductor: write the brief: the goal (for example "the pipeline runs in under 10 minutes" or "the service runs as non-root"), the environments, and the constraints.
2. `sre`: write the checks: the lint and validate commands for the changed files (`actionlint`, `hadolint`, `kubeconform`, `helm lint`, `terraform validate`), and the operations rules (probes, resources, rollback). `security`: add the checks for secrets, permissions, and exposure, when they apply.
3. Checks gate.
4. `platform`: make the change with the skill of the area. Run verify until the checks pass. Write the steps that the human runs (plan, apply, rollout, rollback).
5. `sre` lens, and `security` lens when it applies.
6. Done gate. The human runs `plan` and `apply`, or merges the pipeline change. Agents never apply or deploy.
