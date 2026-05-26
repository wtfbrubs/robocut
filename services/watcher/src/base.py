from abc import ABC, abstractmethod


class BaseWatcher(ABC):
    def __init__(self, channel_id: str, slug: str, name: str):
        self.channel_id = channel_id
        self.slug = slug
        self.name = name

    @abstractmethod
    async def is_live(self) -> bool: ...

    @abstractmethod
    async def get_stream_url(self) -> str: ...

    @abstractmethod
    async def get_metadata(self) -> dict: ...
