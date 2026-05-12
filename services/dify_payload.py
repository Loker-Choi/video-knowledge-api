from __future__ import annotations

from app.models import MetadataInfo, TranscriptInfo, VisualAnalysisInfo
from app.text_utils import chunk_segments


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
