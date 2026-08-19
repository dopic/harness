<!-- Source: Douglas's Notion, References · "Template · Modelo de Haiku de Arquitetura"
     (https://app.notion.com/p/3c01a13b0070816e89a2ce9217c81ea8) · snapshot 2026-08-19.
     Build artifact, not a second source of truth: divergence is resolved by re-snapshotting. -->

# Architecture Haiku — <system>

**Owner:** <one named person — "the team" is not an owner> · **Date:** YYYY-MM-DD ·
**Review by:** YYYY-MM-DD · **Status:** Draft | Approved (approval is the team's, not the author's)

The Haiku is **suggestive, not comprehensive**: it says what matters, on one page.
System description lives in C4; decision rationale lives in ADRs. Here lives what is
true today about priority, limits and tension.

## 1 · Business goals

The ruler everything else is measured against.
**Macro:** <one line>
**Specific to this system:** <one line — money, customer or risk; never technology.
If the sentence survives with another system's name in it, it says nothing.>

## 2 · Quality attributes (three, ranked)

The tiebreaker: when two decisions conflict, the higher one wins. Four attributes are
none. Each comes with a why anchored in something that happened or is on the calendar.

1. <attribute> · why: <evidence>
2. <attribute> · why: <evidence>
3. <attribute> · why: <evidence>

**Left out, and why:** <the attribute people will ask about, with the revisit trigger>

## 3 · Constraints (*who imposes it?*)

Not up for ranking: recorded and obeyed. If "who imposes" is "us", it's a choice —
send it back to the ranking. Constraint must come from outside the deciding table
(law, contract, another department's standing decision).

| What | Who imposes |
|---|---|
| | |

## 4 · Drivers (*what pushes the architecture?*)

Constraints limit today; drivers force change tomorrow. A good driver has a number or
a date ("volume doubles on Black Friday", "feature X enters Q4 roadmap and changes the
flow"). Without number, date and owner, it's decoration.

- <driver>

## 5 · Accepted trade-offs (*what did we agree to lose?*)

Live tension, documented without resolving it — the field that kills thread
re-litigation, because the price is already written. One-sided entries are
advertising, not trade-offs.

| We gain | We pay |
|---|---|
| | |

---
*Rules: one page. Owner and review date on everything. When a ranked attribute changes
position, that's a decision: ADR first, Haiku after. When a driver becomes reality, it
leaves drivers and becomes constraint, trade-off, or nothing. "Re-read on <date>, no
change" is a valid review record.*
