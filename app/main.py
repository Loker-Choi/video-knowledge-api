from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
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
from .models import DEFAULT_LANGUAGES, CookieUpdateRequest, ExtractRequest, ExtractResponse, MetadataInfo, TranscriptInfo
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


def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("VIDEO_API_TOKEN")
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token")


def require_configured_token(authorization: Annotated[str | None, Header()] = None) -> None:
    if not os.getenv("VIDEO_API_TOKEN"):
        raise HTTPException(status_code=403, detail="Set VIDEO_API_TOKEN before using cookie management APIs")
    require_token(authorization)


@app.get("/health")
def health() -> dict[str, bool | str]:
    return {"ok": True, "service": "video-analysis-api"}


@app.get("/v1/auth/cookies/{platform}", dependencies=[Depends(require_configured_token)])
def get_cookie_status(platform: str) -> dict[str, object]:
    try:
        return {"ok": True, **CookieStore().status(platform)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/auth/cookies", dependencies=[Depends(require_configured_token)])
def update_cookie(payload: CookieUpdateRequest) -> dict[str, object]:
    try:
        CookieStore().set(payload.platform, payload.cookie)
        return {"ok": True, **CookieStore().status(payload.platform)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/v1/auth/cookies/{platform}", dependencies=[Depends(require_configured_token)])
def delete_cookie(platform: str) -> dict[str, object]:
    if platform not in SUPPORTED_COOKIE_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported cookie platform: {platform}")
    CookieStore().delete(platform)
    return {"ok": True, **CookieStore().status(platform)}


@app.post("/v1/video/extract", response_model=ExtractResponse, dependencies=[Depends(require_token)])
def extract_video(payload: ExtractRequest) -> ExtractResponse:
    return extract_video_payload(payload)


@app.get("/v1/video/extract", response_model=ExtractResponse, dependencies=[Depends(require_token)])
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
    video_id: str | None = None

    if payload.include_keyframes:
        warnings.append("include_keyframes is reserved for v2 and ignored in v1.")

    if platform == Platform.UNKNOWN:
        return failure_response(
            platform=platform.value,
            url=url,
            error="UNSUPPORTED_PLATFORM",
            warnings=["Only Bilibili and YouTube URLs are supported."],
        )

    try:
        if platform == Platform.YOUTUBE:
            video_id, transcript = fetch_youtube_transcript(
                url=url,
                languages=payload.languages,
                preserve_formatting=payload.preserve_formatting,
            )
            if payload.include_metadata:
                metadata = try_fetch_metadata(url, warnings, platform.value)
        else:
            cookie = CookieStore().get("bilibili")
            try:
                video_id, transcript = fetch_bilibili_player_transcript(url, cookie)
                metadata = try_fetch_metadata(url, warnings, platform.value) if payload.include_metadata else None
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
            if payload.include_metadata and metadata is None:
                metadata = try_fetch_metadata(url, warnings, platform.value)
            return failure_response(
                platform=platform.value,
                url=url,
                video_id=video_id,
                metadata=metadata,
                error="NO_TRANSCRIPT",
                warnings=warnings or ["No usable subtitle/timeline track found."],
            )
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

    return ExtractResponse(
        ok=True,
        platform=platform.value,
        video_id=video_id,
        url=url,
        metadata=metadata,
        transcript=transcript,
        dify_payload=build_dify_payload(
            url=url,
            platform=platform.value,
            video_id=video_id,
            transcript=transcript,
            metadata=metadata,
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
    }
