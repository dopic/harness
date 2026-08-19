# Azure DevOps adapter

CLI: `az` with the `azure-devops` extension. All commands assume
`--organization {provider.organization} --project "{provider.project}"` (or
`az devops configure --defaults organization=… project=…` once per session).

## Auth check (doctor)

```bash
az account show || az devops login   # PAT via AZURE_DEVOPS_EXT_PAT env var also works
az boards query --wiql "SELECT [System.Id] FROM WorkItems" --top 1   # proves Boards access
```

## Verb recipes

### create_item
```bash
az boards work-item create --type "Product Backlog Item" \
  --title "<title>" --description "<html-or-markdown body>"
# types: Epic | Feature | "Product Backlog Item" | Bug | Task  (Scrum process)
# Agile process uses "User Story" instead of PBI — detect via:
az boards work-item show --id <any-id> --query "fields.\"System.WorkItemType\""
# then add the gate tag:
az boards work-item update --id <ID> --fields "System.Tags=harness:proposed"
```

### set_gate_state
Tags are a single `;`-separated field — read, replace the `harness:*` entry, write:
```bash
CURRENT=$(az boards work-item show --id <ID> --query "fields.\"System.Tags\"" -o tsv)
# strip any existing harness:* tag, append the new one, then:
az boards work-item update --id <ID> --fields "System.Tags=<rebuilt>;harness:approved"
```

### comment
```bash
az boards work-item update --id <ID> --discussion "<comment (HTML allowed)>"
```

### link_items
```bash
az boards work-item relation add --id <child> --relation-type parent --target-id <parent>
# relates-to: --relation-type "related"
```

### list_by_gate_state
```bash
az boards query --wiql "SELECT [System.Id],[System.Title],[System.WorkItemType] \
 FROM WorkItems WHERE [System.Tags] CONTAINS 'harness:approved' \
 AND [System.TeamProject] = @project ORDER BY [System.ChangedDate] ASC"
```

### create_pr
```bash
az repos pr create --repository "{provider.repository}" \
  --source-branch <branch> --target-branch main \
  --title "<title>" --description "<body>" --work-items <ID>
```

### get_pr_diff
```bash
az repos pr show --id <PR> --query "lastMergeSourceCommit.commitId" -o tsv
git fetch origin && git diff origin/main...<commit>   # diff via git, not the REST API
```

### request_changes / approve
```bash
az repos pr set-vote --id <PR> --vote reject      # request changes (-10)
az repos pr set-vote --id <PR> --vote approve     # approve (+10)
# rationale goes as a PR thread comment (az repos pr thread create? not in CLI —
# fall back to: az devops invoke --area git --resource pullRequestThreads … or
# comment on the linked work item; state which one you used)
```

## Traps

- **Process template matters:** Scrum says PBI, Agile says User Story. Detect, don't
  assume. `harness init` records it in `harness.yaml` after the first query.
- **Tags field is atomic:** concurrent tag edits lose writes. Re-read before every
  `set_gate_state`.
- **Commit linking:** `AB#<id>` in the commit message auto-links and can transition
  items — we do NOT use auto-transition; gates move only via `set_gate_state`.
- **PAT scopes needed:** Work Items (read/write), Code (read/write), Build (read).
  Expired PAT is the most common doctor failure — check it first.
