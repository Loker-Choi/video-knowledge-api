from __future__ import annotations

from app.glm import analyze_frame_grids_with_glm, transcribe_audio_with_glm
from app.media import build_frame_grids, cache_dir_for_url, download_media, extract_keyframes
from app.models import ExtractRequest, FrameGridInfo, KeyframeInfo, TranscriptInfo, VisualAnalysisInfo
from config import get_settings
from services.cache import cleanup_workdir


def fetch_glm_stt_transcript(
    url: str,
    platform: str,
    payload: ExtractRequest,
    warnings: list[str],
) -> TranscriptInfo:
    settings = get_settings()
    workdir = cache_dir_for_url(url, platform, settings.cache_root) / "stt"
    try:
        audio_path = download_media(url, platform, workdir, media_type="audio")
        warnings.append("Downloaded audio for GLM STT.")
        return transcribe_audio_with_glm(
            audio_path,
            model=payload.glm_stt_model,
            segment_seconds=payload.stt_segment_seconds,
            max_segment_mb=payload.stt_max_segment_mb,
        )
    finally:
        cleanup_workdir(workdir)


def fetch_visual_analysis(
    url: str,
    platform: str,
    payload: ExtractRequest,
    warnings: list[str],
) -> VisualAnalysisInfo:
    settings = get_settings()
    workdir = cache_dir_for_url(url, platform, settings.cache_root) / "visual"
    try:
        video_path = download_media(url, platform, workdir, media_type="video")
        warnings.append("Downloaded video for keyframe extraction.")
        keyframes = extract_keyframes(
            video_path,
            workdir / "frames",
            frame_interval=payload.frame_interval,
            max_keyframes=payload.max_keyframes,
        )
        frame_grids = build_frame_grids(
            keyframes,
            workdir / "grids",
            grid_size=payload.grid_size,
        )

        if not payload.include_visual_analysis:
            return sanitize_visual_paths(
                VisualAnalysisInfo(
                    source="keyframes",
                    model=None,
                    frame_interval=payload.frame_interval,
                    grid_size=payload.grid_size,
                    keyframes=keyframes,
                    frame_grids=frame_grids,
                    summary="",
                )
            )

        return sanitize_visual_paths(
            analyze_frame_grids_with_glm(
                frame_grids,
                model=payload.glm_vision_model,
                prompt=payload.visual_prompt,
                frame_interval=payload.frame_interval,
                grid_size=payload.grid_size,
            )
        )
    finally:
        cleanup_workdir(workdir)


def sanitize_visual_paths(info: VisualAnalysisInfo) -> VisualAnalysisInfo:
    if get_settings().keep_cache:
        return info
    return VisualAnalysisInfo(
        source=info.source,
        model=info.model,
        frame_interval=info.frame_interval,
        grid_size=info.grid_size,
        keyframes=[
            KeyframeInfo(
                index=frame.index,
                timestamp=frame.timestamp,
                timestamp_text=frame.timestamp_text,
            )
            for frame in info.keyframes
        ],
        frame_grids=[
            FrameGridInfo(
                index=grid.index,
                start=grid.start,
                end=grid.end,
                timestamp_text=grid.timestamp_text,
                keyframes=[
                    KeyframeInfo(
                        index=frame.index,
                        timestamp=frame.timestamp,
                        timestamp_text=frame.timestamp_text,
                    )
                    for frame in grid.keyframes
                ],
            )
            for grid in info.frame_grids
        ],
        summary=info.summary,
    )
