# Feature toggle record

Append to the registry file (`harness.yaml → toggles.registry`).

```markdown
## <toggle-name>

- **Type:** Release | Experiment | Ops | Permission
- **Owner:** <named person/agent lane>
- **Created:** YYYY-MM-DD · **Item:** <work item link>
- **Expiry / review:** YYYY-MM-DD
  - Release/Experiment: removal item <link>, target date mandatory
  - Experiment: deciding metric — <metric, threshold, where measured>
  - Ops/Permission: periodic review date mandatory
- **Decision point:** <the single place in code where this toggle is checked>
- **Default state:** off | on · **Removal PR:** <filled when it dies>
```

`harness doctor` flags entries past expiry/review. A toggle in code but not in the
registry is a review blocker.
