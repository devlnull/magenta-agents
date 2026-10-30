---
name: stack-java-spring
description: Default guidance for Java and Spring Boot code. Use it when the project uses Java or Kotlin with Spring. The project context always wins over this skill.
---

# Stack: Java and Spring Boot

The project context wins. Use these defaults only where the project has no convention.

## Code

- Use constructor injection. Do not use field injection.
- Keep controllers thin. Put the business rules in the domain or service layer.
- Use records or value objects for immutable data.
- Use the data access library of the project (for example plain `JdbcTemplate`, jOOQ, or JPA). Do not mix two libraries in one module.
- Put the transaction boundary in the application service. Keep transactions short.
- Validate input at the boundary (Bean Validation).
- Use the error model of the project (for example RFC 9457 problem details).
- Use the logging and metrics libraries of the project (for example SLF4J and Micrometer). Do not log personal data or secrets.

## Messaging

- Make consumers idempotent. Store a processed-message key if the project does.
- Use the outbox pattern of the project for "save and publish" when it exists.
- Keep event schemas backward compatible (for example Avro with a schema registry).

## Tests

- Unit tests: JUnit 5 and AssertJ (or the libraries of the project).
- Integration tests: Testcontainers for PostgreSQL, Kafka, and Redis, if the project uses them.
- Architecture tests: ArchUnit rules, if the project has them. Add a rule when the design asks for a fitness function.
- Build with the wrapper: `./gradlew test` or `./mvnw test`.
