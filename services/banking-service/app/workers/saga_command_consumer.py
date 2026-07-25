"""Consumer for saga commands directed at banking-service.

Handles:
- saga.cmd.bank_fetch_transactions: fetch from Enable Banking API
- saga.cmd.mark_sync_complete: update last_synced_at + emit BankSyncCompletedEvent
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage
from contracts.events.bank import BankSyncCompletedEvent, SyncTrigger
from messaging import OutboxRepository
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.enable_banking_client import EnableBankingClient, EnableBankingConfig
from app.config import settings
from app.database import async_session_factory
from app.models import BankConnectionModel
from app.models.outbox import OutboxEventModel
from app.models.processed_events import ProcessedEventModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "banking_service.saga_commands"
ROUTING_KEYS = ["saga.cmd.bank_fetch_transactions", "saga.cmd.mark_sync_complete"]
MAX_RETRIES = 3


def _parse_sync_trigger(raw: str | None) -> SyncTrigger:
    """Claim-kolonnen → enum, med MANUAL som fallback.

    To forskellige tilfælde, med vilje skilt ad:

    - ``NULL`` er forventet på rækker claimet før migration 004 og kræver ingen
      støj.
    - En værdi vi ikke kan parse er derimod et *bug-signal* — en writer og
      denne enum er ude af sync. Fallback'en gør at hver scheduled sync
      relabelles ``manual``, så undertrykkelsen holder op med at virke, og
      uden en log-linje er det eneste spor "klokken blev støjende igen".

    Begge falder tilbage til MANUAL: den værste fejl her er at brugeren aldrig
    hører om sin egen sync.
    """
    if raw is None:
        return SyncTrigger.MANUAL
    try:
        return SyncTrigger(raw)
    except ValueError:
        logger.warning(
            "Ukendt sync_trigger %r på claim — falder tilbage til manual. "
            "En writer er ude af sync med SyncTrigger-enum'en.",
            raw,
        )
        return SyncTrigger.MANUAL


def _step_key(saga_id: str, step_name: str) -> str:
    """Inbox-nøgle for én saga-kommando: sagaens trin-identitet.

    Platformens inbox-nøgle er event'ets ``correlation_id`` (se
    ``messaging.InboxDeduplicator``), men den duer ikke for saga-kommandoer:
    orchestratoren bygger kommando-payloaden som et rent dict uden
    ``correlation_id``, og den værdi den sætter på outbox-rækken er
    ``saga.correlation_id`` — **den samme for alle trin i samme saga**. Dedup
    på den ville behandle trin 2 som en dublet af trin 1 og standse sagaen.

    ``(saga_id, step_name)`` er derimod sagaens naturlige trin-identitet, og
    den er sikker her fordi orchestratoren aldrig genudsender et
    *eksekverings*-trin: ``handle_reply`` kræver ``status == STARTED`` og
    navne-match og rykker derefter frem, og timeout går til kompensation —
    ikke til retry af trinnet. Kun ``rollback_import`` genudsendes
    (``_handle_stale_compensation``), og den er idempotent i forvejen.

    Tom nøgle ⇒ ingen dedup (se ``_inbox_key_or_none``): en delvis nøgle er
    farligere end ingen.
    """
    return f"{saga_id}:{step_name}"


def _inbox_key_or_none(body: dict) -> str | None:
    """Nøgle for denne kommando, eller ``None`` hvis den ikke kan dannes.

    Mangler ét af felterne, falder vi tilbage til adfærden fra før guarden
    (ingen dedup) i stedet for at gætte. Nøglen ``":"`` ville ellers matche
    hver anden nøgleløs kommando og gøre alle på nær den første til dubletter.
    """
    saga_id = body.get("saga_id") or ""
    step_name = body.get("step_name") or ""
    if not saga_id or not step_name:
        logger.warning(
            "Saga-kommando uden saga_id/step_name (saga_id=%r step_name=%r) — "
            "kører uden inbox-guard; en redelivery kan give dobbelt effekt.",
            saga_id,
            step_name,
        )
        return None
    return _step_key(saga_id, step_name)


class BankingSagaCommandConsumer:
    def __init__(self) -> None:
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._banking_client: EnableBankingClient | None = None

    def _get_banking_client(self) -> EnableBankingClient:
        if self._banking_client is None:
            config = EnableBankingConfig(
                app_id=settings.ENABLE_BANKING_APP_ID,
                key_path=settings.ENABLE_BANKING_KEY_PATH,
                redirect_uri=settings.ENABLE_BANKING_REDIRECT_URI,
                max_tx_pages=settings.MAX_TX_PAGES,
            )
            self._banking_client = EnableBankingClient(config)
        return self._banking_client

    async def aclose(self) -> None:
        if self._banking_client is not None:
            await self._banking_client.aclose()
            self._banking_client = None
        if self._connection is not None:
            await self._connection.close()

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)

        exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)

        dlx = await self._channel.declare_exchange(f"{EXCHANGE_NAME}.dlx", ExchangeType.DIRECT, durable=True)
        dlq = await self._channel.declare_queue(f"{QUEUE_NAME}.dlq", durable=True)
        await dlq.bind(dlx, routing_key=QUEUE_NAME)

        queue = await self._channel.declare_queue(
            QUEUE_NAME,
            durable=True,
            arguments={
                "x-dead-letter-exchange": f"{EXCHANGE_NAME}.dlx",
                "x-dead-letter-routing-key": QUEUE_NAME,
            },
        )
        for key in ROUTING_KEYS:
            await queue.bind(exchange, routing_key=key)
        await queue.consume(self._on_message)

        logger.info("Banking saga command consumer started, listening on %s", ROUTING_KEYS)
        await asyncio.Future()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        # Parse inside error handling: a malformed body is dead-lettered
        # instead of crashing the consumer callback.
        try:
            body = json.loads(message.body.decode("utf-8"))
        except Exception:
            logger.error("Invalid JSON on %s — sending to DLQ", QUEUE_NAME, exc_info=True)
            await message.nack(requeue=False)
            return
        event_type = body.get("event_type", "")
        saga_id = body.get("saga_id", "")
        step_name = body.get("step_name", "")

        try:
            if event_type == "saga.cmd.bank_fetch_transactions":
                reply = await self._handle_fetch_transactions(body)
            elif event_type == "saga.cmd.mark_sync_complete":
                reply = await self._handle_mark_sync_complete(body)
            else:
                logger.warning("Unknown saga command: %s", event_type)
                await message.nack(requeue=False)
                return

            await self._publish_reply(saga_id, step_name, reply)
            await message.ack()

        except Exception as exc:
            retry_count = (message.headers or {}).get("x-retry-count", 0)
            if isinstance(retry_count, bytes):
                retry_count = int(retry_count)
            if retry_count >= MAX_RETRIES:
                logger.error("Max retries for %s saga=%s — sending failure reply", event_type, saga_id, exc_info=True)
                await self._publish_reply(
                    saga_id,
                    step_name,
                    {
                        "success": False,
                        "error_message": str(exc),
                    },
                )
                await message.ack()
            else:
                logger.warning("Retrying %s saga=%s (attempt %d)", event_type, saga_id, retry_count + 1, exc_info=True)
                await self._republish(message, retry_count + 1)
                await message.ack()

    async def _handle_fetch_transactions(self, body: dict) -> dict:
        """Hent transaktioner fra EB. **Bevidst uden inbox-guard** (P2-22).

        Dette trins reply *bærer* resultatet (``result_data.items`` = hele
        fetchen). En dedup-sti kan derfor ikke bare svare "success" uden at
        genskabe items: sagaen ville importere 0 og syncen tabe transaktioner
        i stilhed. Det er en værre fejl end det gentagne EB-kald en redelivery
        koster — og handleren skriver ingenting, så en redelivery er netop
        kun spild, ikke skade.

        Vil man dedupe her, kræver det *stored reply* (gem svaret, gensend
        det) — samme mekanisme som transaction-service's bulk-import mangler
        (P2-23), ikke den guard ``_handle_mark_sync_complete`` bruger.
        """
        connection_id = body["connection_id"]
        bank_account_uid = body.get("bank_account_uid", "")
        date_from = body.get("date_from")

        # Expiry gate mirrors start_sync_saga (audit H9): the API layer
        # already rejects expired consents, but commands can arrive from
        # other producers / after a delay — fail fast with a clear
        # message instead of an opaque EB error deep in the fetch.
        expired_reply = await self._reject_if_consent_expired(connection_id)
        if expired_reply is not None:
            return expired_reply

        client = self._get_banking_client()
        transactions, parse_skipped = await client.get_transactions(
            account_uid=bank_account_uid,
            date_from=date_from,
        )

        items = []
        errors = 0
        for txn in transactions:
            try:
                tx_type = "income" if txn.amount >= 0 else "expense"
                # entry_reference-based identity + currency (P2-09/H10).
                # Blank ids are normalized to None so transaction-service
                # never dedupes on "" — it falls back to the fuzzy key.
                items.append(
                    {
                        "amount": str(abs(txn.amount)),
                        "transaction_type": tx_type,
                        "date": txn.date.isoformat(),
                        "description": txn.description,
                        "external_id": (txn.transaction_id or "").strip() or None,
                        "currency": txn.currency or "DKK",
                    }
                )
            except Exception:
                errors += 1
                logger.warning("Failed to prepare transaction for saga", exc_info=True)

        return {
            "success": True,
            "result_data": {
                "items": items,
                "total_fetched": len(transactions),
                "parse_skipped": parse_skipped,
                "errors": errors,
            },
        }

    async def _reject_if_consent_expired(self, connection_id: str) -> dict | None:
        """Return a failure reply if the connection's consent has lapsed."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(BankConnectionModel).where(BankConnectionModel.id == UUID(connection_id))
            )
            conn = result.scalar_one_or_none()
        if conn is None or conn.expires_at is None:
            return None
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if conn.expires_at > now_naive:
            return None
        logger.warning(
            "Rejecting bank_fetch_transactions: consent for connection %s expired at %s",
            connection_id,
            conn.expires_at.isoformat(),
        )
        return {
            "success": False,
            "error_message": (f"Bank consent expired at {conn.expires_at.isoformat()} — reconsent required"),
        }

    async def _handle_mark_sync_complete(self, body: dict) -> dict:
        connection_id = body["connection_id"]
        user_id = body["user_id"]
        saga_id = body.get("saga_id", "")
        inbox_key = _inbox_key_or_none(body)

        async with async_session_factory() as session:
            # P2-22: kommandoen må kun have effekt én gang. Uden denne guard
            # læser en redelivery (reply-publish fejlede efter commit, eller
            # ACK'en blev tabt) et nu-NULL sync_trigger → MANUAL → et ANDET
            # BankSyncCompletedEvent med frisk correlation_id → en ny
            # source_key i notification-service, som unique-constraint'en
            # derfor ikke kan absorbere. Én spøgelses-"ingen nye
            # transaktioner" per redelivery.
            if inbox_key is not None and await self._is_duplicate(session, inbox_key):
                # Svar ALLIGEVEL. Årsagen til redeliveryen er typisk netop et
                # tabt reply; ack'er vi uden at svare, hænger sagaen til
                # timeout og går i kompensation — vi ville bytte en
                # spøgelsesnotifikation for en fejlet saga.
                logger.info(
                    "Dublet saga-kommando (%s) — springer effekten over, svarer success",
                    inbox_key,
                )
                return {"success": True}

            result = await session.execute(
                select(BankConnectionModel).where(BankConnectionModel.id == UUID(connection_id))
            )
            conn = result.scalar_one_or_none()
            if conn is not None:
                # Naive UTC per column convention; not domain logic, so a
                # direct timestamp (not injected clock) is acceptable here.
                conn.last_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
                # Læs trigger'en FØR claimet ryddes nedenfor — claimet er dens
                # eneste bærer — og KUN hvis claimet stadig er vores.
                #
                # Claim-rækken er ikke versioneret per saga: try_claim_sync
                # vinder alene på TTL-cutoff, så en nyere saga kan have
                # overskrevet sync_trigger mens vi kørte. Læste vi den blindt,
                # ville en langsom MANUEL sync kunne stemples "scheduled" og
                # derefter undertrykkes i notification-service — brugeren
                # trykkede på knappen og fik stilhed. Fremmed claim ⇒ MANUAL,
                # så vi fejler i retning af at notificere.
                own_claim = bool(saga_id) and conn.sync_saga_id == saga_id
                trigger = _parse_sync_trigger(conn.sync_trigger) if own_claim else SyncTrigger.MANUAL
                if not own_claim:
                    logger.info(
                        "mark_sync_complete: claimet tilhører ikke saga %s (nu: %s) — "
                        "stempler completion som manual (connection=%s)",
                        saga_id,
                        conn.sync_saga_id,
                        connection_id,
                    )
                # P3-14: frigiv sync-claimet — kun hvis det stadig er VORES
                # (en nyere sagas claim må ikke ryddes af en gammel reply).
                if own_claim:
                    conn.sync_saga_id = None
                    conn.sync_started_at = None
                    conn.sync_trigger = None

                outbox_repo = OutboxRepository(session, OutboxEventModel)
                event = BankSyncCompletedEvent(
                    connection_id=connection_id,
                    account_id=conn.account_id,
                    user_id=user_id,
                    total_fetched=body.get("total_fetched", 0),
                    new_imported=body.get("new_imported", 0),
                    duplicates_skipped=body.get("duplicates_skipped", 0),
                    errors=body.get("errors", 0),
                    parse_skipped=body.get("parse_skipped", 0),
                    trigger=trigger,
                )
                await outbox_repo.add(
                    event=event,
                    aggregate_type="bank_connection",
                    aggregate_id=connection_id,
                )

                # Inbox-rækken hører i SAMME transaktion som effekterne.
                # Committede vi den for sig, ville idempotensen koste
                # retry-evnen: en handler der rejser efter inbox-commit men
                # før effekt-commit ville aldrig køre igen. Sammen betyder
                # "effekterne skete" og "kommandoen er set" ét faktum.
                #
                # Ligger uden for conn is None-grenen med vilje: findes
                # forbindelsen ikke, er der ingen effekt at deduplikere, og
                # adfærden er uændret fra før guarden (ingen commit, success).
                if inbox_key is not None:
                    session.add(
                        ProcessedEventModel(
                            correlation_id=inbox_key,
                            consumer_name=QUEUE_NAME,
                        )
                    )

                try:
                    await session.commit()
                except IntegrityError:
                    # To deliveries kørte samtidigt: exists-checket var rent i
                    # begge, unique-constraint'en afgjorde kapløbet. Taberen
                    # har rullet sine effekter tilbage og svarer som dublet.
                    await session.rollback()
                    logger.info("Dublet på commit (%s) — benign kapløb", inbox_key)
                    return {"success": True}

        return {"success": True}

    @staticmethod
    async def _is_duplicate(session: AsyncSession, inbox_key: str) -> bool:
        result = await session.execute(
            select(ProcessedEventModel).where(
                ProcessedEventModel.correlation_id == inbox_key,
                ProcessedEventModel.consumer_name == QUEUE_NAME,
            )
        )
        return result.scalar_one_or_none() is not None

    async def _publish_reply(self, saga_id: str, step_name: str, reply_data: dict) -> None:
        if self._channel is None:
            return
        exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)

        reply_payload = {
            "event_type": f"saga.reply.{step_name}",
            "saga_id": saga_id,
            "step_name": step_name,
            "success": reply_data.get("success", False),
            "error_message": reply_data.get("error_message"),
            "result_data": reply_data.get("result_data"),
            "is_compensation": False,
        }
        msg = aio_pika.Message(
            body=json.dumps(reply_payload, default=str).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await exchange.publish(msg, routing_key=f"saga.reply.{step_name}")

    async def _republish(self, original: AbstractIncomingMessage, retry_count: int) -> None:
        if self._channel is None:
            return
        exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)
        headers = dict(original.headers or {})
        headers["x-retry-count"] = retry_count
        msg = aio_pika.Message(
            body=original.body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=headers,
        )
        await exchange.publish(msg, routing_key=original.routing_key or "")


async def main() -> None:
    consumer = BankingSagaCommandConsumer()
    try:
        await consumer.start()
    finally:
        await consumer.aclose()


if __name__ == "__main__":
    asyncio.run(main())
