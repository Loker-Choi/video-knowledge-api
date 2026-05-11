from __future__ import annotations

import re
from enum import StrEnum
from urllib.parse import parse_qs, urlparse


class Platform(StrEnum):
    YOUTUBE = "youtube"
    BILIBILI = "bilibili"
    UNKNOWN = "unknown"


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def detect_platform(url: str) -> Platform:
    host = _host(url)

    if host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}:
        return Platform.YOUTUBE
    if host.endswith(".youtube.com"):
        return Platform.YOUTUBE

    if host in {"bilibili.com", "m.bilibili.com", "b23.tv"}:
        return Platform.BILIBILI
    if host.endswith(".bilibili.com"):
        return Platform.BILIBILI

    return Platform.UNKNOWN


def extract_youtube_video_id(url_or_id: str) -> str | None:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id

    parsed = urlparse(url_or_id)
    host = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host == "youtu.be" and path_parts:
        candidate = path_parts[0]
        return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None

    if host.endswith("youtube.com"):
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", query_id):
            return query_id

        if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
            candidate = path_parts[1]
            return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None

    return None

