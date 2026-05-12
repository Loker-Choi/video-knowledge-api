from __future__ import annotations

import os
from pathlib import Path
import tempfile
import urllib.request
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp import YoutubeDL

from .cookies import CookieStore, write_temp_cookiefile
from .models import ChapterInfo, MetadataInfo, TranscriptInfo, TranscriptSegment
from .platforms import extract_youtube_video_id
from .subtitles import parse_subtitle_text
from .text_utils import normalize_text, seconds_to_timestamp, segments_to_plain_text, segments_to_timeline_text
from config import get_settings


class ExtractionError(RuntimeError):
    pass


class TranscriptNotFound(ExtractionError):
    pass


def build_transcript(
    *,
    source: str,
    raw_segments: list[dict[str, Any]],
    language: str | None = None,
    language_name: str | None = None,
    is_generated: bool | None = None,
) -> TranscriptInfo:
    segments: list[TranscriptSegment] = []

    for item in raw_segments:
        text = normalize_text(str(item.get("text") or item.get("content") or ""))
        if not text:
            continue

        start = float(item.get("start") if item.get("start") is not None else item.get("from") or 0)
        duration = item.get("duration")
        end = item.get("end")

        if end is None and item.get("to") is not None:
            end = item.get("to")
        if duration is None and end is not None:
            duration = max(float(end) - start, 0)
        if end is None and duration is not None:
            end = start + float(duration)

        segments.append(
            TranscriptSegment(
                index=len(segments),
                start=start,
                end=float(end) if end is not None else None,
                duration=float(duration) if duration is not None else None,
                timestamp=seconds_to_timestamp(start),
                text=text,
            )
        )

    return TranscriptInfo(
        source=source,
        language=language,
        language_name=language_name,
        is_generated=is_generated,
        has_timeline=bool(segments),
        segments=segments,
        plain_text=segments_to_plain_text(segments),
        timeline_text=segments_to_timeline_text(segments),
    )


def ytdlp_options(platform: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": settings.yt_dlp_timeout_seconds,
    }
    if settings.ytdlp_cookies_file:
        options["cookiefile"] = str(settings.ytdlp_cookies_file)
    elif platform:
        cookie = CookieStore(settings.cookie_store_path).get(platform)
        if cookie:
            options["cookiefile"] = write_temp_cookiefile(platform, cookie)
    return options


def fetch_ytdlp_info(url: str, platform: str | None = None) -> dict[str, Any]:
    options = ytdlp_options(platform)
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict):
            raise ExtractionError("yt-dlp did not return a video info dictionary")
        return info
    finally:
        cleanup_temp_cookiefile(options.get("cookiefile"))


def metadata_from_ytdlp(info: dict[str, Any]) -> MetadataInfo:
    chapters = [
        ChapterInfo(
            start=chapter.get("start_time"),
            end=chapter.get("end_time"),
            title=str(chapter.get("title") or ""),
        )
        for chapter in info.get("chapters") or []
        if isinstance(chapter, dict) and chapter.get("title")
    ]

    raw = {
        key: info.get(key)
        for key in [
            "id",
            "display_id",
            "title",
            "duration",
            "uploader",
            "channel",
            "webpage_url",
            "thumbnail",
            "subtitles",
            "automatic_captions",
        ]
        if key in info
    }

    return MetadataInfo(
        title=info.get("title"),
        duration=info.get("duration"),
        uploader=info.get("uploader") or info.get("channel"),
        webpage_url=info.get("webpage_url"),
        thumbnail=info.get("thumbnail"),
        chapters=chapters,
        raw=raw,
    )


def fetch_youtube_transcript(
    url: str,
    languages: list[str],
    preserve_formatting: bool = False,
) -> tuple[str, TranscriptInfo]:
    video_id = extract_youtube_video_id(url)
    if not video_id:
        raise ExtractionError("Could not extract a YouTube video id from the URL")

    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)
        transcript = None

        try:
            transcript = transcript_list.find_manually_created_transcript(languages)
        except Exception:
            pass

        if transcript is None:
            try:
                transcript = transcript_list.find_transcript(languages)
            except Exception:
                pass

        if transcript is None:
            transcripts = list(transcript_list)
            if not transcripts:
                raise TranscriptNotFound("No YouTube transcript is available")
            manual = [item for item in transcripts if not getattr(item, "is_generated", False)]
            transcript = (manual or transcripts)[0]

        fetched = transcript.fetch(preserve_formatting=preserve_formatting)
        raw_segments = fetched.to_raw_data()

        return video_id, build_transcript(
            source="youtube_transcript_api",
            raw_segments=raw_segments,
            language=getattr(transcript, "language_code", None),
            language_name=getattr(transcript, "language", None),
            is_generated=getattr(transcript, "is_generated", None),
        )
    except TranscriptNotFound:
        raise
    except Exception as exc:
        raise TranscriptNotFound(f"YouTube transcript unavailable: {exc}") from exc


def fetch_ytdlp_subtitle_transcript(
    url: str,
    languages: list[str],
    platform: str | None = None,
) -> tuple[str | None, MetadataInfo, TranscriptInfo]:
    info = fetch_ytdlp_info(url, platform)
    metadata = metadata_from_ytdlp(info)
    chosen = choose_subtitle_track(info, languages)
    if not chosen:
        raise TranscriptNotFound("No usable subtitle/timeline track found")

    language, track, is_generated = chosen
    subtitle_text = fetch_url_text(str(track["url"]))
    raw_segments = parse_subtitle_text(subtitle_text)
    if not raw_segments:
        raise TranscriptNotFound("Subtitle track was found but no timed text could be parsed")

    video_id = info.get("id") or info.get("display_id")
    return (
        str(video_id) if video_id else None,
        metadata,
        build_transcript(
            source="yt_dlp_automatic_captions" if is_generated else "yt_dlp_subtitles",
            raw_segments=raw_segments,
            language=language,
            is_generated=is_generated,
        ),
    )


def choose_subtitle_track(info: dict[str, Any], languages: list[str]) -> tuple[str, dict[str, Any], bool] | None:
    for source_key, is_generated in [("subtitles", False), ("automatic_captions", True)]:
        tracks_by_language = info.get(source_key) or {}
        if not isinstance(tracks_by_language, dict):
            continue

        for language in preferred_language_keys(tracks_by_language, languages):
            tracks = tracks_by_language.get(language) or []
            if not isinstance(tracks, list):
                continue
            sorted_tracks = sorted(
                [track for track in tracks if isinstance(track, dict) and track.get("url")],
                key=lambda track: subtitle_track_score(str(track.get("ext") or ""), str(track.get("url") or "")),
                reverse=True,
            )
            if sorted_tracks:
                return language, sorted_tracks[0], is_generated

    return None


def preferred_language_keys(available: dict[str, Any], languages: list[str]) -> list[str]:
    keys = list(available.keys())
    normalized = {key.lower(): key for key in keys}
    selected: list[str] = []

    for language in languages:
        lower = language.lower()
        candidates = [lower, lower.replace("_", "-"), lower.split("-")[0]]
        for candidate in candidates:
            key = normalized.get(candidate)
            if key and key not in selected:
                selected.append(key)

    selected.extend(key for key in keys if key not in selected)
    return selected


def subtitle_track_score(ext: str, url: str) -> int:
    ext = ext.lower()
    url = url.lower()
    if ext in {"json", "json3"} or ".json" in url:
        return 5
    if ext == "vtt" or ".vtt" in url:
        return 4
    if ext == "srt" or ".srt" in url:
        return 3
    return 1


def fetch_url_text(url: str) -> str:
    if url.startswith("//"):
        url = f"https:{url}"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 video-analysis-api"},
    )
    with urllib.request.urlopen(request, timeout=get_settings().http_timeout_seconds) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def cleanup_temp_cookiefile(cookiefile: object) -> None:
    if not isinstance(cookiefile, str):
        return
    temp_root = Path(tempfile.gettempdir()).resolve()
    basename = os.path.basename(cookiefile)
    resolved_cookiefile = Path(cookiefile).resolve()
    try:
        resolved_cookiefile.relative_to(temp_root)
    except ValueError:
        return
    if not basename.startswith("video-analysis-api-") or not basename.endswith(".cookies.txt"):
        return
    try:
        os.remove(cookiefile)
    except OSError:
        pass
