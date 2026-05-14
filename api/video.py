from __future__ import annotations

import multiprocessing
import os
import queue
import signal
import threading
import time
import uuid
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.models import DEFAULT_LANGUAGES, ExtractRequest, ExtractResponse
from config import get_settings
from services.video import extract_video_payload
from utils.stage_log import log_stage, set_request_id


router = APIRouter(tags=["video"])
_worker_context = multiprocessing.get_context("spawn")
_active_lock = threading.Lock()
_active_task: dict[str, Any] | None = None
_cancelled_requests: set[str] = set()

ERROR_STATUS_CODES = {
    "UNSUPPORTED_PLATFORM": 400,
    "MISSING_GLM_API_KEY": 400,
    "MISSING_BILIBILI_COOKIE": 400,
    "NO_TRANSCRIPT": 404,
    "REQUEST_CANCELLED": 409,
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
    request_id = uuid.uuid4().hex[:12]
    set_request_id(request_id)
    log_stage("request_received", url=url)
    result_queue: multiprocessing.Queue[dict[str, Any]] = _worker_context.Queue(maxsize=1)
    process = _worker_context.Process(
        target=extract_worker,
        args=(payload.model_dump(mode="json"), result_queue, request_id),
    )

    try:
        start_latest_worker(request_id, process)
        started_at = time.monotonic()

        while True:
            process.join(timeout=1)
            if not process.is_alive():
                break
            if is_cancelled(request_id):
                terminate_process(process)
                log_stage("request_cancelled", pid=process.pid)
                return ExtractResponse(
                    ok=False,
                    platform="unknown",
                    url=url,
                    dify_payload=empty_dify_payload(url),
                    warnings=["A newer request cancelled this video task."],
                    error="REQUEST_CANCELLED",
                )
            if time.monotonic() - started_at >= timeout:
                terminate_process(process)
                log_stage("request_timeout", timeout_seconds=timeout, pid=process.pid)
                return ExtractResponse(
                    ok=False,
                    platform="unknown",
                    url=url,
                    dify_payload=empty_dify_payload(url),
                    warnings=[f"Request exceeded {timeout} seconds and the worker process was terminated."],
                    error="REQUEST_TIMEOUT",
                )

        if is_cancelled(request_id):
            log_stage("request_cancelled", pid=process.pid)
            return ExtractResponse(
                ok=False,
                platform="unknown",
                url=url,
                dify_payload=empty_dify_payload(url),
                warnings=["A newer request cancelled this video task."],
                error="REQUEST_CANCELLED",
            )

        try:
            result = result_queue.get(timeout=1)
        except queue.Empty:
            log_stage("worker_crashed", exitcode=process.exitcode)
            return ExtractResponse(
                ok=False,
                platform="unknown",
                url=url,
                dify_payload=empty_dify_payload(url),
                warnings=[f"Worker exited without a response. Exit code: {process.exitcode}."],
                error="WORKER_CRASHED",
            )

        if result.get("ok"):
            response = ExtractResponse.model_validate(result["response"])
            log_stage("request_completed", ok=response.ok, error=response.error)
            return response

        log_stage("worker_failed", message=str(result.get("message") or "Worker failed."))
        return ExtractResponse(
            ok=False,
            platform="unknown",
            url=url,
            dify_payload=empty_dify_payload(url),
            warnings=[str(result.get("message") or "Worker failed.")],
            error="WORKER_FAILED",
        )
    finally:
        clear_active_task(request_id)
        close_queue(result_queue)


def start_latest_worker(request_id: str, process: multiprocessing.Process) -> None:
    global _active_task
    with _active_lock:
        previous = _active_task
        if previous and previous.get("process") and previous["process"].is_alive():
            previous_request_id = str(previous.get("request_id") or "")
            if previous_request_id:
                _cancelled_requests.add(previous_request_id)
            log_stage("previous_worker_cancel", previous_request_id=previous_request_id, pid=previous["process"].pid)
            terminate_process(previous["process"])
        _active_task = {"request_id": request_id, "process": process}
        log_stage("worker_starting")
        process.start()
        log_stage("worker_started", pid=process.pid)


def is_cancelled(request_id: str) -> bool:
    with _active_lock:
        return request_id in _cancelled_requests


def clear_active_task(request_id: str) -> None:
    global _active_task
    with _active_lock:
        _cancelled_requests.discard(request_id)
        if _active_task and _active_task.get("request_id") == request_id:
            _active_task = None


def extract_worker(payload_data: dict[str, Any], result_queue: multiprocessing.Queue[dict[str, Any]], request_id: str) -> None:
    create_worker_process_group()
    set_request_id(request_id)
    try:
        log_stage("worker_processing")
        payload = ExtractRequest.model_validate(payload_data)
        response = extract_video_payload(payload)
        log_stage("worker_response_ready", ok=response.ok, error=response.error)
        result_queue.put({"ok": True, "response": response.model_dump(mode="json")})
    except BaseException as exc:
        log_stage("worker_exception", message=str(exc), exc_type=type(exc).__name__)
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
    terminate_process_group(process)
    process.join(timeout=5)
    if process.is_alive():
        kill_process_group(process)
        process.join(timeout=5)


def close_queue(result_queue: multiprocessing.Queue[dict[str, Any]]) -> None:
    result_queue.close()
    result_queue.join_thread()


def create_worker_process_group() -> None:
    if os.name != "posix":
        return
    try:
        os.setsid()
    except OSError:
        pass


def terminate_process_group(process: multiprocessing.Process) -> None:
    if os.name == "posix" and process.pid:
        try:
            process_group_id = os.getpgid(process.pid)
            if process_group_id == process.pid:
                os.killpg(process_group_id, signal.SIGTERM)
                return
        except ProcessLookupError:
            return
        except OSError:
            pass
    process.terminate()


def kill_process_group(process: multiprocessing.Process) -> None:
    if os.name == "posix" and process.pid:
        try:
            process_group_id = os.getpgid(process.pid)
            if process_group_id == process.pid:
                os.killpg(process_group_id, signal.SIGKILL)
                return
        except ProcessLookupError:
            return
        except OSError:
            pass
    process.kill()
