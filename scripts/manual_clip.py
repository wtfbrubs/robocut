#!/usr/bin/env python3
"""
Usage: python scripts/manual_clip.py --platform twitch --channel nomeDoCanalTwitch \
       --url "https://..." --start 0 --end 60
"""
import argparse
import asyncio
import os
import uuid
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared", "src"))

import redis.asyncio as aioredis

from clipbot_shared.models import ClipCandidate, Platform
from clipbot_shared.queue import publish, QUEUE_CLIP_CANDIDATE
from clipbot_shared.logger import configure_logging


async def main():
    configure_logging("manual-clip")
    parser = argparse.ArgumentParser(description="Manually enqueue a clip candidate")
    parser.add_argument("--platform", choices=["twitch", "youtube", "kick"], required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=60.0)
    parser.add_argument("--session", default=str(uuid.uuid4()))
    args = parser.parse_args()

    redis = aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    candidate = ClipCandidate(
        trace_id=str(uuid.uuid4()),
        channel_id=args.channel,
        platform=Platform(args.platform),
        session_id=args.session,
        stream_url=args.url,
        start_ts=args.start,
        end_ts=args.end,
        score=1.0,
        reason="scheduled",
    )
    await publish(redis, QUEUE_CLIP_CANDIDATE, candidate)
    print(candidate.model_dump_json(indent=2))
    await redis.aclose()


asyncio.run(main())
