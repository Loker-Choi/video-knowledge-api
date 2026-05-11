from __future__ import annotations

import json
import re
from typing import Any

from .text_utils import strip_subtitle_markup


def parse_subtitle_text(content: str) -> list[dict[str, Any]]:
    stripped = content.lstrip("\ufeff \n\r\t")
    if not stripped:
        return []

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None

    if parsed is not None:
        json_segments = parse_json_subtitles(parsed)
        if json_segments:
            return json_segments

    if stripped.startswith("WEBVTT"):
        return parse_vtt_subtitles(stripped)

    return parse_srt_subtitles(stripped)


def parse_json_subtitles(parsed: Any) -> list[dict[str, Any]]:
    # Bilibili JSON subtitles usually contain body: [{from, to, content}, ...].
    if isinstance(parsed, dict) and isinstance(parsed.get("body"), list):
        segments: list[dict[str, Any]] = []
        for item in parsed["body"]:
            if not isinstance(item, dict):
                continue
            segments.append(
                {
                    "start": item.get("from", item.get("start", 0)),
                    "end": item.get("to", item.get("end")),
                    "text": item.get("content", item.get("text", "")),
                }
            )
        return segments

    # YouTube json3 subtitle payloads use events with millisecond offsets.
    if isinstance(parsed, dict) and isinstance(parsed.get("events"), list):
        segments = []
        for event in parsed["events"]:
            if not isinstance(event, dict):
                continue
            start_ms = event.get("tStartMs")
            duration_ms = event.get("dDurationMs")
            parts = event.get("segs") or []
            text = "".join(str(part.get("utf8") or "") for part in parts if isinstance(part, dict))
            if start_ms is None or not text.strip():
                continue
            start = float(start_ms) / 1000
            duration = float(duration_ms or 0) / 1000
            segments.append({"start": start, "duration": duration, "text": text})
        return segments

    if isinstance(parsed, list):
        segments = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            segments.append(
                {
                    "start": item.get("start", item.get("from", 0)),
                    "duration": item.get("duration"),
                    "end": item.get("end", item.get("to")),
                    "text": item.get("text", item.get("content", "")),
                }
            )
        return segments

    return []


def parse_vtt_subtitles(content: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n"))
    segments: list[dict[str, Any]] = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0] == "WEBVTT" or lines[0].startswith(("NOTE", "STYLE", "REGION")):
            continue

        time_line_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if time_line_index is None:
            continue

        start, end = parse_time_range(lines[time_line_index])
        text = strip_subtitle_markup(" ".join(lines[time_line_index + 1 :]))
        if text:
            segments.append({"start": start, "end": end, "text": text})

    return segments


def parse_srt_subtitles(content: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n"))
    segments: list[dict[str, Any]] = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        time_line_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if time_line_index is None:
            continue

        start, end = parse_time_range(lines[time_line_index])
        text = strip_subtitle_markup(" ".join(lines[time_line_index + 1 :]))
        if text:
            segments.append({"start": start, "end": end, "text": text})

    return segments


def parse_time_range(line: str) -> tuple[float, float]:
    left, right = line.split("-->", 1)
    right = right.strip().split(" ", 1)[0]
    return parse_timestamp(left.strip()), parse_timestamp(right.strip())


def parse_timestamp(value: str) -> float:
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    else:
        return 0.0
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

