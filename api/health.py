from __future__ import annotations

import shutil

from fastapi import APIRouter

from config import get_settings
from services.cookies import cookie_service


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    bilibili_cookie_status = cookie_service().status("bilibili")
    return {
        "ok": True,
        "service": "video-knowledge-api",
        "version": settings.app_version,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "glm_configured": settings.glm_enabled,
        "bilibili_cookie_configured": bilibili_cookie_status["configured"],
        "bilibili_cookie_source": bilibili_cookie_status["source"],
        "defaults": {
            "fallback_to_glm_stt": True,
            "include_visual_analysis": True,
        },
        "ready": settings.glm_enabled and bool(bilibili_cookie_status["configured"]),
    }
