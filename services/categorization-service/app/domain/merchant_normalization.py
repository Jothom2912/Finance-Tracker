"""Merchant-pattern normalization for the feedback loop (F1-03).

Turns a raw transaction description into a stable, matchable pattern
for a learned rule.  Heuristic v1, deliberately conservative:

- lowercase + Danish ASCII transliteration (mirrors the rule engine's
  match-time normalization, so stored patterns and descriptions meet
  on the same form)
- drop tokens with no letters (card/reference numbers, dates, "12345")
  — "NETTO VESTERBRO 12345" and "NETTO VESTERBRO 99887" must converge
  on the same pattern.  Tokens that mix digits and letters survive
  ("7-eleven", "b52").  Side effect: "Rema 1000" learns as "rema",
  which contains-matches future "Rema 1000" rows anyway.
- collapse whitespace, cap at 200 chars (rules-API pattern bound)

Pure function — no I/O, no state.  Learned rules are visible and
deletable in the rules UI, so an over-broad pattern is recoverable by
the user rather than silently permanent.
"""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")
MAX_PATTERN_LENGTH = 200


def normalize_merchant_pattern(description: str) -> str:
    """Raw description → learned-rule pattern. Empty result = unlearnable."""
    text = description.lower().replace("ø", "oe").replace("æ", "ae").replace("å", "aa")
    tokens = [t for t in _WHITESPACE.split(text) if any(c.isalpha() for c in t)]
    return " ".join(tokens)[:MAX_PATTERN_LENGTH].strip()
