from app.subtitles import parse_subtitle_text


def test_parse_bilibili_json_subtitles():
    payload = """
    {
      "body": [
        {"from": 0.0, "to": 2.5, "content": "你好"},
        {"from": 2.5, "to": 5.0, "content": "欢迎学习"}
      ]
    }
    """

    segments = parse_subtitle_text(payload)

    assert segments == [
        {"start": 0.0, "end": 2.5, "text": "你好"},
        {"start": 2.5, "end": 5.0, "text": "欢迎学习"},
    ]


def test_parse_youtube_json3_subtitles():
    payload = """
    {
      "events": [
        {"tStartMs": 1000, "dDurationMs": 1500, "segs": [{"utf8": "hello "}, {"utf8": "world"}]},
        {"tStartMs": 3000, "dDurationMs": 1000, "segs": [{"utf8": "\\n"}]}
      ]
    }
    """

    segments = parse_subtitle_text(payload)

    assert segments == [{"start": 1.0, "duration": 1.5, "text": "hello world"}]


def test_parse_vtt_subtitles():
    payload = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c>First line</c>

00:00:03.000 --> 00:00:05.500
Second line
"""

    segments = parse_subtitle_text(payload)

    assert segments == [
        {"start": 1.0, "end": 3.0, "text": "First line"},
        {"start": 3.0, "end": 5.5, "text": "Second line"},
    ]


def test_parse_srt_subtitles():
    payload = """1
00:00:01,000 --> 00:00:03,000
First line

2
00:00:03,000 --> 00:00:05,500
Second line
"""

    segments = parse_subtitle_text(payload)

    assert segments == [
        {"start": 1.0, "end": 3.0, "text": "First line"},
        {"start": 3.0, "end": 5.5, "text": "Second line"},
    ]

