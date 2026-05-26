import httpx
import asyncio
from pathlib import Path

TIKTOK_API = "https://open.tiktokapis.com"
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB


class TikTokUploader:
    def __init__(self, access_token: str):
        self._token = access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    async def upload_video(self, file_path: Path, title: str) -> str:
        """Initializes upload, sends chunks, returns publish_id."""
        file_size = file_path.stat().st_size
        total_chunks = -(-file_size // CHUNK_SIZE)  # ceiling division

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{TIKTOK_API}/v2/post/publish/video/init/",
                headers=self._headers(),
                json={
                    "post_info": {
                        "title": title[:150],
                        "privacy_level": "SELF_ONLY",
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                        "video_cover_timestamp_ms": 1000,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": file_size,
                        "chunk_size": CHUNK_SIZE,
                        "total_chunk_count": total_chunks,
                    },
                },
            )
            if resp.status_code == 401:
                raise PermissionError("TikTok token expired or invalid")
            resp.raise_for_status()
            data = resp.json().get("data", {})
            publish_id = data["publish_id"]
            upload_url = data["upload_url"]

        await self._upload_chunks(file_path, upload_url, file_size)
        return publish_id

    async def _upload_chunks(self, file_path: Path, upload_url: str, file_size: int) -> None:
        offset = 0
        async with httpx.AsyncClient(timeout=120) as client:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    end = offset + len(chunk) - 1
                    resp = await client.put(
                        upload_url,
                        content=chunk,
                        headers={
                            "Content-Type": "video/mp4",
                            "Content-Length": str(len(chunk)),
                            "Content-Range": f"bytes {offset}-{end}/{file_size}",
                        },
                    )
                    resp.raise_for_status()
                    offset += len(chunk)

    async def poll_status(self, publish_id: str, max_attempts: int = 20) -> str:
        """Polls until PUBLISH_COMPLETE or terminal error. Returns final status."""
        async with httpx.AsyncClient(timeout=15) as client:
            for _ in range(max_attempts):
                resp = await client.post(
                    f"{TIKTOK_API}/v2/post/publish/status/fetch/",
                    headers=self._headers(),
                    json={"publish_id": publish_id},
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("retry-after", "10"))
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                status = resp.json().get("data", {}).get("status", "")
                if status == "PUBLISH_COMPLETE":
                    return status
                if status in ("FAILED", "CANCELLED"):
                    raise RuntimeError(f"TikTok publish failed with status: {status}")
                await asyncio.sleep(10)
        raise TimeoutError(f"TikTok status polling timed out for publish_id={publish_id}")
