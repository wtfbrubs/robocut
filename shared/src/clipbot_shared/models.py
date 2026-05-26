from pydantic import BaseModel, Field
from enum import Enum
from typing import Literal
import uuid


class Platform(str, Enum):
    TWITCH = "twitch"
    YOUTUBE = "youtube"
    KICK = "kick"


class ClipStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class StreamStarted(BaseModel):
    event_type: Literal["stream.started"] = "stream.started"
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str
    platform: Platform
    stream_url: str
    streamer_name: str
    title: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hashtags: list[str] = []
    category: str = ""


class StreamEnded(BaseModel):
    event_type: Literal["stream.ended"] = "stream.ended"
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str
    platform: Platform
    session_id: str


class ClipCandidate(BaseModel):
    event_type: Literal["clip.candidate"] = "clip.candidate"
    trace_id: str
    channel_id: str
    platform: Platform
    session_id: str
    stream_url: str
    start_ts: float
    end_ts: float
    score: float
    reason: Literal["audio_spike", "scene_change", "scheduled"]
    streamer_name: str = ""
    hashtags: list[str] = []


class ClipReady(BaseModel):
    event_type: Literal["clip.ready"] = "clip.ready"
    trace_id: str
    channel_id: str
    platform: Platform
    session_id: str
    candidate_id: str
    storage_key: str
    duration: float
    streamer_name: str
    hashtags: list[str] = []


class UploadDone(BaseModel):
    event_type: Literal["upload.done"] = "upload.done"
    trace_id: str
    clip_id: str
    tiktok_account_id: str
    publish_id: str
    tiktok_url: str | None = None
    status: Literal["success", "failed"]
