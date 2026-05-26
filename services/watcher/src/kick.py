import asyncio
import httpx
from .base import BaseWatcher

KICK_API = "https://kick.com/api/v1/channels"


class KickWatcher(BaseWatcher):
    async def is_live(self) -> bool:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{KICK_API}/{self.slug}")
            resp.raise_for_status()
            data = resp.json()
            return data.get("livestream") is not None

    async def get_stream_url(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--get-url", "--no-warnings",
            f"https://kick.com/{self.slug}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return stdout.decode().strip().splitlines()[0]

    async def get_metadata(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{KICK_API}/{self.slug}")
            resp.raise_for_status()
            data = resp.json()
            ls = data.get("livestream") or {}
            return {
                "title": ls.get("session_title", ""),
                "streamer": data.get("user", {}).get("username", self.name),
                "category": ls.get("categories", [{}])[0].get("name", "") if ls.get("categories") else "",
                "thumbnail": ls.get("thumbnail", {}).get("url", "") if ls.get("thumbnail") else "",
            }
