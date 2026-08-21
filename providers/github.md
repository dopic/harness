# GitHub adapter

CLI: `gh`. All commands assume `-R "{provider.organization}/{provider.repository}"`
(or `gh repo set-default` once per clone). The recipes below use `REPO` as shorthand:

```bash
REPO="{provider.organization}/{provider.repository}"
```

`harness.yaml` mapping: `organization` = owner (org **or** user login);
`repository` = repo name; `project` = optional Projects v2 board **title** (empty
means the harness does not touch Projects — gate state lives in labels either way).

## Bootstrap (once per repo)

GitHub refuses `--label` for labels that do not exist yet, so nothing works before
this runs:

```bash
harness provider-setup            # idempotent: gh label create --force for every
                                  # harness:* gate + type:* item-type label
```

## Auth check (doctor)

```bash
gh auth status                                    # token + scopes
gh label list -R "$REPO" --limit 1                # proves repo + issues access
```

Required scopes: `repo` (issues, PRs, code) and `workflow` (secdevops pushes files
under `.github/workflows/`; a token without it gets the push rejected). Add `project`
only if `provider.project` is set. Refresh with `gh auth refresh -s workflow`.

## Verb recipes

### create_item
```bash
gh issue create -R "$REPO" \
  --title "<title>" \
  --label "type:user-story" --label "harness:proposed" \
  --body-file - <<'MD'
<markdown body — GitHub renders Markdown natively, no HTML needed>
MD
# types: type:user-story | type:bug | type:tech-debt | type:spike
# there is no Epic/Feature type — an Epic is an issue whose children are sub-issues.
# the command prints the issue URL; capture the number:
NUM=$(gh issue create -R "$REPO" … | grep -oE '[0-9]+$')

# if harness.yaml sets provider.project (a Projects v2 board title), add the item to it
# — requires the `project` token scope. The board is for the human's visibility only;
# gate state stays in the labels.
[ -n "{provider.project}" ] && gh issue edit "$NUM" -R "$REPO" --add-project "{provider.project}"
```

### update_item
```bash
# --body REPLACES the whole body: read, edit, write back.
gh issue view <N> -R "$REPO" --json body --jq .body > /tmp/body.md
# …edit /tmp/body.md (task checklist lives here as `- [ ] task`)…
gh issue edit <N> -R "$REPO" --body-file /tmp/body.md
gh issue edit <N> -R "$REPO" --title "<new title>"
gh issue edit <N> -R "$REPO" --add-label "arch-review" --add-label "security-review"
```

### comment
```bash
gh issue comment <N> -R "$REPO" --body-file - <<'MD'
<comment body>
MD
# PRs share the numbering space and accept `gh pr comment <PR> -R "$REPO"`.
```

### set_gate_state
Labels are individually addressable — no read-modify-write race (unlike ADO's atomic
tags field). Still strip *every* existing gate label so the "exactly one" invariant
holds even after a manual edit in the UI:

```bash
for L in $(gh issue view <N> -R "$REPO" --json labels \
             --jq '.labels[].name | select(startswith("harness:"))'); do
  gh issue edit <N> -R "$REPO" --remove-label "$L"
done
gh issue edit <N> -R "$REPO" --add-label "harness:approved"
```

### link_items
Parent/child = **native sub-issues**, via the REST API (`gh issue edit` has no flag
for it). The endpoint takes the child's *database id*, not its issue number:

```bash
CHILD_ID=$(gh api "repos/$REPO/issues/<child-number>" --jq .id)
gh api --method POST "repos/$REPO/issues/<parent-number>/sub_issues" \
  -F sub_issue_id="$CHILD_ID"          # -F (typed) — -f would send a string and 422

gh api "repos/$REPO/issues/<parent-number>/sub_issues" --jq '.[].number'   # list
gh api --method DELETE "repos/$REPO/issues/<parent>/sub_issues" -F sub_issue_id="$CHILD_ID"
```

`relates-to` has no native equivalent: post a cross-reference comment
(`Relates to #<n>`) on both issues and say so — GitHub renders the backlink, but it
is not a queryable relation.

Removal items for feature toggles: create the removal issue first, then link it as a
sub-issue of the item that introduced the toggle.

### list_by_gate_state
```bash
gh issue list -R "$REPO" --label "harness:approved" --state open --limit 200 \
  --json number,title,labels,createdAt,updatedAt \
  --jq 'sort_by(.createdAt) | .[]'
# repeated --label is AND. Default --limit is 30 — always pass it explicitly.
```

### create_pr
```bash
gh pr create -R "$REPO" --base main --head "<branch>" \
  --title "<title>" --body-file - <<'MD'
Refs #<item-number>

<body>
MD
```
**Never** write `Closes/Fixes/Resolves #n` — those auto-close the issue on merge and
would move the gate behind the orchestrator's back. `Refs #n` links without closing.

### get_pr_diff
```bash
gh pr diff <PR> -R "$REPO"            # unified diff
gh pr diff <PR> -R "$REPO" --patch    # with commit metadata
```

### request_changes / approve
GitHub rejects a review on your own PR (422 *"Can not approve your own pull
request"*), and the harness opens the PR and reviews it with the same token. So the
verdict is a **review comment carrying an explicit marker**, not a native review
state:

```bash
gh pr review <PR> -R "$REPO" --comment --body-file - <<'MD'
[harness:changes-requested] by code-reviewer

[blocker] <reason + suggestion>
[should] …
MD

gh pr review <PR> -R "$REPO" --comment --body-file - <<'MD'
[harness:approved-by:code-reviewer] <one line saying why>
MD
```

Markers, exactly as written: `[harness:approved-by:code-reviewer]`,
`[harness:approved-by:security-reviewer]`, `[harness:changes-requested]`.

The orchestrator reads the **latest marker per reviewer** to decide the merge gate:

```bash
gh pr view <PR> -R "$REPO" --json reviews \
  --jq '[.reviews[] | select(.body | startswith("[harness:"))] | .[-1].body'
```

If the repo is configured with a separate reviewer identity (a machine account whose
token is not the one that opened the PR), `gh pr review --approve` / `--request-changes`
work natively and should be used instead — say in the PR comment which mode was used.

## Traps

- **Labels must pre-exist.** `gh issue create --label harness:proposed` on a fresh repo
  fails with `could not add label: 'harness:proposed' not found`. Run
  `harness provider-setup`; `harness doctor` checks it.
- **No self-approval.** See above. A `--approve` that returns 422 is not a transient
  error — do not retry it, switch to the marker comment.
- **`--body` overwrites.** Every `update_item` that touches the task checklist is a
  read-modify-write. Two agents editing one issue body lose writes.
- **Sub-issues take the database id.** `-F sub_issue_id=<issue number>` links the wrong
  issue or 404s. Always resolve through `gh api repos/$REPO/issues/<n> --jq .id`.
- **Issues and PRs share one number sequence.** `#123` may be a PR; `gh issue view 123`
  errors on one. Check with `gh api repos/$REPO/issues/123 --jq 'has("pull_request")'`.
- **Silent truncation.** `gh issue list` defaults to 30 results and `gh api` to one page
  — pass `--limit` / `--paginate` or the orchestrator will think the backlog is empty.
- **Native issue types.** Newer GitHub orgs have first-class issue types. The harness
  still uses `type:*` labels for portability across accounts and GHES; if the org uses
  native types too, state on the repo which one is authoritative — do not maintain both.
- **GHES / older instances.** Sub-issues may be unavailable. Fall back to a task list
  (`- [ ] #<n>`) in the parent's body and record the fallback in `harness.yaml`
  overrides — do not pretend the hierarchy is native.
- **`workflow` scope.** secdevops changes under `.github/workflows/` are rejected at
  push time without it, with a git error that does not mention scopes.
