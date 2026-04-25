import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from server.db.alerts import Alert
from server.db.messages import Bucket, InboundMessage, TriagedMessage
from server.eventbus.postgres import PostgresEventBus
from server.llm.triage_client import classify, hash_to_vec

logger = logging.getLogger(__name__)

WORKER_ID = "triage-worker-1"
WINDOW_LENGTH_MS = 3000


def _window_floor(ts: datetime, window_ms: int = WINDOW_LENGTH_MS) -> datetime:
    epoch_ms = int(ts.timestamp() * 1000)
    floored = (epoch_ms // window_ms) * window_ms
    return datetime.fromtimestamp(floored / 1000, tz=UTC)


async def _process_message(msg_id: str, session_maker: async_sessionmaker) -> None:
    async with session_maker() as session:
        msg = await session.get(InboundMessage, msg_id)
        if msg is None:
            logger.warning("triage: msg %s not found", msg_id)
            return
        if msg.status != "new":
            return
        msg.status = "triaging"
        msg.claimed_at = datetime.now(UTC)
        msg.claimed_by = WORKER_ID
        await session.commit()

    async with session_maker() as session:
        msg = await session.get(InboundMessage, msg_id)

        alert_summary = None
        alert_id = msg.in_reply_to_alert_id
        if alert_id:
            alert = await session.get(Alert, alert_id)
            if alert:
                desc = alert.description or ""
                alert_summary = (alert.person_name + ". " + desc)[:200]

        body_embedding = hash_to_vec(msg.body)
        result = await classify(msg.body, alert_summary)

        classification = result["classification"]
        geohash6 = result.get("geohash6")
        geohash_source = result.get("geohash_source", "alert_region")
        confidence = float(result.get("confidence", 0.5))
        language = result.get("language", "en")

        geohash_prefix_4 = (geohash6 or "")[:4] or "unkn"
        now = datetime.now(UTC)
        window_start = _window_floor(now, WINDOW_LENGTH_MS)
        bucket_key = f"{alert_id or 'unresolved'}|{geohash_prefix_4}|{window_start.isoformat()}"

        triaged = TriagedMessage(
            msg_id=msg_id,
            ngo_id=msg.ngo_id,
            classification=classification,
            geohash6=geohash6,
            geohash_source=geohash_source,
            confidence=confidence,
            language=language,
            bucket_key=bucket_key,
            body_embedding=body_embedding,
        )
        session.add(triaged)

        if alert_id:
            stmt = (
                pg_insert(Bucket)
                .values(
                    bucket_key=bucket_key,
                    ngo_id=msg.ngo_id,
                    alert_id=alert_id,
                    geohash_prefix_4=geohash_prefix_4,
                    window_start=window_start,
                    window_length_ms=WINDOW_LENGTH_MS,
                    status="open",
                )
                .on_conflict_do_nothing(index_elements=["bucket_key"])
            )
            await session.execute(stmt)

        msg.status = "triaged"
        await session.commit()


async def triage_worker_loop(
    eventbus: PostgresEventBus,
    session_maker: async_sessionmaker,
) -> None:
    """Long-running coroutine: consume new_inbound events and triage."""
    retry_counts: dict[str, int] = {}
    async for msg_id in eventbus.subscribe("new_inbound"):
        try:
            await _process_message(msg_id, session_maker)
            retry_counts.pop(msg_id, None)
            await eventbus.publish("bucket_open", msg_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            count = retry_counts.get(msg_id, 0) + 1
            retry_counts[msg_id] = count
            logger.exception("triage: error on %s (attempt %d): %s", msg_id, count, exc)
            if count >= 3:
                async with session_maker() as session:
                    m = await session.get(InboundMessage, msg_id)
                    if m:
                        m.status = "failed"
                        m.retry_count = count
                        await session.commit()
                retry_counts.pop(msg_id, None)
