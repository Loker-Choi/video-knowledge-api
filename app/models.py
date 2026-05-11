from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


DEFAULT_LANGUAGES = ["zh-Hans", "zh-CN", "zh", "en"]


class ExtractRequest(BaseModel):
    url: str = Field(..., description="Bilibili or YouTube video URL.")
    languages: list[str] = Field(
        default_factory=lambda: DEFAULT_LANGUAGES.copy(),
        description="Preferred subtitle languages in descending priority.",
    )
    include_metadata: bool = Field(default=True)
    max_chars_per_chunk: int = Field(default=5000, ge=500, le=20000)
    preserve_formatting: bool = Field(default=False)

    # Reserved v2 knobs, kept in the API so Dify workflows do not need redesign later.
    include_keyframes: bool = Field(default=False)
    frame_interval: int = Field(default=6, ge=1, le=30)
    grid_size: list[int] = Field(default_factory=lambda: [2, 2], min_length=2, max_length=2)


class CookieUpdateRequest(BaseModel):
    platform: str = Field(..., description="Cookie platform, currently bilibili or youtube.")
    cookie: str = Field(..., description="Raw Cookie header string, for example: name=value; name2=value2.")


class TranscriptSegment(BaseModel):
    index: int
    start: float
    end: float | None = None
    duration: float | None = None
    timestamp: str
    text: str


class TranscriptInfo(BaseModel):
    source: str
    language: str | None = None
    language_name: str | None = None
    is_generated: bool | None = None
    has_timeline: bool = True
    segments: list[TranscriptSegment] = Field(default_factory=list)
    plain_text: str = ""
    timeline_text: str = ""


class ChapterInfo(BaseModel):
    start: float | None = None
    end: float | None = None
    title: str


class MetadataInfo(BaseModel):
    title: str | None = None
    duration: float | None = None
    uploader: str | None = None
    webpage_url: str | None = None
    thumbnail: str | None = None
    chapters: list[ChapterInfo] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class TextChunk(BaseModel):
    index: int
    start: float | None = None
    end: float | None = None
    text: str


class ExtractResponse(BaseModel):
    ok: bool
    platform: str
    video_id: str | None = None
    url: str
    metadata: MetadataInfo | None = None
    transcript: TranscriptInfo | None = None
    dify_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
