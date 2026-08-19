---
rule: review
applies-to: [code-reviewer, security-reviewer, orchestrator]
---

# Review rules

- **Reviewers comment, never edit.** All feedback goes through the provider's review
  mechanism (PR review with request-changes/approve). The engineer owns the fix.
- **A blocking comment carries a reason and a suggestion.** "This breaks X because Y;
  consider Z." Blocking without an alternative is taste, not review.
- **Severity is explicit.** Prefix each comment: `[blocker]`, `[should]`, `[nit]`.
  Only blockers hold the merge. Three nits don't add up to a blocker.
- **Review the diff against the item.** Covered scenarios, honored ADRs, declared
  toggles. Code that is fine in isolation but doesn't deliver the item fails review.
- **Two rounds without convergence → escalate.** Comment mentioning Douglas with a
  one-paragraph summary of the disagreement and both positions. Stop looping.
- **Approve means approve.** No "approve with comments" on blockers. If it blocks,
  request changes.
