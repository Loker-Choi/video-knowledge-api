from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


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

    fallback_to_glm_stt: bool = Field(default=False)
    include_visual_analysis: bool = Field(default=False)
    include_keyframes: bool = Field(default=False)
    frame_interval: int = Field(default=6, ge=1, le=30)
    grid_size: list[int] = Field(default_factory=lambda: [2, 2], min_length=2, max_length=2)
    max_keyframes: int = Field(default=16, ge=1, le=64)
    stt_segment_seconds: int = Field(default=25, ge=5, le=30)
    stt_max_segment_mb: int = Field(default=20, ge=1, le=25)
    glm_stt_model: str = Field(default="glm-asr")
    glm_vision_model: str = Field(default="glm-4.5v")
    visual_prompt: str = Field(default="请按时间顺序概括这些视频关键帧中的主要画面、文字和事件。")

    @field_validator("grid_size")
    @classmethod
    def validate_grid_size(cls, value: list[int]) -> list[int]:
        if len(value) != 2 or any(item <= 0 for item in value):
            raise ValueError("grid_size must contain two positive integers")
        if value[0] * value[1] > 9:
            raise ValueError("grid_size can contain at most 9 frames per grid")
        return value


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


class KeyframeInfo(BaseModel):
    index: int
    timestamp: float
    timestamp_text: str
    path: str | None = None
    image_base64: str | None = None


class FrameGridInfo(BaseModel):
    index: int
    start: float | None = None
    end: float | None = None
    timestamp_text: str
    path: str | None = None
    keyframes: list[KeyframeInfo] = Field(default_factory=list)
    image_base64: str | None = None


class VisualAnalysisInfo(BaseModel):
    source: str = "glm_vision"
    model: str | None = None
    frame_interval: int
    grid_size: list[int] = Field(default_factory=list)
    keyframes: list[KeyframeInfo] = Field(default_factory=list)
    frame_grids: list[FrameGridInfo] = Field(default_factory=list)
    summary: str = ""


class ExtractResponse(BaseModel):
    ok: bool
    platform: str
    video_id: str | None = None
    url: str
    metadata: MetadataInfo | None = None
    transcript: TranscriptInfo | None = None
    visual_analysis: VisualAnalysisInfo | None = None
    dify_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
