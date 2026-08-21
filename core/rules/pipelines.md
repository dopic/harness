---
rule: pipelines
applies-to: [secdevops, qa, orchestrator]
---

# Pipeline & policy rules

- **Every repo has, minimum:** lefthook (pre-commit: lint + format + secret scan;
  pre-push: `commands.test_fast`) and a CI pipeline with lint, fast tests, SAST and
  dependency scan on every PR.
- **`harness.yaml` owns the command strings.** `harness update` rewrites them in
  `lefthook.yml` and in the pipeline files; you never change a command only where it
  runs. `doctor` fails when `commands.lint` or `commands.test_fast` appears in no stage —
  a stage that wraps one declares itself with a `[harness:lint]` / `[harness:test_fast]`
  marker, the same way suites use `[suite:<name>]`.
- **Branch protection:** no direct pushes to main; PR required; client repos also
  require Douglas's approval on merge (the cheap human second eye).
- **The test-suite contract is part of the pipeline.** Every entry in
  `harness.yaml → test-suites` maps to a real stage: integration → post-merge CI,
  acceptance → test environment, smoke → deploy. A declared suite with no stage, or a
  suite on disk not declared, fails `harness doctor` and blocks item closure.
- **A red pipeline blocks dispatch.** The orchestrator does not start a new item on a
  repo whose main pipeline is red. Fixing the pipeline is the item.
- **Pipelines are code.** Azure Pipelines / Actions / GitLab CI files live in the repo,
  reviewed like any change. IaC is CDK for AWS (CDKTF/Bicep per solutions-architect
  decision on other clouds).
- **Flaky policy:** a flaky test gets fixed or deleted within the current item. Retry
  annotations are quarantine with an expiry, not a fix.
