from __future__ import annotations

from app.cookies import CookieStore, configured_cookie_store


def cookie_service() -> CookieStore:
    return configured_cookie_store()
