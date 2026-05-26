import asyncio
from clipbot_shared.storage import download, upload, formatted_key, tmp_path


async def format_vertical(s3_raw_key: str, trace_id: str) -> str:
    """Downloads raw clip, formats to 9:16 vertical, uploads result. Returns S3 key."""
    local_in = tmp_path(f"{trace_id}_raw.mp4")
    local_out = tmp_path(f"{trace_id}_formatted.mp4")
    try:
        await download(s3_raw_key, local_in)

        vf = (
            "[0:v]scale=960:540,boxblur=20:5[bg];"
            "[0:v]scale=-1:960[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[v];"
            "[v]scale=540:960[out]"
        )
        cmd = [
            "ffmpeg", "-threads", "1", "-loglevel", "warning",
            "-i", str(local_in),
            "-filter_complex", vf,
            "-map", "[out]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-b:v", "4M", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-y", str(local_out),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        if proc.returncode != 0 or not local_out.exists() or local_out.stat().st_size == 0:
            raise RuntimeError(f"ffmpeg format failed: {stderr.decode()}")

        key = formatted_key(trace_id)
        await upload(local_out, key)
        return key
    finally:
        local_in.unlink(missing_ok=True)
        local_out.unlink(missing_ok=True)
