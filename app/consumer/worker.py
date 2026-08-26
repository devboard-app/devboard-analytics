import asyncio
import logging
from datetime import datetime, timezone

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.config import settings
from app.database import connect_to_mongo, get_database
from app.services.ingestion import record_event

from .translation import translate_event

STREAM = "devboard:events"
GROUP = "devboard-analytics-group"
CONSUMER = "devboard-analytics-1"

logging.basicConfig(level=logging.INFO)
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
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=10)
    await ensure_group(redis)
    logger.info("Consumer started, waiting for events...")

    while True:
        try:
            results = await redis.xreadgroup(GROUP, CONSUMER, {STREAM: ">"}, count=10, block=5000)
            if not results:
                continue

            for stream, messages in results:
                for message_id, data in messages: # type: ignore
                    try:
                        event=translate_event(data)
                        event.id=message_id
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
        except Exception as e :  # noqa: BLE001
            logger.error(f"Consumer error: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(run())