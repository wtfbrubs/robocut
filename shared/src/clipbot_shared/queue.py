import json
import redis.asyncio as aioredis
from typing import AsyncIterator, Type
from pydantic import BaseModel

QUEUE_STREAM_STARTED = "queue:stream.started"
QUEUE_STREAM_ENDED = "queue:stream.ended"
QUEUE_CLIP_CANDIDATE = "queue:clip.candidate"
QUEUE_CLIP_READY = "queue:clip.ready"
QUEUE_UPLOAD_DONE = "queue:upload.done"
QUEUE_DLQ = "queue:dlq"


async def publish(redis: aioredis.Redis, queue: str, message: BaseModel) -> None:
    await redis.lpush(queue, message.model_dump_json())


async def consume(
    redis: aioredis.Redis,
    queue: str,
    model: Type[BaseModel],
    timeout: int = 5,
) -> AsyncIterator[tuple[BaseModel, bytes]]:
    """Yields (parsed_message, raw_bytes). Caller acks by not raising."""
    while True:
        result = await redis.brpop(queue, timeout=timeout)
        if result is None:
            continue
        _, raw = result
        try:
            yield model.model_validate_json(raw), raw
        except Exception:
            await redis.lpush(QUEUE_DLQ, raw)


async def send_to_dlq(redis: aioredis.Redis, raw: bytes, reason: str) -> None:
    payload = {"reason": reason, "original": raw.decode()}
    await redis.lpush(QUEUE_DLQ, json.dumps(payload))
