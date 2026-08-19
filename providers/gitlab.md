# GitLab adapter — STUB (phase 3)

Design decisions already fixed by `interface.md`; recipes to be validated end to end
in phase 3. CLI: `glab`.

- Item = Issue; type + gate via labels (`glab label create` once per project);
  hierarchy via Epics (Premium) or issue links — bridge stated per project.
- `create_item` → `glab issue create`; `comment` → `glab issue note`;
  `set_gate_state` → `glab issue update --label/--unlabel`;
  `list_by_gate_state` → `glab issue list --label harness:approved`;
  `create_pr` → `glab mr create`; `get_pr_diff` → `glab mr diff`;
  `request_changes/approve` → `glab mr note` + `glab mr approve`.
- Auth check: `glab auth status`.
