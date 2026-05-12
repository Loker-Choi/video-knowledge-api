from __future__ import annotations

import multiprocessing
import queue
import threading
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.models import DEFAULT_LANGUAGES, ExtractRequest, ExtractResponse
from config import get_settings
from services.video import extract_video_payload


router = APIRouter(tags=["video"])
_task_limiter = threading.BoundedSemaphore(get_settings().max_concurrent_tasks)
_worker_context = multiprocessing.get_context("spawn")

ERROR_STATUS_CODES = {
    "UNSUPPORTED_PLATFORM": 400,
    "NO_TRANSCRIPT": 404,
    "SERVER_BUSY": 429,
    "REQUEST_TIMEOUT": 504,
    "WORKER_FAILED": 500,
    "WORKER_CRASHED": 500,
}


@router.post("/api/generate_note", response_model=ExtractResponse)
def generate_note_api(payload: ExtractRequest) -> JSONResponse:
    return response_with_status(run_with_timeout(payload))


@router.post("/v1/video/extract", response_model=ExtractResponse)
def extract_video(payload: ExtractRequest) -> JSONResponse:
    return response_with_status(run_with_timeout(payload))


@router.post("/v1/video/generate_note", response_model=ExtractResponse)
def generate_note(payload: ExtractRequest) -> JSONResponse:
    return response_with_status(run_with_timeout(payload))


@router.get("/v1/video/extract", response_model=ExtractResponse)
def extract_video_get(
    url: str = Query(..., description="Bilibili or YouTube video URL."),
    languages: str = Query(",".join(DEFAULT_LANGUAGES), description="Comma-separated language priority list."),
    include_metadata: bool = True,
    max_chars_per_chunk: int = Query(5000, ge=500, le=20000),
) -> JSONResponse:
    language_list = [item.strip() for item in languages.split(",") if item.strip()]
    payload = ExtractRequest(
        url=url,
        languages=language_list or DEFAULT_LANGUAGES.copy(),
        include_metadata=include_metadata,
        max_chars_per_chunk=max_chars_per_chunk,
    )
    return response_with_status(run_with_timeout(payload))


def run_with_timeout(payload: ExtractRequest) -> ExtractResponse:
    timeout = get_settings().request_timeout_seconds
    url = str(payload.url)

    if not _task_limiter.acquire(blocking=False):
        return ExtractResponse(
            ok=False,
            platform="unknown",
            url=url,
            dify_payload=empty_dify_payload(url),
            warnings=["The service is busy. Try again after the current task finishes."],
            error="SERVER_BUSY",
        )

    result_queue: multiprocessing.Queue[dict[str, Any]] = _worker_context.Queue(maxsize=1)
    process = _worker_context.Process(
        target=extract_worker,
        args=(payload.model_dump(mode="json"), result_queue),
    )

    try:
        process.start()
        process.join(timeout)

        if process.is_alive():
            terminate_process(process)
            return ExtractResponse(
                ok=False,
                platform="unknown",
                url=url,
                dify_payload=empty_dify_payload(url),
                warnings=[f"Request exceeded {timeout} seconds and the worker process was terminated."],
                error="REQUEST_TIMEOUT",
            )

        try:
            result = result_queue.get(timeout=1)
        except queue.Empty:
            return ExtractResponse(
                ok=False,
                platform="unknown",
                url=url,
                dify_payload=empty_dify_payload(url),
                warnings=[f"Worker exited without a response. Exit code: {process.exitcode}."],
                error="WORKER_CRASHED",
            )

        if result.get("ok"):
            return ExtractResponse.model_validate(result["response"])

        return ExtractResponse(
            ok=False,
            platform="unknown",
            url=url,
            dify_payload=empty_dify_payload(url),
            warnings=[str(result.get("message") or "Worker failed.")],
            error="WORKER_FAILED",
        )
    finally:
        close_queue(result_queue)
        _task_limiter.release()


def extract_worker(payload_data: dict[str, Any], result_queue: multiprocessing.Queue[dict[str, Any]]) -> None:
    try:
        payload = ExtractRequest.model_validate(payload_data)
        response = extract_video_payload(payload)
        result_queue.put({"ok": True, "response": response.model_dump(mode="json")})
    except BaseException as exc:
        result_queue.put({"ok": False, "message": str(exc)})


def response_with_status(response: ExtractResponse) -> JSONResponse:
    return JSONResponse(
        status_code=status_code_for_response(response),
        content=response.model_dump(mode="json"),
    )


def status_code_for_response(response: ExtractResponse) -> int:
    if response.ok:
        return 200
    error = response.error or "INTERNAL_ERROR"
    if error.startswith("EXTRACTION_FAILED"):
        return 502
    return ERROR_STATUS_CODES.get(error, 502)


def empty_dify_payload(url: str) -> dict[str, object]:
    return {
        "title": None,
        "url": url,
        "platform": "unknown",
        "timeline_text": "",
        "plain_text": "",
        "chunks": [],
        "visual_summary": "",
    }


def terminate_process(process: multiprocessing.Process) -> None:
    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join(timeout=5)


def close_queue(result_queue: multiprocessing.Queue[dict[str, Any]]) -> None:
    result_queue.close()
    result_queue.join_thread()
