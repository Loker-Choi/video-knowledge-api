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
from config import get_settings
from services.cookies import cookie_service
from services.dify_payload import build_dify_payload
from services.visual import fetch_glm_stt_transcript, fetch_visual_analysis
from utils.stage_log import log_stage


def extract_video_payload(payload: ExtractRequest) -> ExtractResponse:
    payload = payload.model_copy(update={"fallback_to_glm_stt": True, "include_visual_analysis": True})
    url = str(payload.url)
    platform = detect_platform(url)
    log_stage("platform_detected", platform=platform.value)
    warnings: list[str] = []
    transcript: TranscriptInfo | None = None
    metadata: MetadataInfo | None = None
    visual_analysis: VisualAnalysisInfo | None = None
    video_id: str | None = None

    if platform == Platform.UNKNOWN:
        log_stage("request_failed", error="UNSUPPORTED_PLATFORM")
        return failure_response(
            platform=platform.value,
            url=url,
            error="UNSUPPORTED_PLATFORM",
            warnings=["Only Bilibili and YouTube URLs are supported."],
            max_chars_per_chunk=payload.max_chars_per_chunk,
        )

    settings = get_settings()
    if not settings.glm_enabled:
        log_stage("config_check_failed", error="MISSING_GLM_API_KEY")
        return failure_response(
            platform=platform.value,
            url=url,
            error="MISSING_GLM_API_KEY",
            warnings=["请在 .env 中配置 GLM_API_KEY，然后重启服务。"],
            max_chars_per_chunk=payload.max_chars_per_chunk,
        )

    if platform == Platform.BILIBILI and not cookie_service().get("bilibili"):
        log_stage("config_check_failed", error="MISSING_BILIBILI_COOKIE")
        return failure_response(
            platform=platform.value,
            url=url,
            error="MISSING_BILIBILI_COOKIE",
            warnings=["请在 .env 中配置 BILIBILI_COOKIE，然后重启服务。"],
            max_chars_per_chunk=payload.max_chars_per_chunk,
        )

    try:
        if payload.include_metadata or payload.include_visual_analysis or payload.include_keyframes:
            log_stage("metadata_start")
            metadata = try_fetch_metadata(url, warnings, platform.value)
            log_stage("metadata_done", found=metadata is not None, title=metadata.title if metadata else None)

        if platform == Platform.YOUTUBE:
            log_stage("youtube_transcript_start")
            video_id, transcript = fetch_youtube_transcript(
                url=url,
                languages=payload.languages,
                preserve_formatting=payload.preserve_formatting,
            )
            log_stage("youtube_transcript_done", video_id=video_id, segments=len(transcript.segments))
            if payload.include_metadata and metadata is None:
                log_stage("metadata_start")
                metadata = try_fetch_metadata(url, warnings, platform.value)
                log_stage("metadata_done", found=metadata is not None, title=metadata.title if metadata else None)
        else:
            cookie = cookie_service().get("bilibili")
            try:
                log_stage("bilibili_transcript_start")
                video_id, transcript = fetch_bilibili_player_transcript(url, cookie)
                log_stage("bilibili_transcript_done", video_id=video_id, segments=len(transcript.segments))
                if payload.include_metadata and metadata is None:
                    log_stage("metadata_start")
                    metadata = try_fetch_metadata(url, warnings, platform.value)
                    log_stage("metadata_done", found=metadata is not None, title=metadata.title if metadata else None)
                warnings.append("Used Bilibili player API subtitle track.")
            except TranscriptNotFound as player_exc:
                log_stage("bilibili_transcript_failed", message=str(player_exc))
                warnings.append(str(player_exc))
                log_stage("ytdlp_subtitle_start")
                video_id, metadata, transcript = fetch_ytdlp_subtitle_transcript(
                    url,
                    payload.languages,
                    platform=platform.value,
                )
                log_stage("ytdlp_subtitle_done", video_id=video_id, segments=len(transcript.segments))

    except TranscriptNotFound as exc:
        log_stage("transcript_not_found", message=str(exc))
        warnings.append(str(exc))
        if platform == Platform.YOUTUBE:
            try:
                log_stage("ytdlp_subtitle_start")
                video_id, metadata, transcript = fetch_ytdlp_subtitle_transcript(url, payload.languages, platform.value)
                log_stage("ytdlp_subtitle_done", video_id=video_id, segments=len(transcript.segments))
                warnings.append("Fell back from youtube-transcript-api to yt-dlp subtitle tracks.")
            except Exception as fallback_exc:
                log_stage("ytdlp_subtitle_failed", message=str(fallback_exc))
                warnings.append(f"yt-dlp subtitle fallback failed: {fallback_exc}")

        if transcript is None:
            if metadata is None:
                log_stage("metadata_start")
                metadata = try_fetch_metadata(url, warnings, platform.value)
                log_stage("metadata_done", found=metadata is not None, title=metadata.title if metadata else None)
            if payload.fallback_to_glm_stt:
                try:
                    log_stage("glm_stt_start")
                    transcript = fetch_glm_stt_transcript(url, platform.value, payload, warnings)
                    log_stage("glm_stt_done", segments=len(transcript.segments))
                    warnings.append("Used GLM-ASR because no usable platform subtitle was found.")
                except Exception as stt_exc:
                    log_stage("glm_stt_failed", message=str(stt_exc))
                    warnings.append(f"GLM STT fallback failed: {stt_exc}")
            if transcript is None and not (payload.include_visual_analysis or payload.include_keyframes):
                log_stage("request_failed", error="NO_TRANSCRIPT")
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
        log_stage("request_failed", error=str(exc))
        return failure_response(
            platform=platform.value,
            url=url,
            error=str(exc),
            warnings=warnings,
            max_chars_per_chunk=payload.max_chars_per_chunk,
        )
    except Exception as exc:
        log_stage("request_failed", error="EXTRACTION_FAILED", message=str(exc))
        return failure_response(
            platform=platform.value,
            url=url,
            error=f"EXTRACTION_FAILED: {exc}",
            warnings=warnings,
            max_chars_per_chunk=payload.max_chars_per_chunk,
        )

    if payload.include_visual_analysis or payload.include_keyframes:
        try:
            log_stage("visual_analysis_start")
            visual_analysis = fetch_visual_analysis(url, platform.value, payload, warnings)
            log_stage("visual_analysis_done", grids=len(visual_analysis.frame_grids), keyframes=len(visual_analysis.keyframes))
        except Exception as visual_exc:
            log_stage("visual_analysis_failed", message=str(visual_exc))
            warnings.append(f"Visual analysis failed: {visual_exc}")

    response = ExtractResponse(
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
    log_stage("response_built", ok=response.ok, warnings=len(response.warnings))
    return response


def try_fetch_metadata(url: str, warnings: list[str], platform: str | None = None) -> MetadataInfo | None:
    try:
        return metadata_from_ytdlp(fetch_ytdlp_info(url, platform))
    except Exception as exc:
        log_stage("metadata_failed", message=str(exc))
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
