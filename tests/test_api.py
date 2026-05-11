from fastapi.testclient import TestClient

from app.extractors import build_transcript
from app.main import app, build_dify_payload


def test_health():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "service": "video-analysis-api"}


def test_unsupported_platform_returns_ok_false():
    client = TestClient(app)

    response = client.post("/v1/video/extract", json={"url": "https://example.com/video"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "UNSUPPORTED_PLATFORM"


def test_auth_rejects_invalid_token(monkeypatch):
    monkeypatch.setenv("VIDEO_API_TOKEN", "secret")
    client = TestClient(app)

    response = client.post("/v1/video/extract", json={"url": "https://example.com/video"})

    assert response.status_code == 401


def test_auth_accepts_valid_token(monkeypatch):
    monkeypatch.setenv("VIDEO_API_TOKEN", "secret")
    client = TestClient(app)

    response = client.post(
        "/v1/video/extract",
        headers={"Authorization": "Bearer secret"},
        json={"url": "https://example.com/video"},
    )

    assert response.status_code == 200
    assert response.json()["error"] == "UNSUPPORTED_PLATFORM"


def test_build_dify_payload_includes_chunks():
    transcript = build_transcript(
        source="unit_test",
        language="en",
        raw_segments=[
            {"start": 0, "duration": 1, "text": "hello"},
            {"start": 1, "duration": 1, "text": "world"},
        ],
    )

    payload = build_dify_payload(
        url="https://youtu.be/dQw4w9WgXcQ",
        platform="youtube",
        video_id="dQw4w9WgXcQ",
        transcript=transcript,
        metadata=None,
        max_chars_per_chunk=500,
    )

    assert payload["timeline_text"] == "[00:00:00 - 00:00:01] hello\n[00:00:01 - 00:00:02] world"
    assert payload["plain_text"] == "hello\nworld"
    assert payload["chunks"][0]["text"].startswith("[00:00:00")

