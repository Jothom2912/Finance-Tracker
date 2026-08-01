---
name: dev-notes-decision
description: Record or supersede a non-obvious architectural or implementation choice in dev-notes/decisions, optionally promoting it to a formal ADR. Use when choosing between real alternatives, accepting a durable trade-off, deliberately rejecting an expected approach, or revisiting an existing decision. Do not use when a change merely follows an established convention.
---

# Decision workflow

1. Search decisions, ADRs and the relevant work ID. Update or supersede instead of duplicating.
2. Confirm there were real alternatives or a durable accepted cost; do not record routine
   application of an existing convention.
3. Copy `dev-notes/templates/decision.md` to a file named with today's actual date.
4. State the selected option, forces, at least one real alternative and why it lost, plus
   positive and negative consequences.
5. Put IDs in `backlog:` frontmatter; link the decision from its work item and add one short
   index hook.
6. Update the canonical architecture/pattern note if the decision changes current guidance.
7. To supersede, mark the old decision and link both directions; never rewrite history.

Promote only long-lived service-boundary, ownership or protocol choices to the next
`docs/adr/NNNN-slug.md`. Run `make notes-check` after writing.
