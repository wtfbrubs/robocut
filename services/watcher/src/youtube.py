import asyncio
from .base import BaseWatcher


class YouTubeWatcher(BaseWatcher):
    def __init__(self, channel_id: str, slug: str, name: str):
        super().__init__(channel_id, slug, name)
        # slug here is the YouTube channel_id (UCxxxxxxx)
        self._channel_url = f"https://www.youtube.com/channel/{slug}/live"

    @staticmethod
    def _ytdlp_base() -> list[str]:
        return ["yt-dlp", "--username", "oauth2", "--password", ""]

    async def is_live(self) -> bool:
        proc = await asyncio.create_subprocess_exec(
            *self._ytdlp_base(),
            "--skip-download", "--print", "is_live",
            "--no-warnings", "--quiet", self._channel_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            return stdout.decode().strip().lower() == "true"
        except asyncio.TimeoutError:
            proc.kill()
            return False

    async def get_stream_url(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            *self._ytdlp_base(),
            "--get-url", "--no-warnings", self._channel_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return stdout.decode().strip().splitlines()[0]

    async def get_metadata(self) -> dict:
        proc = await asyncio.create_subprocess_exec(
            *self._ytdlp_base(),
            "--skip-download",
            "--print", "title",
            "--print", "uploader",
            "--no-warnings", "--quiet", self._channel_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            lines = stdout.decode().strip().splitlines()
            return {
                "title": lines[0] if lines else "",
                "streamer": lines[1] if len(lines) > 1 else self.name,
                "category": "",
                "thumbnail": "",
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"title": "", "streamer": self.name, "category": "", "thumbnail": ""}
