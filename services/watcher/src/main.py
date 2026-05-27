import asyncio
import os
import uuid
import yaml
import redis.asyncio as aioredis
from pathlib import Path

from clipbot_shared.logger import configure_logging, get_logger
from clipbot_shared.models import StreamStarted, StreamEnded, Platform
from clipbot_shared.queue import publish, QUEUE_STREAM_STARTED, QUEUE_STREAM_ENDED

from .twitch import TwitchWatcher
from .youtube import YouTubeWatcher
from .kick import KickWatcher
from .hashtags import generate_hashtags

log = get_logger("watcher")

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "45"))
CHANNELS_FILE = Path(os.environ.get("CHANNELS_FILE", "/app/config/channels.yaml"))


def build_watcher(channel: dict):
    platform = channel["platform"]
    slug = channel.get("slug") or channel.get("channel_id", "")
    name = channel["name"]
    channel_id = channel.get("channel_id") or slug
    if platform == "twitch":
        return TwitchWatcher(channel_id, slug, name)
    if platform == "youtube":
        return YouTubeWatcher(channel_id, slug, name)
    if platform == "kick":
        return KickWatcher(channel_id, slug, name)
    raise ValueError(f"Unknown platform: {platform}")


async def watch_channel(redis: aioredis.Redis, channel: dict, live_sessions: dict) -> None:
    watcher = build_watcher(channel)
    channel_key = f"{channel['platform']}:{watcher.channel_id}"
    try:
        is_live = await watcher.is_live()
    except Exception as exc:
        log.warning("is_live_check_failed", channel=watcher.name, error=repr(exc))
        return

    was_live = channel_key in live_sessions

    if is_live and not was_live:
        try:
            stream_url = await watcher.get_stream_url()
            meta = await watcher.get_metadata()
        except Exception as exc:
            log.error("get_stream_info_failed", channel=watcher.name, error=str(exc))
            return

        session_id = str(uuid.uuid4())
        live_sessions[channel_key] = session_id

        title = meta.get("title", "")
        category = meta.get("category", "")
        base_hashtags = channel.get("hashtags", [])
        hashtags = await generate_hashtags(title, category, base_hashtags, channel["platform"])

        event = StreamStarted(
            channel_id=watcher.channel_id,
            platform=Platform(channel["platform"]),
            stream_url=stream_url,
            streamer_name=meta.get("streamer", watcher.name),
            title=title,
            session_id=session_id,
            hashtags=hashtags,
            category=category,
        )
        await publish(redis, QUEUE_STREAM_STARTED, event)
        log.info(
            "stream_started",
            channel=watcher.name,
            platform=channel["platform"],
            session_id=session_id,
            trace_id=event.trace_id,
        )

    elif not is_live and was_live:
        session_id = live_sessions.pop(channel_key)
        event = StreamEnded(
            channel_id=watcher.channel_id,
            platform=Platform(channel["platform"]),
            session_id=session_id,
        )
        await publish(redis, QUEUE_STREAM_ENDED, event)
        log.info(
            "stream_ended",
            channel=watcher.name,
            platform=channel["platform"],
            session_id=session_id,
        )


async def main() -> None:
    configure_logging("watcher", os.environ.get("LOG_LEVEL", "INFO"))
    redis = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=False)
    channels_data = yaml.safe_load(CHANNELS_FILE.read_text())
    channels = channels_data.get("channels", [])
    live_sessions: dict[str, str] = {}

    log.info("watcher_started", channel_count=len(channels), poll_interval=POLL_INTERVAL)

    while True:
        tasks = [watch_channel(redis, ch, live_sessions) for ch in channels if ch.get("active", True)]
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
