---
name: issue
agent: issue-writer
description: Turn a demand into structured work items upstream, gated at harness:proposed.
argument-hint: "<demand description>"
---
Act as the **issue-writer** agent (see `agents/issue-writer.md`, rules included there).
Demand: $ARGUMENTS

Gather context (repo docs, `docs/architecture/`, global docs link from harness.yaml,
Notion if available), choose the item type(s), write them from the matching template in
`templates/issues/`, decide toggles, set routing flags, create everything upstream via
the provider adapter with gate `harness:proposed`, post the created IDs/links here, and
STOP. Do not start development.
