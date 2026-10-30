---
name: stack-dotnet
description: Default guidance for C# and .NET code. Use it when the project uses .NET. The project context always wins over this skill.
---

# Stack: C# and .NET

The project context wins. Use these defaults only where the project has no convention.

## Code

- Use the built-in dependency injection. Register services with the correct lifetime.
- Use `async` and `await` from end to end. Pass a `CancellationToken`. Do not block with `.Result` or `.Wait()`.
- Use records for immutable data. Enable nullable reference types if the project does.
- Use the data access library of the project (EF Core or Dapper). Do not mix them in one module.
- Use the options pattern for configuration.
- Use the logging of the project (`ILogger<T>`, structured messages). Do not log personal data or secrets.
- Use the error model of the project (for example ProblemDetails).

## Tests

- Use the test framework of the project (xUnit, NUnit, or MSTest) and its assertion library.
- Integration tests: `WebApplicationFactory` and Testcontainers, if the project uses them.
- Architecture tests: NetArchTest or ArchUnitNET, if the project has them.
- Run: `dotnet test`.
