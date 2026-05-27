import asyncio
from curl_cffi.requests import AsyncSession
from .base import BaseWatcher

KICK_API = "https://kick.com/api/v2/channels"
_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://kick.com/",
}


async def _kick_get(path: str) -> dict:
    async with AsyncSession(impersonate="chrome") as s:
        resp = await s.get(f"{KICK_API}/{path}", headers=_HEADERS, timeout=15)
        if resp.status_code == 404:
            return {"data": None}
        resp.raise_for_status()
        return resp.json()


class KickWatcher(BaseWatcher):
    async def is_live(self) -> bool:
        data = await _kick_get(f"{self.slug}/livestream")
        return data.get("data") is not None

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
        data = await _kick_get(f"{self.slug}/livestream")
        ls = data.get("data") or {}
        categories = ls.get("categories") or []
        return {
            "title": ls.get("session_title", ""),
            "streamer": ls.get("channel", {}).get("slug", self.name),
            "category": categories[0].get("name", "") if categories else "",
            "thumbnail": ls.get("thumbnail", {}).get("url", "") if ls.get("thumbnail") else "",
        }
