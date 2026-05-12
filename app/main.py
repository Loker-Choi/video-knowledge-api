from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .bilibili import fetch_bilibili_player_transcript
from .cookies import CookieStore, SUPPORTED_COOKIE_PLATFORMS
from .extractors import (
    ExtractionError,
    TranscriptNotFound,
    fetch_youtube_transcript,
    fetch_ytdlp_info,
    fetch_ytdlp_subtitle_transcript,
    metadata_from_ytdlp,
)
from .glm import analyze_frame_grids_with_glm, transcribe_audio_with_glm
from .media import build_frame_grids, cache_dir_for_url, download_media, extract_keyframes
from .models import (
    DEFAULT_LANGUAGES,
    CookieUpdateRequest,
    ExtractRequest,
    ExtractResponse,
    MetadataInfo,
    TranscriptInfo,
    VisualAnalysisInfo,
)
from .platforms import Platform, detect_platform
from .text_utils import chunk_segments


app = FastAPI(
    title="Video Analysis API",
    version="0.1.0",
    description="Extract Bilibili/YouTube subtitles and timeline text for Dify workflows.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, bool | str]:
    return {"ok": True, "service": "video-analysis-api"}


@app.get("/v1/auth/cookies/{platform}")
def get_cookie_status(platform: str) -> dict[str, object]:
    try:
        return {"ok": True, **CookieStore().status(platform)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/auth/cookies")
def update_cookie(payload: CookieUpdateRequest) -> dict[str, object]:
    try:
        CookieStore().set(payload.platform, payload.cookie)
        return {"ok": True, **CookieStore().status(payload.platform)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/v1/auth/cookies/{platform}")
def delete_cookie(platform: str) -> dict[str, object]:
    if platform not in SUPPORTED_COOKIE_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported cookie platform: {platform}")
    CookieStore().delete(platform)
    return {"ok": True, **CookieStore().status(platform)}


@app.post("/v1/video/extract", response_model=ExtractResponse)
def extract_video(payload: ExtractRequest) -> ExtractResponse:
    return extract_video_payload(payload)


@app.get("/v1/video/extract", response_model=ExtractResponse)
def extract_video_get(
    url: str = Query(..., description="Bilibili or YouTube video URL."),
    languages: str = Query(
        ",".join(DEFAULT_LANGUAGES),
        description="Comma-separated language priority list.",
    ),
    include_metadata: bool = True,
    max_chars_per_chunk: int = Query(5000, ge=500, le=20000),
) -> ExtractResponse:
    language_list = [item.strip() for item in languages.split(",") if item.strip()]
    return extract_video_payload(
        ExtractRequest(
            url=url,
            languages=language_list or DEFAULT_LANGUAGES.copy(),
            include_metadata=include_metadata,
            max_chars_per_chunk=max_chars_per_chunk,
        )
    )


def extract_video_payload(payload: ExtractRequest) -> ExtractResponse:
    url = str(payload.url)
    platform = detect_platform(url)
    warnings: list[str] = []
    transcript: TranscriptInfo | None = None
    metadata: MetadataInfo | None = None
    visual_analysis: VisualAnalysisInfo | None = None
    video_id: str | None = None

    if platform == Platform.UNKNOWN:
        return failure_response(
            platform=platform.value,
            url=url,
            error="UNSUPPORTED_PLATFORM",
            warnings=["Only Bilibili and YouTube URLs are supported."],
        )

    try:
        if payload.include_metadata or payload.include_visual_analysis or payload.include_keyframes:
            metadata = try_fetch_metadata(url, warnings, platform.value)

        if platform == Platform.YOUTUBE:
            video_id, transcript = fetch_youtube_transcript(
                url=url,
                languages=payload.languages,
                preserve_formatting=payload.preserve_formatting,
            )
            if payload.include_metadata and metadata is None:
                metadata = try_fetch_metadata(url, warnings, platform.value)
        else:
            cookie = CookieStore().get("bilibili")
            try:
                video_id, transcript = fetch_bilibili_player_transcript(url, cookie)
                if payload.include_metadata and metadata is None:
                    metadata = try_fetch_metadata(url, warnings, platform.value)
                warnings.append("Used Bilibili player API subtitle track.")
            except TranscriptNotFound as player_exc:
                warnings.append(str(player_exc))
                video_id, metadata, transcript = fetch_ytdlp_subtitle_transcript(
                    url,
                    payload.languages,
                    platform=platform.value,
                )

    except TranscriptNotFound as exc:
        warnings.append(str(exc))

        # YouTube transcript-api can fail in cloud IP ranges; try yt-dlp subtitles once.
        if platform == Platform.YOUTUBE:
            try:
                video_id, metadata, transcript = fetch_ytdlp_subtitle_transcript(url, payload.languages, platform.value)
                warnings.append("Fell back from youtube-transcript-api to yt-dlp subtitle tracks.")
            except Exception as fallback_exc:
                warnings.append(f"yt-dlp subtitle fallback failed: {fallback_exc}")

        if transcript is None:
            if metadata is None:
                metadata = try_fetch_metadata(url, warnings, platform.value)

            if payload.fallback_to_glm_stt:
                try:
                    transcript = fetch_glm_stt_transcript(url, platform.value, payload, warnings)
                    warnings.append("Used GLM-ASR because no usable platform subtitle was found.")
                except Exception as stt_exc:
                    warnings.append(f"GLM STT fallback failed: {stt_exc}")

            if transcript is None and not (payload.include_visual_analysis or payload.include_keyframes):
                return failure_response(
                    platform=platform.value,
                    url=url,
                    video_id=video_id,
                    metadata=metadata,
                    error="NO_TRANSCRIPT",
                    warnings=warnings or ["No usable subtitle/timeline track found."],
                )
            if transcript is None:
                warnings.append("No transcript was found; continuing with visual extraction.")
    except ExtractionError as exc:
        return failure_response(
            platform=platform.value,
            url=url,
            error=str(exc),
            warnings=warnings,
        )
    except Exception as exc:
        return failure_response(
            platform=platform.value,
            url=url,
            error=f"EXTRACTION_FAILED: {exc}",
            warnings=warnings,
        )

    if payload.include_visual_analysis or payload.include_keyframes:
        try:
            visual_analysis = fetch_visual_analysis(url, platform.value, payload, warnings)
        except Exception as visual_exc:
            warnings.append(f"Visual analysis failed: {visual_exc}")

    return ExtractResponse(
        ok=True,
        platform=platform.value,
        video_id=video_id,
        url=url,
        metadata=metadata,
        transcript=transcript,
        visual_analysis=visual_analysis,
        dify_payload=build_dify_payload(
            url=url,
            platform=platform.value,
            video_id=video_id,
            transcript=transcript,
            metadata=metadata,
            visual_analysis=visual_analysis,
            max_chars_per_chunk=payload.max_chars_per_chunk,
        ),
        warnings=warnings,
    )


def try_fetch_metadata(url: str, warnings: list[str], platform: str | None = None) -> MetadataInfo | None:
    try:
        return metadata_from_ytdlp(fetch_ytdlp_info(url, platform))
    except Exception as exc:
        warnings.append(f"Metadata fetch failed: {exc}")
        return None


def fetch_glm_stt_transcript(
    url: str,
    platform: str,
    payload: ExtractRequest,
    warnings: list[str],
) -> TranscriptInfo:
    workdir = cache_dir_for_url(url, platform) / "stt"
    audio_path = download_media(url, platform, workdir, media_type="audio")
    warnings.append(f"Downloaded audio for GLM STT: {audio_path}")
    return transcribe_audio_with_glm(
        audio_path,
        model=payload.glm_stt_model,
        segment_seconds=payload.stt_segment_seconds,
        max_segment_mb=payload.stt_max_segment_mb,
    )


def fetch_visual_analysis(
    url: str,
    platform: str,
    payload: ExtractRequest,
    warnings: list[str],
) -> VisualAnalysisInfo:
    workdir = cache_dir_for_url(url, platform) / "visual"
    video_path = download_media(url, platform, workdir, media_type="video")
    warnings.append(f"Downloaded video for keyframe extraction: {video_path}")
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
        return VisualAnalysisInfo(
            source="keyframes",
            model=None,
            frame_interval=payload.frame_interval,
            grid_size=payload.grid_size,
            keyframes=keyframes,
            frame_grids=frame_grids,
            summary="",
        )

    return analyze_frame_grids_with_glm(
        frame_grids,
        model=payload.glm_vision_model,
        prompt=payload.visual_prompt,
        frame_interval=payload.frame_interval,
        grid_size=payload.grid_size,
    )


def failure_response(
    *,
    platform: str,
    url: str,
    error: str,
    warnings: list[str],
    video_id: str | None = None,
    metadata: MetadataInfo | None = None,
) -> ExtractResponse:
    return ExtractResponse(
        ok=False,
        platform=platform,
        video_id=video_id,
        url=url,
        metadata=metadata,
        transcript=None,
        dify_payload=build_dify_payload(
            url=url,
            platform=platform,
            video_id=video_id,
            transcript=None,
            metadata=metadata,
            visual_analysis=None,
            max_chars_per_chunk=5000,
        ),
        warnings=warnings,
        error=error,
    )


def build_dify_payload(
    *,
    url: str,
    platform: str,
    video_id: str | None,
    transcript: TranscriptInfo | None,
    metadata: MetadataInfo | None,
    visual_analysis: VisualAnalysisInfo | None,
    max_chars_per_chunk: int,
) -> dict[str, object]:
    chunks = chunk_segments(transcript.segments, max_chars_per_chunk) if transcript else []

    return {
        "title": metadata.title if metadata else None,
        "url": url,
        "platform": platform,
        "video_id": video_id,
        "duration": metadata.duration if metadata else None,
        "subtitle_source": transcript.source if transcript else None,
        "subtitle_language": transcript.language if transcript else None,
        "subtitle_is_generated": transcript.is_generated if transcript else None,
        "timeline_text": transcript.timeline_text if transcript else "",
        "plain_text": transcript.plain_text if transcript else "",
        "segments": [segment.model_dump() for segment in transcript.segments] if transcript else [],
        "chunks": [chunk.model_dump() for chunk in chunks],
        "chapters": [chapter.model_dump() for chapter in metadata.chapters] if metadata else [],
        "visual_summary": visual_analysis.summary if visual_analysis else "",
        "keyframes": [frame.model_dump(exclude={"image_base64"}) for frame in visual_analysis.keyframes]
        if visual_analysis
        else [],
        "frame_grids": [grid.model_dump(exclude={"image_base64"}) for grid in visual_analysis.frame_grids]
        if visual_analysis
        else [],
    }
