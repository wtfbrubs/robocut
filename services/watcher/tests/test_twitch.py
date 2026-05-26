import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.twitch import TwitchWatcher


@pytest.fixture
def watcher():
    os.environ.setdefault("TWITCH_CLIENT_ID", "test_id")
    os.environ.setdefault("TWITCH_CLIENT_SECRET", "test_secret")
    return TwitchWatcher("test_channel", "test_channel", "Test Channel")


@pytest.mark.asyncio
async def test_is_live_true(watcher):
    with patch("src.twitch.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "tok", "expires_in": 3600}
        token_resp.raise_for_status = MagicMock()

        stream_resp = MagicMock()
        stream_resp.json.return_value = {"data": [{"user_login": "test_channel"}]}
        stream_resp.raise_for_status = MagicMock()

        mock_client.post = AsyncMock(return_value=token_resp)
        mock_client.get = AsyncMock(return_value=stream_resp)

        result = await watcher.is_live()
        assert result is True


@pytest.mark.asyncio
async def test_is_live_false(watcher):
    with patch("src.twitch.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "tok", "expires_in": 3600}
        token_resp.raise_for_status = MagicMock()

        stream_resp = MagicMock()
        stream_resp.json.return_value = {"data": []}
        stream_resp.raise_for_status = MagicMock()

        mock_client.post = AsyncMock(return_value=token_resp)
        mock_client.get = AsyncMock(return_value=stream_resp)

        result = await watcher.is_live()
        assert result is False
