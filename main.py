from __future__ import annotations

import shutil

import uvicorn

from config import get_settings
from core import create_app
from services.cookies import cookie_service


app = create_app()


def print_startup_status() -> None:
    settings = get_settings()
    bilibili_cookie = cookie_service().status("bilibili")
    print("Video Knowledge API")
    print(f"- URL: http://{settings.host}:{settings.port}")
    print(f"- OpenAPI: http://{settings.host}:{settings.port}/docs")
    print(f"- ffmpeg: {'found' if shutil.which('ffmpeg') else 'missing'}")
    print(f"- GLM_API_KEY: {'configured' if settings.glm_enabled else 'not configured'}")
    print(f"- Bilibili Cookie: {'configured' if bilibili_cookie['configured'] else 'not configured'}")
    print(f"- Cache root: {settings.cache_root}")


if __name__ == "__main__":
    settings = get_settings()
    print_startup_status()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
