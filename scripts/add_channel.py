#!/usr/bin/env python3
"""
Usage: python scripts/add_channel.py --platform twitch --slug nomeDoCanal \
       --name "Nome do Streamer" --tiktok-account conta_tiktok_1
"""
import argparse
import sys
import os
from pathlib import Path

CHANNELS_FILE = Path(os.environ.get("CHANNELS_FILE", "config/channels.yaml"))


def main():
    parser = argparse.ArgumentParser(description="Add a channel to channels.yaml")
    parser.add_argument("--platform", choices=["twitch", "youtube", "kick"], required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--channel-id", default=None)
    parser.add_argument("--name", required=True)
    parser.add_argument("--tiktok-account", required=True)
    parser.add_argument("--hashtags", nargs="+", default=[])
    parser.add_argument("--clip-min-score", type=float, default=0.55)
    parser.add_argument("--inactive", action="store_true")
    args = parser.parse_args()

    import yaml

    if CHANNELS_FILE.exists():
        data = yaml.safe_load(CHANNELS_FILE.read_text()) or {}
    else:
        data = {}

    channels = data.get("channels", [])

    channel_id = args.channel_id or args.slug
    new_channel = {
        "platform": args.platform,
        "slug": args.slug,
        "channel_id": channel_id,
        "name": args.name,
        "active": not args.inactive,
        "tiktok_account": args.tiktok_account,
        "hashtags": args.hashtags or [f"#{args.platform}", "#IRL", "#live"],
        "clip_min_score": args.clip_min_score,
    }

    existing = next(
        (i for i, ch in enumerate(channels) if ch.get("slug") == args.slug and ch.get("platform") == args.platform),
        None,
    )
    if existing is not None:
        channels[existing] = new_channel
        print(f"Updated existing channel: {args.slug} ({args.platform})")
    else:
        channels.append(new_channel)
        print(f"Added new channel: {args.slug} ({args.platform})")

    data["channels"] = channels
    CHANNELS_FILE.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False))
    print(f"Saved to {CHANNELS_FILE}")


main()
