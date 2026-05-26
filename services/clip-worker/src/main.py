import asyncio
import os
import uuid
import yaml
import redis.asyncio as aioredis
from pathlib import Path

from clipbot_shared.logger import configure_logging, get_logger
from clipbot_shared.models import ClipCandidate, ClipReady
from clipbot_shared.queue import consume, publish, QUEUE_CLIP_CANDIDATE, QUEUE_CLIP_READY, send_to_dlq
from clipbot_shared.storage import ensure_bucket

from .clipper import cut_clip
from .formatter import format_vertical

log = get_logger("clip-worker")

CHANNELS_FILE = Path(os.environ.get("CHANNELS_FILE", "/app/config/channels.yaml"))


def load_channel_config() -> dict:
    data = yaml.safe_load(CHANNELS_FILE.read_text())
    return {
        (ch.get("platform"), ch.get("slug") or ch.get("channel_id")): ch
        for ch in data.get("channels", [])
    }



async def process(redis: aioredis.Redis, candidate: ClipCandidate, raw: bytes, channel_cfg: dict) -> None:
    log.info("clip_processing_started", trace_id=candidate.trace_id, reason=candidate.reason, channel=candidate.channel_id)
    try:
        s3_raw = await cut_clip(candidate)
        s3_formatted = await format_vertical(s3_raw, candidate.trace_id)

        ch = channel_cfg.get((candidate.platform.value, candidate.channel_id), {})

        ready = ClipReady(
            trace_id=candidate.trace_id,
            channel_id=candidate.channel_id,
            platform=candidate.platform,
            session_id=candidate.session_id,
            candidate_id=str(uuid.uuid4()),
            storage_key=s3_formatted,
            duration=candidate.end_ts - candidate.start_ts,
            streamer_name=ch.get("name", candidate.channel_id),
            hashtags=ch.get("hashtags", []),
        )
        await publish(redis, QUEUE_CLIP_READY, ready)
        log.info("clip_ready", trace_id=candidate.trace_id, storage_key=s3_formatted)
    except Exception as exc:
        log.error("clip_processing_failed", trace_id=candidate.trace_id, error=str(exc))
        await send_to_dlq(redis, raw, reason=str(exc))


async def main() -> None:
    configure_logging("clip-worker", os.environ.get("LOG_LEVEL", "INFO"))
    redis = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=False)
    await ensure_bucket()
    channel_cfg = load_channel_config()
    log.info("clip_worker_started")

    async for candidate, raw in consume(redis, QUEUE_CLIP_CANDIDATE, ClipCandidate):
        asyncio.create_task(process(redis, candidate, raw, channel_cfg))


if __name__ == "__main__":
    asyncio.run(main())
