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
    ready = settings.glm_enabled and bilibili_cookie["configured"]
    print("Video Knowledge API 启动配置")
    print(f"- 服务地址：http://{settings.host}:{settings.port}")
    print(f"- 接口文档：http://{settings.host}:{settings.port}/docs")
    print(f"- ffmpeg：{'已安装' if shutil.which('ffmpeg') else '未检测到'}")
    print(f"- GLM_API_KEY：{'已配置' if settings.glm_enabled else '未配置'}")
    print(f"- Bilibili Cookie：{'已配置' if bilibili_cookie['configured'] else '未配置'}")
    print(f"- 默认视觉解析：已开启")
    print(f"- 默认 GLM-ASR fallback：已开启")
    print(f"- 必填配置状态：{'已就绪' if ready else '未就绪，请检查 .env'}")
    print(f"- 缓存目录：{settings.cache_root}")


if __name__ == "__main__":
    settings = get_settings()
    print_startup_status()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
