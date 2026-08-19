# GitHub adapter — STUB (phase 3)

Design decisions already fixed by `interface.md`; recipes to be validated end to end
in phase 3. CLI: `gh`.

- Item = Issue; type via labels `type:user-story|bug|tech-debt|spike`; gate via labels
  `harness:*` (create once per repo: `gh label create`).
- Hierarchy: sub-issues (native) or task-list checklists; no real Epic — bridge stated
  per repo.
- `create_item` → `gh issue create`; `comment` → `gh issue comment`;
  `set_gate_state` → `gh issue edit --add-label/--remove-label`;
  `list_by_gate_state` → `gh issue list --label harness:approved`;
  `create_pr` → `gh pr create` (body `Closes #n` disabled — gates move explicitly);
  `get_pr_diff` → `gh pr diff`; `request_changes/approve` → `gh pr review`.
- Auth check: `gh auth status`.
