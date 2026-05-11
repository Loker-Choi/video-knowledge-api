from app.platforms import Platform, detect_platform, extract_youtube_video_id


def test_detect_youtube_hosts():
    assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == Platform.YOUTUBE
    assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == Platform.YOUTUBE
    assert detect_platform("https://m.youtube.com/shorts/dQw4w9WgXcQ") == Platform.YOUTUBE


def test_detect_bilibili_hosts():
    assert detect_platform("https://www.bilibili.com/video/BV1xx411c7mD/") == Platform.BILIBILI
    assert detect_platform("https://b23.tv/abcdef") == Platform.BILIBILI


def test_extract_youtube_video_id():
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_video_id("https://youtu.be/dQw4w9WgXcQ?t=1") == "dQw4w9WgXcQ"
    assert extract_youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_unknown_platform():
    assert detect_platform("https://example.com/video") == Platform.UNKNOWN

