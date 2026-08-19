---
stack-id: javascript
stack-name: JavaScript/TypeScript
---
- TypeScript strict by default on new code; JS only where the repo already is JS.
- BDD: framework from `harness.yaml → bdd_frameworks.javascript` (cucumber-js or
  vitest-gherkin). Unit: Vitest (Jest if the repo already uses it).
- Lint/format: repo's ESLint + Prettier via `commands.lint` / `commands.format` —
  never introduce a parallel toolchain.
- Async discipline: no floating promises; AbortController on cancellable IO; timeouts
  on every external call.
- Prefer the platform (fetch, URL, crypto) over dependencies; every new dependency is
  justified in the PR description.
