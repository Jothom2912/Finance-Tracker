"""Transaktions-projektion med konvergente scripted upserts.

Idempotens-modellen (ADR-004): dokument-``_id`` = transaction_id, og to
uafhængige timestamp-guards deler dokumentet i feltgrupper:

- ``core_event_ts`` vogter kernefelter (beløb, dato, beskrivelse …)
  skrevet af ``transaction.created/updated``.
- ``categorization_event_ts`` vogter kategoriseringsfelter, som ejes af
  ``transaction.categorized`` — et ældre core-event kan aldrig rulle en
  nyere kategorisering tilbage, og omvendt.

``is_deleted`` er terminal: sene replays genopliver aldrig et slettet
dokument. Et ``categorized``-event der ankommer FØR ``created`` skaber
et partielt dokument uden account_id/user_id/tx_date — usynligt for
alle queries (som filtrerer på netop de felter) indtil core-eventet
kompletterer det.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import NotFoundError

from app.adapters.outbound.elasticsearch.mappings import TRANSACTIONS_INDEX, alias_name
from app.application.ports.outbound import IEmbeddingStore, ITransactionProjectionStore

_CORE_SCRIPT = """
if (ctx._source.is_deleted == true) { ctx.op = 'noop'; }
else {
  def core = ctx._source.core_event_ts;
  if (core == null || params.event_ts >= core) {
    ctx._source.account_id = params.account_id;
    ctx._source.user_id = params.user_id;
    ctx._source.amount = params.amount;
    ctx._source.amount_abs = params.amount_abs;
    ctx._source.transaction_type = params.transaction_type;
    ctx._source.tx_date = params.tx_date;
    ctx._source.description = params.description;
    ctx._source.core_event_ts = params.event_ts;
    ctx._source.updated_at = params.event_ts;
    def cat = ctx._source.categorization_event_ts;
    if (cat == null || params.event_ts >= cat) {
      ctx._source.category_id = params.category_id;
      ctx._source.category_name = params.category_name;
      ctx._source.subcategory_id = params.subcategory_id;
      ctx._source.subcategory_name = params.subcategory_name;
      ctx._source.categorization_tier = params.categorization_tier;
      ctx._source.categorization_confidence = params.categorization_confidence;
    }
  } else { ctx.op = 'noop'; }
}
"""

_CATEGORIZATION_SCRIPT = """
if (ctx._source.is_deleted == true) { ctx.op = 'noop'; }
else {
  def cat = ctx._source.categorization_event_ts;
  if (cat == null || params.event_ts >= cat) {
    ctx._source.category_id = params.category_id;
    ctx._source.category_name = params.category_name;
    ctx._source.subcategory_id = params.subcategory_id;
    ctx._source.subcategory_name = params.subcategory_name;
    ctx._source.categorization_tier = params.categorization_tier;
    ctx._source.categorization_confidence = params.categorization_confidence;
    ctx._source.categorization_event_ts = params.event_ts;
    ctx._source.updated_at = params.event_ts;
  } else { ctx.op = 'noop'; }
}
"""

_DELETE_SCRIPT = """
ctx._source.is_deleted = true;
ctx._source.updated_at = params.event_ts;
"""

# Vektoren er afledt state (af beskrivelse/kategori) — dens guard-ts er
# dokumentets updated_at på embed-tidspunktet, så en re-embed af nyere
# dokument-state altid vinder, og replays/backfill er benigne no-ops.
# Ingen upsert: findes dokumentet ikke (endnu), er der intet at embedde.
_EMBEDDING_SCRIPT = """
if (ctx._source.is_deleted == true) { ctx.op = 'noop'; }
else {
  def emb = ctx._source.embedding_event_ts;
  if (emb == null || params.event_ts >= emb) {
    ctx._source.description_vector = params.vector;
    ctx._source.embedding_event_ts = params.event_ts;
  } else { ctx.op = 'noop'; }
}
"""


class EsTransactionProjectionStore(ITransactionProjectionStore, IEmbeddingStore):
    def __init__(self, es: AsyncElasticsearch, index_prefix: str = "") -> None:
        self._es = es
        self._alias = alias_name(index_prefix, TRANSACTIONS_INDEX)

    async def upsert_core(
        self,
        *,
        transaction_id: int,
        account_id: int,
        user_id: int,
        amount: float,
        transaction_type: str,
        tx_date: date,
        description: str,
        category_id: Optional[int],
        category_name: Optional[str],
        subcategory_id: Optional[int],
        subcategory_name: Optional[str],
        categorization_tier: Optional[str],
        categorization_confidence: Optional[str],
        event_ts: int,
    ) -> None:
        params: dict[str, Any] = {
            "account_id": account_id,
            "user_id": user_id,
            "amount": amount,
            "amount_abs": abs(amount),
            "transaction_type": transaction_type,
            "tx_date": tx_date.isoformat(),
            "description": description,
            "category_id": category_id,
            "category_name": category_name,
            "subcategory_id": subcategory_id,
            "subcategory_name": subcategory_name,
            "categorization_tier": categorization_tier,
            "categorization_confidence": categorization_confidence,
            "event_ts": event_ts,
        }
        await self._es.update(
            index=self._alias,
            id=str(transaction_id),
            script={"source": _CORE_SCRIPT, "lang": "painless", "params": params},
            upsert={"transaction_id": transaction_id, "is_deleted": False},
            scripted_upsert=True,
            retry_on_conflict=3,
        )

    async def apply_categorization(
        self,
        *,
        transaction_id: int,
        category_id: int,
        category_name: str,
        subcategory_id: Optional[int],
        subcategory_name: str,
        categorization_tier: str,
        categorization_confidence: str,
        event_ts: int,
    ) -> None:
        params: dict[str, Any] = {
            "category_id": category_id,
            "category_name": category_name or None,
            "subcategory_id": subcategory_id,
            "subcategory_name": subcategory_name or None,
            "categorization_tier": categorization_tier or None,
            "categorization_confidence": categorization_confidence or None,
            "event_ts": event_ts,
        }
        await self._es.update(
            index=self._alias,
            id=str(transaction_id),
            script={"source": _CATEGORIZATION_SCRIPT, "lang": "painless", "params": params},
            upsert={"transaction_id": transaction_id, "is_deleted": False},
            scripted_upsert=True,
            retry_on_conflict=3,
        )

    async def get_projection(self, *, transaction_id: int) -> Optional[dict[str, Any]]:
        """Rå dokument-state (uden vektor) til embed-workerens prosa-bygning."""
        try:
            doc = await self._es.get(
                index=self._alias,
                id=str(transaction_id),
                source_excludes=["description_vector"],
            )
        except NotFoundError:
            return None
        return dict(doc["_source"])

    async def update_embedding(
        self,
        *,
        transaction_id: int,
        vector: list[float],
        event_ts: int,
    ) -> None:
        try:
            await self._es.update(
                index=self._alias,
                id=str(transaction_id),
                script={
                    "source": _EMBEDDING_SCRIPT,
                    "lang": "painless",
                    "params": {"vector": vector, "event_ts": event_ts},
                },
                retry_on_conflict=3,
            )
        except NotFoundError:
            # Slettet mellem get og update — vektor på en tombstone er
            # ligegyldig (alle queries filtrerer is_deleted).
            return

    async def mark_deleted(self, *, transaction_id: int, event_ts: int) -> None:
        await self._es.update(
            index=self._alias,
            id=str(transaction_id),
            script={
                "source": _DELETE_SCRIPT,
                "lang": "painless",
                "params": {"event_ts": event_ts},
            },
            upsert={
                "transaction_id": transaction_id,
                "is_deleted": True,
                "updated_at": event_ts,
            },
            scripted_upsert=True,
            retry_on_conflict=3,
        )
