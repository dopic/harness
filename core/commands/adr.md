---
name: adr
agent: software-architect
description: Record an architecture decision as a Nygard ADR in the right place.
argument-hint: "<the decision or the tension needing one>"
---
Act as the **software-architect** (see `agents/software-architect.md`).
Subject: $ARGUMENTS

Write the ADR from `templates/architecture/adr.md`. Apply the placement rule: reach
beyond this repo → global docs; repo-scope → `docs/architecture/adrs/` with the next
ADR number. If this supersedes an existing ADR, mark the old one Superseded — never
edit its content.
