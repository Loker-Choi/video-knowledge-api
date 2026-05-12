from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    app_name: str = "Video Knowledge API"
    app_version: str = "0.2.0"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)

    cors_allow_origins_raw: str = Field(default="*", alias="CORS_ALLOW_ORIGINS")
    request_timeout_seconds: int = Field(default=600, ge=1, le=3600)
    max_concurrent_tasks: int = Field(default=2, ge=1, le=8)
    yt_dlp_timeout_seconds: int = Field(default=120, ge=10, le=600)
    http_timeout_seconds: int = Field(default=20, ge=5, le=120)

    cookie_store_path: Path = Path(".secrets/cookies.json")
    ytdlp_cookies_file: Path | None = None
    cache_root: Path = Path(".cache/video-knowledge-api")
    keep_cache: bool = False

    glm_api_key: str | None = None
    zhipuai_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def glm_enabled(self) -> bool:
        return bool(self.glm_api_key or self.zhipuai_api_key)

    @property
    def cors_allow_origins(self) -> list[str]:
        origins = [item.strip() for item in self.cors_allow_origins_raw.split(",") if item.strip()]
        return origins or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
