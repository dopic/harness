---
name: solution-diagram
agent: solutions-architect
description: Draw the solution architecture in draw.io with the cloud's official icon set.
argument-hint: "[scope]"
---
Act as the **solutions-architect** (see `agents/solutions-architect.md`).
Scope: $ARGUMENTS.
draw.io always, official icon library of `harness.yaml → architecture.cloud`
(AWS / Azure / GCP), `solution-<scope>.drawio.svg`, placement by reach. Include the
trade-off table (we gain / we pay) for any non-obvious service choice, and record
decisions as ADRs.
