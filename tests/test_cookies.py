from pathlib import Path

from fastapi.testclient import TestClient

from app.cookies import CookieStore, cookie_to_netscape_lines, parse_cookie_keys, write_temp_cookiefile
from app.extractors import cleanup_temp_cookiefile
from app.main import app


def test_parse_cookie_keys():
    assert parse_cookie_keys("SESSDATA=abc; bili_jct=def; DedeUserID=123") == {
        "SESSDATA",
        "bili_jct",
        "DedeUserID",
    }


def test_cookie_store_status(tmp_path: Path):
    store = CookieStore(tmp_path / "cookies.json")

    store.set("bilibili", "SESSDATA=abc; bili_jct=def")
    status = store.status("bilibili")

    assert status["configured"] is True
    assert status["required_keys_present"] == ["SESSDATA", "bili_jct"]
    assert status["required_keys_missing"] == ["DedeUserID"]


def test_cookie_to_netscape_lines():
    lines = cookie_to_netscape_lines("bilibili", "SESSDATA=abc; bili_jct=def")

    assert lines[0].startswith("# Netscape")
    assert ".bilibili.com\tTRUE\t/\tFALSE\t0\tSESSDATA\tabc\n" in lines


def test_cleanup_only_removes_owned_temp_cookiefile(tmp_path: Path):
    owned = Path(write_temp_cookiefile("bilibili", "SESSDATA=abc"))
    user_file = tmp_path / "my.cookies.txt"
    user_file.write_text("cookie", encoding="utf-8")

    cleanup_temp_cookiefile(str(owned))
    cleanup_temp_cookiefile(str(user_file))

    assert not owned.exists()
    assert user_file.exists()


def test_cookie_management_requires_configured_video_api_token(monkeypatch):
    monkeypatch.delenv("VIDEO_API_TOKEN", raising=False)
    client = TestClient(app)

    response = client.get("/v1/auth/cookies/bilibili")

    assert response.status_code == 403


def test_cookie_management_status_with_token(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_API_TOKEN", "secret")
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/v1/auth/cookies",
        headers={"Authorization": "Bearer secret"},
        json={"platform": "bilibili", "cookie": "SESSDATA=abc; bili_jct=def; DedeUserID=123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["configured"] is True
    assert body["required_keys_missing"] == []
