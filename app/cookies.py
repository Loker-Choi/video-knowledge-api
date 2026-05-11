from __future__ import annotations

import json
import tempfile
from pathlib import Path


SUPPORTED_COOKIE_PLATFORMS = {"bilibili", "youtube"}
REQUIRED_COOKIE_KEYS = {
    "bilibili": ["SESSDATA", "bili_jct", "DedeUserID"],
    "youtube": [],
}


class CookieStore:
    def __init__(self, filepath: str | Path = ".secrets/cookies.json"):
        self.path = Path(filepath)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def get(self, platform: str) -> str | None:
        data = self._read()
        value = data.get(platform, {}).get("cookie")
        return value if isinstance(value, str) and value.strip() else None

    def set(self, platform: str, cookie: str) -> None:
        validate_platform(platform)
        cookie = cookie.strip()
        if not cookie:
            raise ValueError("Cookie cannot be empty")
        data = self._read()
        data[platform] = {"cookie": cookie}
        self._write(data)

    def delete(self, platform: str) -> None:
        data = self._read()
        if platform in data:
            del data[platform]
            self._write(data)

    def status(self, platform: str) -> dict[str, object]:
        validate_platform(platform)
        cookie = self.get(platform)
        keys = parse_cookie_keys(cookie or "")
        required = REQUIRED_COOKIE_KEYS.get(platform, [])
        present = [key for key in required if key in keys]
        missing = [key for key in required if key not in keys]
        return {
            "platform": platform,
            "configured": bool(cookie),
            "cookie_count": len(keys),
            "required_keys_present": present,
            "required_keys_missing": missing,
        }


def validate_platform(platform: str) -> None:
    if platform not in SUPPORTED_COOKIE_PLATFORMS:
        raise ValueError(f"Unsupported cookie platform: {platform}")


def parse_cookie_keys(cookie: str) -> set[str]:
    keys: set[str] = set()
    for pair in cookie.split(";"):
        if "=" not in pair:
            continue
        key, _ = pair.split("=", 1)
        key = key.strip()
        if key:
            keys.add(key)
    return keys


def cookie_to_netscape_lines(platform: str, cookie: str) -> list[str]:
    domain = ".bilibili.com" if platform == "bilibili" else ".youtube.com"
    secure = "FALSE"
    lines = ["# Netscape HTTP Cookie File\n"]
    for pair in cookie.split(";"):
        if "=" not in pair:
            continue
        key, value = pair.strip().split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        lines.append(f"{domain}\tTRUE\t/\t{secure}\t0\t{key}\t{value}\n")
    return lines


def write_temp_cookiefile(platform: str, cookie: str) -> str:
    validate_platform(platform)
    file = tempfile.NamedTemporaryFile(
        mode="w",
        prefix="video-analysis-api-",
        suffix=".cookies.txt",
        delete=False,
        encoding="utf-8",
    )
    try:
        file.writelines(cookie_to_netscape_lines(platform, cookie))
        return file.name
    finally:
        file.close()
