from __future__ import annotations

import re
from html import unescape

from .models import TextChunk, TranscriptSegment


def seconds_to_timestamp(seconds: float | int | None) -> str:
    value = max(float(seconds or 0), 0.0)
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    secs = int(value % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def strip_subtitle_markup(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\\.*?\}", "", text)
    return normalize_text(text)


def segments_to_plain_text(segments: list[TranscriptSegment]) -> str:
    return "\n".join(segment.text for segment in segments)


def segments_to_timeline_text(segments: list[TranscriptSegment]) -> str:
    lines: list[str] = []
    for segment in segments:
        end = f" - {seconds_to_timestamp(segment.end)}" if segment.end is not None else ""
        lines.append(f"[{segment.timestamp}{end}] {segment.text}")
    return "\n".join(lines)


def chunk_segments(segments: list[TranscriptSegment], max_chars: int) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    current_lines: list[str] = []
    current_start: float | None = None
    current_end: float | None = None

    def flush() -> None:
        nonlocal current_lines, current_start, current_end
        text = "\n".join(current_lines).strip()
        if text:
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    start=current_start,
                    end=current_end,
                    text=text,
                )
            )
        current_lines = []
        current_start = None
        current_end = None

    for segment in segments:
        line_end = f" - {seconds_to_timestamp(segment.end)}" if segment.end is not None else ""
        line = f"[{segment.timestamp}{line_end}] {segment.text}"

        if current_lines and len("\n".join(current_lines)) + 1 + len(line) > max_chars:
            flush()

        if current_start is None:
            current_start = segment.start
        current_end = segment.end if segment.end is not None else segment.start

        if len(line) > max_chars:
            if current_lines:
                flush()
            for offset in range(0, len(line), max_chars):
                chunks.append(
                    TextChunk(
                        index=len(chunks),
                        start=segment.start,
                        end=segment.end,
                        text=line[offset : offset + max_chars],
                    )
                )
            continue

        current_lines.append(line)

    flush()
    return chunks

