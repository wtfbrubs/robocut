import asyncio
import os
from pathlib import Path
from clipbot_shared.models import ClipCandidate
from clipbot_shared.storage import upload, raw_key, tmp_path

CLIP_MAX_DURATION = float(os.environ.get("CLIP_MAX_DURATION", "60"))
CLIP_MIN_DURATION = float(os.environ.get("CLIP_MIN_DURATION", "10"))


async def cut_clip(candidate: ClipCandidate) -> str:
    """Returns S3 key of raw clip."""
    duration = min(candidate.end_ts - candidate.start_ts, CLIP_MAX_DURATION)
    if duration < CLIP_MIN_DURATION:
        raise ValueError(f"Clip too short: {duration}s")

    local = tmp_path(f"{candidate.trace_id}_raw.mp4")
    try:
        cmd = [
            "ffmpeg", "-threads", "1", "-loglevel", "warning",
            "-ss", str(candidate.start_ts),
            "-i", candidate.stream_url,
            "-t", str(duration),
            "-c", "copy",
            "-movflags", "+faststart",
            "-y", str(local),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode != 0 or not local.exists() or local.stat().st_size == 0:
            raise RuntimeError(f"ffmpeg clip failed: {stderr.decode()}")

        key = raw_key(candidate.trace_id)
        await upload(local, key)
        return key
    finally:
        local.unlink(missing_ok=True)
