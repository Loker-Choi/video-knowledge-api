from __future__ import annotations

import concurrent.futures
import threading

from fastapi import APIRouter, Query

from app.models import DEFAULT_LANGUAGES, ExtractRequest, ExtractResponse
from config import get_settings
from services.video import extract_video_payload


router = APIRouter(tags=["video"])
_task_limiter = threading.BoundedSemaphore(get_settings().max_concurrent_tasks)


@router.post("/api/generate_note", response_model=ExtractResponse)
def generate_note_api(payload: ExtractRequest) -> ExtractResponse:
    return run_with_timeout(payload)


@router.post("/v1/video/extract", response_model=ExtractResponse)
def extract_video(payload: ExtractRequest) -> ExtractResponse:
    return run_with_timeout(payload)


@router.post("/v1/video/generate_note", response_model=ExtractResponse)
def generate_note(payload: ExtractRequest) -> ExtractResponse:
    return run_with_timeout(payload)


@router.get("/v1/video/extract", response_model=ExtractResponse)
def extract_video_get(
    url: str = Query(..., description="Bilibili or YouTube video URL."),
    languages: str = Query(",".join(DEFAULT_LANGUAGES), description="Comma-separated language priority list."),
    include_metadata: bool = True,
    max_chars_per_chunk: int = Query(5000, ge=500, le=20000),
) -> ExtractResponse:
    language_list = [item.strip() for item in languages.split(",") if item.strip()]
    return run_with_timeout(
        ExtractRequest(
            url=url,
            languages=language_list or DEFAULT_LANGUAGES.copy(),
            include_metadata=include_metadata,
            max_chars_per_chunk=max_chars_per_chunk,
        )
    )


def run_with_timeout(payload: ExtractRequest) -> ExtractResponse:
    timeout = get_settings().request_timeout_seconds
    if not _task_limiter.acquire(blocking=False):
        return ExtractResponse(
            ok=False,
            platform="unknown",
            url=str(payload.url),
            dify_payload={
                "title": None,
                "url": str(payload.url),
                "platform": "unknown",
                "timeline_text": "",
                "plain_text": "",
                "chunks": [],
                "visual_summary": "",
            },
            warnings=["The service is busy. Try again after the current task finishes."],
            error="SERVER_BUSY",
        )

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    released = False
    future: concurrent.futures.Future[ExtractResponse] | None = None

    def release_task() -> None:
        nonlocal released
        if released:
            return
        released = True
        executor.shutdown(wait=False, cancel_futures=True)
        _task_limiter.release()

    try:
        future = executor.submit(extract_video_payload, payload)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            future.add_done_callback(lambda _: release_task())
            future.cancel()
            url = str(payload.url)
            return ExtractResponse(
                ok=False,
                platform="unknown",
                url=url,
                dify_payload={
                    "title": None,
                    "url": url,
                    "platform": "unknown",
                    "timeline_text": "",
                    "plain_text": "",
                    "chunks": [],
                    "visual_summary": "",
                },
                warnings=[f"Request exceeded {timeout} seconds."],
                error="REQUEST_TIMEOUT",
            )
    finally:
        if future is not None and future.done():
            release_task()
