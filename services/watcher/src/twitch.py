import os
import time
import asyncio
import httpx
from .base import BaseWatcher

TWITCH_API = "https://api.twitch.tv/helix"
TWITCH_AUTH = "https://id.twitch.tv/oauth2/token"


class TwitchWatcher(BaseWatcher):
    def __init__(self, channel_id: str, slug: str, name: str):
        super().__init__(channel_id, slug, name)
        self._client_id = os.environ["TWITCH_CLIENT_ID"]
        self._client_secret = os.environ["TWITCH_CLIENT_SECRET"]
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(TWITCH_AUTH, data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            })
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expires_at = time.time() + data["expires_in"]
            return self._token

    async def is_live(self) -> bool:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{TWITCH_API}/streams",
                params={"user_login": self.slug},
                headers={"Client-Id": self._client_id, "Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return len(resp.json().get("data", [])) > 0

    async def get_stream_url(self) -> str:
        # yt-dlp resolves the HLS URL directly from Twitch
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--get-url", "--no-warnings",
            f"https://www.twitch.tv/{self.slug}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return stdout.decode().strip().splitlines()[0]

    async def get_metadata(self) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{TWITCH_API}/streams",
                params={"user_login": self.slug},
                headers={"Client-Id": self._client_id, "Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data = resp.json().get("data", [{}])[0]
            return {
                "title": data.get("title", ""),
                "streamer": self.name,
                "category": data.get("game_name", ""),
                "thumbnail": data.get("thumbnail_url", ""),
            }
