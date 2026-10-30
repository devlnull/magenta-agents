## Rule: project first

Before any work, do these steps:

1. Read the project rules: AGENTS.md or CLAUDE.md, CONTRIBUTING, the lint and format configuration, CODEOWNERS, the CI configuration, and the ADRs.
2. Read `.magenta/project-context.md`. If it does not exist, stop and report it. The Principal runs the skill `discover-project`, and the human confirms the result.
3. Find two or three examples of the same kind of code in the same module. Follow their style.

The sources of truth, in order of priority:

1. Explicit project rules: AGENTS.md, ADRs, lint configuration.
2. The patterns that the code uses now: the same module first, then the repository.
3. Organization standards.
4. General best practice.

Example: if the project uses plain JdbcTemplate, do not propose JPA, even if most Spring projects use JPA.

Exception: do not copy an insecure local pattern, for example SQL that the code builds from strings. Report it and use the deviation protocol. Safety wins.

Do not bring patterns from other projects. If you think that a pattern from another project is better, use the deviation protocol.
