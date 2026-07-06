"""Fælles guarded fuld-state upsert for accounts/goals/taxonomy.

Events for disse domæner bærer fuld state med én producent per entitet,
så én ``event_ts``-guard rækker: nyeste event vinder, replays og
out-of-order ældre events bliver no-ops. ``is_deleted`` er terminal
ligesom på transaktioner.
"""

from __future__ import annotations

from typing import Any

from elasticsearch import AsyncElasticsearch

_FULL_STATE_SCRIPT = """
if (ctx._source.is_deleted == true) { ctx.op = 'noop'; }
else {
  def ts = ctx._source.event_ts;
  if (ts == null || params.event_ts >= ts) {
    for (entry in params.fields.entrySet()) {
      ctx._source[entry.getKey()] = entry.getValue();
    }
    ctx._source.event_ts = params.event_ts;
    ctx._source.updated_at = params.event_ts;
  } else { ctx.op = 'noop'; }
}
"""


async def guarded_full_state_upsert(
    es: AsyncElasticsearch,
    *,
    alias: str,
    doc_id: str,
    fields: dict[str, Any],
    event_ts: int,
    upsert_extra: dict[str, Any] | None = None,
) -> bool:
    """Returnerer True hvis opdateringen blev anvendt (ikke noop)."""
    response = await es.update(
        index=alias,
        id=doc_id,
        script={
            "source": _FULL_STATE_SCRIPT,
            "lang": "painless",
            "params": {"fields": fields, "event_ts": event_ts},
        },
        upsert={"is_deleted": False, **(upsert_extra or {})},
        scripted_upsert=True,
        retry_on_conflict=3,
    )
    return str(response["result"]) != "noop"
