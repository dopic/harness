---
name: triage
agent: orchestrator
description: List items awaiting approval and the approved queue.
---
Act as the **orchestrator**. Using the provider adapter, list:
1. Items in `harness:proposed` (awaiting Douglas), oldest first, with age in days.
2. Items in `harness:approved` (ready to develop), in dispatch order.
3. Items in `harness:needs-revision` (awaiting issue-writer rework).
Flag anything sitting in `proposed` for more than 5 days. Read-only: change nothing.
