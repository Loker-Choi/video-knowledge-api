from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Any

from config import get_settings

from .extractors import TranscriptNotFound, build_transcript
from .models import TranscriptInfo


BILIBILI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def extract_bvid(url_or_bvid: str) -> str | None:
    match = re.search(r"(BV[0-9A-Za-z]+)", url_or_bvid)
    return match.group(1) if match else None


def fetch_bilibili_player_transcript(url: str, cookie: str | None = None) -> tuple[str, TranscriptInfo]:
    bvid = extract_bvid(url)
    if not bvid:
        raise TranscriptNotFound("Could not extract Bilibili BV id from URL")

    cid = fetch_cid(bvid, cookie)
    subtitles = list_subtitles(bvid, cid, cookie)
    if not subtitles:
        raise TranscriptNotFound("No Bilibili player subtitle tracks found. AI subtitles may require SESSDATA cookie.")

    track = pick_subtitle_track(subtitles)
    subtitle_url = track.get("subtitle_url")
    if not subtitle_url:
        raise TranscriptNotFound("Bilibili subtitle track exists but has no subtitle_url. Login cookie may be required.")

    body = fetch_subtitle_body(str(subtitle_url), cookie)
    if not body:
        raise TranscriptNotFound("Bilibili subtitle URL returned no timed text.")

    language = str(track.get("lan") or "zh")
    is_generated = bool(track.get("ai_type"))
    return bvid, build_transcript(
        source="bilibili_player_api",
        raw_segments=[
            {
                "start": item.get("from", 0),
                "end": item.get("to"),
                "text": item.get("content", ""),
            }
            for item in body
            if isinstance(item, dict)
        ],
        language=language,
        is_generated=is_generated,
    )


def fetch_cid(bvid: str, cookie: str | None = None) -> int:
    data = http_get_json(
        "https://api.bilibili.com/x/web-interface/view",
        params={"bvid": bvid},
        cookie=cookie,
    )
    if data.get("code") != 0:
        raise TranscriptNotFound(f"Bilibili view API failed: {data.get('message') or data.get('code')}")
    cid = data.get("data", {}).get("cid")
    if not cid:
        raise TranscriptNotFound("Bilibili view API did not return cid")
    return int(cid)


def list_subtitles(bvid: str, cid: int, cookie: str | None = None) -> list[dict[str, Any]]:
    data = http_get_json(
        "https://api.bilibili.com/x/player/wbi/v2",
        params={"bvid": bvid, "cid": cid},
        cookie=cookie,
    )
    if data.get("code") != 0:
        raise TranscriptNotFound(f"Bilibili player API failed: {data.get('message') or data.get('code')}")
    subtitles = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
    return [item for item in subtitles if isinstance(item, dict)]


def pick_subtitle_track(subtitles: list[dict[str, Any]]) -> dict[str, Any]:
    def is_zh(track: dict[str, Any]) -> bool:
        language = str(track.get("lan") or "").lower()
        return language.startswith("zh") or language == "ai-zh"

    for track in subtitles:
        if is_zh(track) and not track.get("ai_type"):
            return track
    for track in subtitles:
        if is_zh(track):
            return track
    return subtitles[0]


def fetch_subtitle_body(subtitle_url: str, cookie: str | None = None) -> list[dict[str, Any]]:
    data = http_get_json(normalize_url(subtitle_url), cookie=cookie)
    body = data.get("body") or []
    return [item for item in body if isinstance(item, dict)]


def http_get_json(url: str, params: dict[str, object] | None = None, cookie: str | None = None) -> dict[str, Any]:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    headers = {
        "User-Agent": BILIBILI_UA,
        "Referer": "https://www.bilibili.com",
    }
    if cookie:
        headers["Cookie"] = cookie
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=get_settings().http_timeout_seconds) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        payload = response.read().decode(charset, errors="replace")
    import json

    parsed = json.loads(payload)
    return parsed if isinstance(parsed, dict) else {}


def normalize_url(url: str) -> str:
    return f"https:{url}" if url.startswith("//") else url
