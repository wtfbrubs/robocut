import asyncio
import os
import yaml
import redis.asyncio as aioredis
from pathlib import Path

from clipbot_shared.logger import configure_logging, get_logger
from clipbot_shared.models import ClipReady, UploadDone
from clipbot_shared.queue import consume, publish, QUEUE_CLIP_READY, QUEUE_UPLOAD_DONE, send_to_dlq
from clipbot_shared.storage import download, delete_job, tmp_path

from .tiktok import TikTokUploader

log = get_logger("uploader")

CHANNELS_FILE = Path(os.environ.get("CHANNELS_FILE", "/app/config/channels.yaml"))


def load_tiktok_accounts() -> dict[str, str]:
    accounts = {}
    for key, val in os.environ.items():
        if key.startswith("TIKTOK_ACCESS_TOKEN_"):
            account_id = key.removeprefix("TIKTOK_ACCESS_TOKEN_").lower()
            accounts[account_id] = val
    return accounts


def load_channel_accounts() -> dict[str, str]:
    data = yaml.safe_load(CHANNELS_FILE.read_text())
    return {
        ch.get("slug") or ch.get("channel_id"): ch.get("tiktok_account", "")
        for ch in data.get("channels", [])
    }


async def process(
    redis: aioredis.Redis,
    event: ClipReady,
    raw: bytes,
    tiktok_accounts: dict,
    channel_accounts: dict,
) -> None:
    account_id = channel_accounts.get(event.channel_id, "")
    token = tiktok_accounts.get(account_id)
    if not token:
        log.error("no_tiktok_token", channel=event.channel_id, account_id=account_id, trace_id=event.trace_id)
        await send_to_dlq(redis, raw, reason=f"no token for account {account_id}")
        return

    hashtags_str = " ".join(event.hashtags)
    title = f"🔴 {event.streamer_name} | {event.platform.value.upper()} {hashtags_str}"

    local = tmp_path(f"{event.trace_id}_upload.mp4")
    log.info("upload_started", trace_id=event.trace_id, channel=event.channel_id, account=account_id)

    uploader = TikTokUploader(token)
    try:
        await download(event.storage_key, local)
        publish_id = await uploader.upload_video(local, title)
        await uploader.poll_status(publish_id)

        done = UploadDone(
            trace_id=event.trace_id,
            clip_id=event.candidate_id,
            tiktok_account_id=account_id,
            publish_id=publish_id,
            status="success",
        )
        await publish(redis, QUEUE_UPLOAD_DONE, done)
        await delete_job(event.trace_id)
        log.info("upload_done", trace_id=event.trace_id, publish_id=publish_id, account=account_id)
    except PermissionError:
        log.error("tiktok_token_expired", trace_id=event.trace_id, account=account_id)
        await send_to_dlq(redis, raw, reason="token_expired")
    except Exception as exc:
        log.error("upload_failed", trace_id=event.trace_id, error=str(exc), account=account_id)
        done = UploadDone(
            trace_id=event.trace_id,
            clip_id=event.candidate_id,
            tiktok_account_id=account_id,
            publish_id="",
            status="failed",
        )
        await publish(redis, QUEUE_UPLOAD_DONE, done)
    finally:
        local.unlink(missing_ok=True)


async def main() -> None:
    configure_logging("uploader", os.environ.get("LOG_LEVEL", "INFO"))
    redis = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=False)
    tiktok_accounts = load_tiktok_accounts()
    channel_accounts = load_channel_accounts()
    log.info("uploader_started", accounts=list(tiktok_accounts.keys()))

    async for event, raw in consume(redis, QUEUE_CLIP_READY, ClipReady):
        asyncio.create_task(process(redis, event, raw, tiktok_accounts, channel_accounts))


if __name__ == "__main__":
    asyncio.run(main())
