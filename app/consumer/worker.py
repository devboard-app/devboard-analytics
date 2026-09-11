import asyncio
import logging
from datetime import datetime, timezone

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.config import settings
from app.database import connect_to_mongo, ensure_indexes, get_database
from app.schemas.events import IGNORED_ACTIONS
from app.services.ingestion import record_event

from .translation import created_at_from_message_id, translate_event

STREAM = "devboard:events"
GROUP = "devboard-analytics-group"
CONSUMER = "devboard-analytics-1"

MAX_ATTEMPTS = 3
PENDING_SCAN_LIMIT = 5000 #must cover xautoclaim's max reclaim capacity (50 iterations * count=100)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


async def ensure_group(redis: Redis) -> None:
    try:
        await redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        logger.info("Consumer group created.")
    except ResponseError as e:  
        if "BUSYGROUP" in str(e):
            logger.info("Consumer group already exists.")
        else:
            raise

async def run() -> None:
    await connect_to_mongo()
    db = get_database()
    await ensure_indexes()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=10)
    await ensure_group(redis)
    logger.info("Consumer started, waiting for events...")

    while True:
        try:
            claimed = []
            cursor = "0-0"
            for _ in range(50):
                cursor, batch, _ = await redis.xautoclaim(STREAM, GROUP, CONSUMER, min_idle_time=30000, start_id=cursor, count=100)
                claimed.extend(batch)
                if cursor == "0-0": 
                    break
            else:
                logger.warning("Reclaim scan hit the iteration cap, continuing anyway")
            if claimed:
                logger.info(f"Reclaimed {len(claimed)} pending messages")

            attempts = {
                entry["message_id"]: int(entry["times_delivered"])
                for entry in await redis.xpending_range(STREAM, GROUP, min="-", max="+", count=PENDING_SCAN_LIMIT)
            } if claimed else {}

            results = await redis.xreadgroup(GROUP, CONSUMER, {STREAM: ">"}, count=10, block=5000)
            all_messages = claimed + (results[0][1] if results else []) #type:ignore

            for message_id, data in all_messages: # type: ignore
                if data.get("event") in IGNORED_ACTIONS:
                    await redis.xack(STREAM, GROUP, message_id)
                    logger.info(f"Ignored event {data.get('event')} for message {message_id}")
                    continue
                if attempts.get(message_id, 1) > MAX_ATTEMPTS:
                    await db.failed_events.insert_one({
                        "message_id": message_id,
                        "raw_data": data,
                        "error": "max attempts exceeded",
                        "failed_at": datetime.now(timezone.utc)
                    })
                    await redis.xack(STREAM, GROUP, message_id)
                    logger.error(f"Gave up on {message_id} after {attempts[message_id]} attempts")
                    continue
                try:
                    event=translate_event(data)
                    event.id=message_id
                    event.created_at=created_at_from_message_id(message_id) or datetime.now(timezone.utc)
                    await record_event(event, db)
                    await redis.xack(STREAM, GROUP, message_id)
                    logger.info(f"Processed {event.action} for {event.entity_key}")
                except (ValidationError, ValueError, KeyError) as e:
                    await db.failed_events.insert_one({
                        "message_id": message_id,
                        "raw_data": data,
                        "error": str(e),
                        "failed_at": datetime.now(timezone.utc)
                    })
                    await redis.xack(STREAM, GROUP, message_id)
                    logger.error(f"Failed to process event {data}: {e}")
                except Exception: 
                    logger.exception(f"Write failed for message {message_id}")
                    raise
        except Exception as e :  # noqa: BLE001
            logger.error(f"Consumer error: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(run())