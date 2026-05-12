from __future__ import annotations

from app.bilibili import fetch_bilibili_player_transcript
from app.extractors import (
    ExtractionError,
    TranscriptNotFound,
    fetch_youtube_transcript,
    fetch_ytdlp_info,
    fetch_ytdlp_subtitle_transcript,
    metadata_from_ytdlp,
)
from app.models import ExtractRequest, ExtractResponse, MetadataInfo, TranscriptInfo, VisualAnalysisInfo
from app.platforms import Platform, detect_platform
from services.cookies import cookie_service
from services.dify_payload import build_dify_payload
from services.visual import fetch_glm_stt_transcript, fetch_visual_analysis


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
            max_chars_per_chunk=payload.max_chars_per_chunk,
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
            cookie = cookie_service().get("bilibili")
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
                    max_chars_per_chunk=payload.max_chars_per_chunk,
                )
            if transcript is None:
                warnings.append("No transcript was found; continuing with visual extraction.")
    except ExtractionError as exc:
        return failure_response(
            platform=platform.value,
            url=url,
            error=str(exc),
            warnings=warnings,
            max_chars_per_chunk=payload.max_chars_per_chunk,
        )
    except Exception as exc:
        return failure_response(
            platform=platform.value,
            url=url,
            error=f"EXTRACTION_FAILED: {exc}",
            warnings=warnings,
            max_chars_per_chunk=payload.max_chars_per_chunk,
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


def failure_response(
    *,
    platform: str,
    url: str,
    error: str,
    warnings: list[str],
    max_chars_per_chunk: int,
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
        visual_analysis=None,
        dify_payload=build_dify_payload(
            url=url,
            platform=platform,
            video_id=video_id,
            transcript=None,
            metadata=metadata,
            visual_analysis=None,
            max_chars_per_chunk=max_chars_per_chunk,
        ),
        warnings=warnings,
        error=error,
    )
