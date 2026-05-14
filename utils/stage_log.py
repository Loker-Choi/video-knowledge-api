from __future__ import annotations

import contextvars
import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit


_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_SENSITIVE_PARTS = ("key", "cookie", "token", "authorization", "secret", "sessdata", "bili_jct")
_SENSITIVE_VALUE_PATTERNS = (
    (re.compile(r"(Cookie:\s*)[^\r\n]+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(SESSDATA=)[^;\s]+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(bili_jct=)[^;\s]+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(DedeUserID=)[^;\s]+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(GLM_API_KEY\s*=\s*)[^\s;]+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(ZHIPUAI_API_KEY\s*=\s*)[^\s;]+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"((?:api[_-]?key|secret|token)\s*[=:]\s*)[^\s;]+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(Authorization:\s*Bearer\s+)[^\s;]+", re.IGNORECASE), r"\1<redacted>"),
)


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def get_request_id() -> str:
    return _request_id.get()


def log_stage(stage: str, message: str = "", **fields: Any) -> None:
    parts = [
        f"time={json.dumps(datetime.now().isoformat(timespec='seconds'), ensure_ascii=False)}",
        f"request_id={json.dumps(get_request_id(), ensure_ascii=False)}",
        f"stage={json.dumps(stage, ensure_ascii=False)}",
        f"status={json.dumps(_status_from_stage(stage), ensure_ascii=False)}",
    ]
    if message:
        parts.append(f"message={json.dumps(_sanitize_string(message), ensure_ascii=False)}")
    for key, value in fields.items():
        if _is_sensitive_key(key):
            parts.append(f"{key}=\"<redacted>\"")
            continue
        parts.append(f"{key}={json.dumps(_sanitize_value(key, value), ensure_ascii=False, default=str)}")
    print(" ".join(parts), flush=True)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_PARTS)


def _shorten(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    value = _sanitize_string(value)
    if len(value) <= 180:
        return value
    return f"{value[:177]}..."


def _sanitize_value(key: str, value: Any) -> Any:
    if isinstance(value, str) and "url" in key.lower():
        return _shorten(_sanitize_url(value))
    return _shorten(value)


def _sanitize_string(value: str) -> str:
    sanitized = value
    for pattern, replacement in _SENSITIVE_VALUE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def _sanitize_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or not parsed.netloc:
        return value
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _status_from_stage(stage: str) -> str:
    lowered = stage.lower()
    if lowered.endswith(("_start", "_starting")):
        return "start"
    if lowered.endswith(("_done", "_completed", "_ready", "_built")):
        return "done"
    if lowered.endswith(("_failed", "_exception", "_crashed")):
        return "failed"
    if lowered.endswith("_timeout"):
        return "timeout"
    if lowered.endswith("_cancel") or lowered.endswith("_cancelled"):
        return "cancelled"
    if lowered.endswith("_cleanup"):
        return "cleanup"
    if lowered.endswith("_received"):
        return "received"
    return "info"
