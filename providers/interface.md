# Provider interface

Agents speak these neutral verbs; the compiler injects the adapter selected by
`harness.yaml → provider.kind`. Adapters are recipe documents (CLI invocations +
vocabulary mapping), not code — the executing agent runs the recipe's commands.

## Verbs

| Verb | Meaning |
|---|---|
| `create_item(type, title, body, parent?, gate)` | create work item / issue with initial gate tag |
| `update_item(id, fields)` | title, body, checklist, routing flags |
| `comment(id, body)` | comment on item or PR |
| `set_gate_state(id, state)` | move between `harness:*` gate tags (remove old, add new) |
| `link_items(id, related_id, relation)` | parent/child, relates-to, removal-item |
| `list_by_gate_state(state)` | items currently in a gate state |
| `create_pr(source, target, title, body, item_id)` | PR/MR linked to the item |
| `get_pr_diff(pr_id)` | full diff for review |
| `request_changes(pr_id, body)` / `approve(pr_id, body)` | formal review verdict |

## Vocabulary map

| Neutral | Azure DevOps | GitHub | GitLab |
|---|---|---|---|
| Work item | Work Item (Epic/Feature/PBI/Bug/Task) | Issue | Issue |
| Item type | Work Item Type (native) | label `type:*` | label `type:*` |
| Gate state | Tag (State untouched) | Label | Label |
| Hierarchy | Epic → Feature → PBI → Task (native links) | sub-issues / task lists | Epic → Issue |
| Code review | Pull Request | Pull Request | Merge Request |
| Pipeline | Azure Pipelines | GitHub Actions | GitLab CI |
| Item ref in commit | `AB#123` | `#123` | `#123` |

## Rules

- Gate state is expressed as tags/labels so the provider's own State/Status field
  stays free for the client's process. Exactly one `harness:*` gate tag per item.
- Adapters must be honest about what the provider lacks (e.g., GitHub has no native
  Epic): the mapping says how the gap is bridged, never pretends it isn't there.
