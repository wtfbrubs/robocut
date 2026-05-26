import asyncio
import os
import redis.asyncio as aioredis

from clipbot_shared.logger import configure_logging, get_logger
from clipbot_shared.models import StreamStarted, ClipCandidate
from clipbot_shared.queue import consume, publish, QUEUE_STREAM_STARTED, QUEUE_CLIP_CANDIDATE, send_to_dlq

log = get_logger("detector")

WINDOW_SECONDS = float(os.environ.get("DETECTOR_WINDOW_SECONDS", "600"))
CLIP_MAX_DURATION = float(os.environ.get("CLIP_MAX_DURATION", "60"))


async def scheduled_clipper(redis: aioredis.Redis, event: StreamStarted) -> None:
    """Generates clip candidates at fixed intervals while the stream is active."""
    elapsed = 0.0
    log.info(
        "scheduled_clipper_started",
        session_id=event.session_id,
        channel=event.streamer_name,
        trace_id=event.trace_id,
    )
    while True:
        await asyncio.sleep(WINDOW_SECONDS)
        elapsed += WINDOW_SECONDS
        candidate = ClipCandidate(
            trace_id=event.trace_id,
            channel_id=event.channel_id,
            platform=event.platform,
            session_id=event.session_id,
            stream_url=event.stream_url,
            start_ts=max(0.0, elapsed - CLIP_MAX_DURATION),
            end_ts=elapsed,
            score=0.6,
            reason="scheduled",
            streamer_name=event.streamer_name,
            hashtags=event.hashtags,
        )
        await publish(redis, QUEUE_CLIP_CANDIDATE, candidate)
        log.info(
            "clip_candidate_emitted",
            session_id=event.session_id,
            reason="scheduled",
            start_ts=candidate.start_ts,
            end_ts=candidate.end_ts,
            trace_id=event.trace_id,
        )


async def main() -> None:
    configure_logging("detector", os.environ.get("LOG_LEVEL", "INFO"))
    redis = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=False)
    active_sessions: dict[str, asyncio.Task] = {}
    log.info("detector_started")

    async for event, raw in consume(redis, QUEUE_STREAM_STARTED, StreamStarted):
        if event.session_id not in active_sessions:
            task = asyncio.create_task(scheduled_clipper(redis, event))
            active_sessions[event.session_id] = task


if __name__ == "__main__":
    asyncio.run(main())
