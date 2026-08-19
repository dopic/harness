---
stack-id: csharp
stack-name: C#/.NET
---
- Current LTS .NET unless the repo pins otherwise. Nullable reference types enabled.
- BDD: Reqnroll (SpecFlow's successor). Unit: xUnit + FluentAssertions if present.
- Analyzers on (`TreatWarningsAsErrors` where the repo allows); `dotnet format` via
  `commands.format`.
- Async all the way down — no `.Result`/`.Wait()`; `CancellationToken` flows through
  every public async API.
- DI via the built-in container; options pattern for config; no service locators.
