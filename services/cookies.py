from __future__ import annotations

from app.cookies import CookieStore
from config import get_settings


def cookie_service() -> CookieStore:
    return CookieStore(get_settings().cookie_store_path)
