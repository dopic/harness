---
name: review
agent: code-reviewer
description: Ad-hoc code + security review of an existing PR.
argument-hint: "<PR id or URL>"
---
Run both reviews on PR $ARGUMENTS, in parallel where possible:
1. As **code-reviewer** (see `agents/code-reviewer.md`).
2. As **security-reviewer** (see `agents/security-reviewer.md`).
Post verdicts upstream through the provider adapter (comments + request-changes/
approve). Comment-only: never edit code.
