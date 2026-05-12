from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from .extractors import build_transcript
from .media import split_audio
from .models import FrameGridInfo, TranscriptInfo, VisualAnalysisInfo
from config import get_settings


class GlmError(RuntimeError):
    pass


def glm_client() -> Any:
    settings = get_settings()
    api_key = settings.glm_api_key or settings.zhipuai_api_key
    if not api_key:
        raise GlmError("Set GLM_API_KEY before using GLM STT or visual analysis")
    try:
        from zhipuai import ZhipuAI
    except ImportError as exc:
        raise GlmError("Install zhipuai before using GLM STT or visual analysis") from exc
    return ZhipuAI(api_key=api_key)


def transcribe_audio_with_glm(
    audio_path: Path,
    *,
    model: str = "glm-asr",
    segment_seconds: int = 25,
    max_segment_mb: int = 20,
) -> TranscriptInfo:
    client = glm_client()
    segment_dir = audio_path.parent / "audio_segments"
    segments = split_audio(audio_path, segment_dir, segment_seconds=segment_seconds, max_segment_mb=max_segment_mb)
    if not segments:
        raise GlmError("No audio segments were generated for GLM STT")

    raw_segments: list[dict[str, object]] = []
    for index, segment_path in enumerate(segments):
        start = float(index * segment_seconds)
        text = transcribe_audio_segment(client, segment_path, model=model)
        if text:
            raw_segments.append({"start": start, "duration": float(segment_seconds), "text": text})

    if not raw_segments:
        raise GlmError("GLM STT returned empty transcript")

    return build_transcript(
        source="glm_asr",
        raw_segments=raw_segments,
        language="auto",
        is_generated=True,
    )


def transcribe_audio_segment(client: Any, segment_path: Path, *, model: str) -> str:
    with segment_path.open("rb") as audio_file:
        response = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
        )
    text = getattr(response, "text", None)
    if text is None and isinstance(response, dict):
        text = response.get("text")
    return str(text or "").strip()


def analyze_frame_grids_with_glm(
    frame_grids: list[FrameGridInfo],
    *,
    model: str = "glm-4.5v",
    prompt: str,
    frame_interval: int,
    grid_size: list[int],
) -> VisualAnalysisInfo:
    if not frame_grids:
        raise GlmError("No frame grids were generated for visual analysis")

    client = glm_client()
    content: list[dict[str, object]] = [
        {
            "type": "text",
            "text": prompt,
        }
    ]

    enriched_grids: list[FrameGridInfo] = []
    keyframes = []
    for grid in frame_grids:
        if not grid.path:
            continue
        image_url = image_data_url(Path(grid.path))
        content.append({"type": "text", "text": f"拼图 {grid.index}，时间范围 {grid.timestamp_text}"})
        content.append({"type": "image_url", "image_url": {"url": image_url}})
        enriched_grids.append(grid.model_copy(update={"image_base64": None}))
        keyframes.extend(grid.keyframes)

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
    )
    summary = response.choices[0].message.content if getattr(response, "choices", None) else ""
    return VisualAnalysisInfo(
        source="glm_vision",
        model=model,
        frame_interval=frame_interval,
        grid_size=grid_size,
        keyframes=keyframes,
        frame_grids=enriched_grids,
        summary=str(summary or "").strip(),
    )


def image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
