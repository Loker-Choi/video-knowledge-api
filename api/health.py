from __future__ import annotations

import shutil

from fastapi import APIRouter

from config import get_settings
from services.cookies import cookie_service


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "ok": True,
        "service": "video-knowledge-api",
        "version": settings.app_version,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "glm_configured": settings.glm_enabled,
        "bilibili_cookie_configured": cookie_service().status("bilibili")["configured"],
    }
