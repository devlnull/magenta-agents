---
name: ci-cd-pipeline
description: Change a CI/CD pipeline (GitHub Actions, GitLab CI, Jenkins, and others) to be fast, repeatable, and safe, with deployment strategies that can roll back. Use it for each change of a pipeline.
---

# CI/CD pipeline

## Rules

1. **Keep the gates.** Do not remove or weaken tests, checks, scans, or approvals. A faster pipeline that checks less is not better.
2. **Pin versions.** Pin actions and images to a version, and to a commit SHA or a digest for third-party actions. Do not use `latest` or `main`.
3. **Least privilege.** Give the pipeline token only the permissions that the job needs (for example `permissions: contents: read` in GitHub Actions). Use OIDC to the cloud, not long-lived keys.
4. **Secrets.** Read secrets only from the secret store of the CI system. Do not print them. Do not pass them as build arguments to images.
5. **Untrusted input.** Do not put pull request titles, branch names, or other user text directly into shell commands (`${{ github.event.pull_request.title }}`). Pass them through environment variables.
6. **Repeatable builds.** Use lock files and a fixed toolchain version. The same commit gives the same result.
7. **Speed.** Cache dependencies by the hash of the lock file. Run independent jobs in parallel. Fail fast on lint and unit tests before slow jobs.

## Deployment strategies

| Strategy | Use it when | Rollback |
|---|---|---|
| Rolling | Stateless service, compatible versions | Roll back the version |
| Blue-green | Fast switch and fast rollback are necessary | Switch the traffic back |
| Canary | Risky change, good metrics | Stop the canary when the SLO burn rate is high |
| Feature flag | The code ships before the feature is on | Turn the flag off |

Each deployment has an automatic or a written rollback. The human starts each production deployment, or approves the automatic one.

## Validate

- GitHub Actions: `actionlint`.
- Shell steps: `shellcheck`.
- GitLab CI: the CI Lint of GitLab (the human runs it), or a dry run in a branch.
