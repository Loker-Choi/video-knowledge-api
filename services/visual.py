from __future__ import annotations

from app.glm import analyze_frame_grids_with_glm, transcribe_audio_with_glm
from app.media import build_frame_grids, cache_dir_for_url, download_media, extract_keyframes
from app.models import ExtractRequest, FrameGridInfo, KeyframeInfo, TranscriptInfo, VisualAnalysisInfo
from config import get_settings
from services.cache import cleanup_workdir
from utils.stage_log import log_stage


def fetch_glm_stt_transcript(
    url: str,
    platform: str,
    payload: ExtractRequest,
    warnings: list[str],
) -> TranscriptInfo:
    settings = get_settings()
    workdir = cache_dir_for_url(url, platform, settings.cache_root) / "stt"
    try:
        log_stage("audio_download_start")
        audio_path = download_media(url, platform, workdir, media_type="audio")
        log_stage("audio_download_done", size_bytes=audio_path.stat().st_size if audio_path.exists() else None)
        warnings.append("Downloaded audio for GLM STT.")
        return transcribe_audio_with_glm(
            audio_path,
            model=payload.glm_stt_model,
            segment_seconds=payload.stt_segment_seconds,
            max_segment_mb=payload.stt_max_segment_mb,
        )
    finally:
        log_stage("cache_cleanup", path_type="stt")
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
        log_stage("video_download_start")
        video_path = download_media(url, platform, workdir, media_type="video")
        log_stage("video_download_done", size_bytes=video_path.stat().st_size if video_path.exists() else None)
        warnings.append("Downloaded video for keyframe extraction.")
        log_stage("keyframe_extract_start", frame_interval=payload.frame_interval, max_keyframes=payload.max_keyframes)
        keyframes = extract_keyframes(
            video_path,
            workdir / "frames",
            frame_interval=payload.frame_interval,
            max_keyframes=payload.max_keyframes,
        )
        log_stage("keyframe_extract_done", count=len(keyframes))
        log_stage("frame_grid_build_start", grid_size=payload.grid_size)
        frame_grids = build_frame_grids(
            keyframes,
            workdir / "grids",
            grid_size=payload.grid_size,
        )
        log_stage("frame_grid_build_done", count=len(frame_grids))

        keyframe_result = VisualAnalysisInfo(
            source="keyframes",
            model=None,
            frame_interval=payload.frame_interval,
            grid_size=payload.grid_size,
            keyframes=keyframes,
            frame_grids=frame_grids,
            summary="",
        )

        if not payload.include_visual_analysis:
            return sanitize_visual_paths(keyframe_result)

        try:
            log_stage("glm_visual_start", grids=len(frame_grids), model=payload.glm_vision_model)
            return sanitize_visual_paths(analyze_frame_grids_with_glm(
                frame_grids,
                model=payload.glm_vision_model,
                prompt=payload.visual_prompt,
                frame_interval=payload.frame_interval,
                grid_size=payload.grid_size,
            ))
        except Exception as exc:
            log_stage("glm_visual_failed", message=str(exc))
            warnings.append(f"GLM visual analysis failed: {exc}")
            return sanitize_visual_paths(keyframe_result)
    finally:
        log_stage("cache_cleanup", path_type="visual")
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
