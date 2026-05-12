from __future__ import annotations

import shutil
from pathlib import Path

from config import get_settings


def cleanup_workdir(path: Path) -> None:
    settings = get_settings()
    if settings.keep_cache:
        return
    cache_root = settings.cache_root.resolve()
    target = path.resolve()
    try:
        target.relative_to(cache_root)
    except ValueError:
        return
    shutil.rmtree(target, ignore_errors=True)
