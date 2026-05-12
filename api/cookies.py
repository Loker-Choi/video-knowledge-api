from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.cookies import SUPPORTED_COOKIE_PLATFORMS
from app.models import CookieUpdateRequest
from services.cookies import cookie_service


router = APIRouter(prefix="/v1/auth", tags=["cookies"])


@router.get("/cookies/{platform}")
def get_cookie_status(platform: str) -> dict[str, object]:
    try:
        return {"ok": True, **cookie_service().status(platform)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cookies")
def update_cookie(payload: CookieUpdateRequest) -> dict[str, object]:
    try:
        cookie_service().set(payload.platform, payload.cookie)
        return {"ok": True, **cookie_service().status(payload.platform)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/cookies/{platform}")
def delete_cookie(platform: str) -> dict[str, object]:
    if platform not in SUPPORTED_COOKIE_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported cookie platform: {platform}")
    cookie_service().delete(platform)
    return {"ok": True, **cookie_service().status(platform)}
