---
rule: qa
applies-to: [qa, test-engineer, secdevops, orchestrator]
---

# QA rules

- **Boundary with test-engineer:** the test-engineer proves the business rule (BDD specs
  at code level, cheap, run on every PR). QA proves the assembled system: integration
  tests (real boundaries — DB, queue, external API; testcontainers where it fits),
  end-to-end acceptance with Cypress, and a minimal smoke suite (Cypress, `@smoke` tag).
  QA does not re-test what the specs already prove.
- **QA builds; the pipeline validates.** QA's deliverable is the suite PLUS its entry in
  `harness.yaml → test-suites` (path, command, stage). SecDevOps materializes the stage.
  A suite the pipeline doesn't run does not exist — the orchestrator won't close the
  item until the suite↔stage check is green.
- **Smoke is small and fast by definition.** Minutes, not tens of minutes; the critical
  paths only. If smoke grows, something is mislabeled acceptance.
- **Acceptance maps to Gherkin too.** E2E scenarios reference the story scenarios they
  cover; uncovered critical scenarios get flagged on the item.
- **Flaky:** fix it or delete it, inside the current item. Never `skip` and move on.
- **Test data is owned.** Each suite creates and destroys its own data; suites that
  depend on leftover state fail review.
