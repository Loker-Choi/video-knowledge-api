from app.bilibili import extract_bvid, pick_subtitle_track


def test_extract_bvid():
    assert extract_bvid("https://www.bilibili.com/video/BV1gCoYBHEYQ/") == "BV1gCoYBHEYQ"
    assert extract_bvid("BV1gCoYBHEYQ") == "BV1gCoYBHEYQ"


def test_pick_subtitle_track_prefers_manual_chinese():
    tracks = [
        {"lan": "en", "subtitle_url": "//example.com/en.json"},
        {"lan": "ai-zh", "ai_type": 1, "subtitle_url": "//example.com/ai.json"},
        {"lan": "zh-CN", "ai_type": 0, "subtitle_url": "//example.com/manual.json"},
    ]

    assert pick_subtitle_track(tracks)["subtitle_url"] == "//example.com/manual.json"


def test_pick_subtitle_track_falls_back_to_ai_chinese():
    tracks = [
        {"lan": "en", "subtitle_url": "//example.com/en.json"},
        {"lan": "ai-zh", "ai_type": 1, "subtitle_url": "//example.com/ai.json"},
    ]

    assert pick_subtitle_track(tracks)["subtitle_url"] == "//example.com/ai.json"

