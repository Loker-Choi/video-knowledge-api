from app.models import TranscriptSegment
from app.text_utils import chunk_segments, seconds_to_timestamp, segments_to_timeline_text


def test_seconds_to_timestamp():
    assert seconds_to_timestamp(0) == "00:00:00"
    assert seconds_to_timestamp(3661.2) == "01:01:01"


def test_segments_to_timeline_text():
    segments = [
        TranscriptSegment(index=0, start=0, end=1.5, duration=1.5, timestamp="00:00:00", text="hello"),
        TranscriptSegment(index=1, start=1.5, end=3, duration=1.5, timestamp="00:00:01", text="world"),
    ]

    assert segments_to_timeline_text(segments) == (
        "[00:00:00 - 00:00:01] hello\n"
        "[00:00:01 - 00:00:03] world"
    )


def test_chunk_segments_respects_max_chars():
    segments = [
        TranscriptSegment(index=0, start=0, end=1, duration=1, timestamp="00:00:00", text="a" * 40),
        TranscriptSegment(index=1, start=1, end=2, duration=1, timestamp="00:00:01", text="b" * 40),
        TranscriptSegment(index=2, start=2, end=3, duration=1, timestamp="00:00:02", text="c" * 40),
    ]

    chunks = chunk_segments(segments, 70)

    assert len(chunks) == 3
    assert all(len(chunk.text) <= 70 for chunk in chunks)
    assert chunks[0].start == 0
    assert chunks[-1].end == 3

