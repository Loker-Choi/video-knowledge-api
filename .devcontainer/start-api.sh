#!/usr/bin/env bash
set -u

cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"
LOG_FILE="/tmp/video-knowledge-api.log"
PID_FILE="/tmp/video-knowledge-api.pid"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RESTART="${RESTART:-false}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

ensure_dependencies() {
  if "$PYTHON_BIN" -c "import uvicorn, fastapi, yt_dlp" >/dev/null 2>&1; then
    return
  fi

  echo "Python dependencies are missing. Installing requirements.txt..."
  "$PYTHON_BIN" -m pip install -r requirements.txt
}

is_healthy() {
  curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1
}

stop_existing() {
  if [ ! -f "$PID_FILE" ]; then
    return
  fi

  existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -z "$existing_pid" ]; then
    rm -f "$PID_FILE"
    return
  fi

  if kill -0 "$existing_pid" >/dev/null 2>&1; then
    echo "Stopping existing Video Knowledge API process ${existing_pid}..."
    kill "$existing_pid" >/dev/null 2>&1 || true
    for _ in $(seq 1 10); do
      if ! kill -0 "$existing_pid" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
  fi

  rm -f "$PID_FILE"
}

if [ "$RESTART" = "1" ] || [ "$RESTART" = "true" ]; then
  stop_existing
fi

if is_healthy; then
  echo "Video Knowledge API is already running on port ${PORT}."
  exit 0
fi

mkdir -p "$(dirname "$LOG_FILE")"
: > "$LOG_FILE"

ensure_dependencies

echo "Starting Video Knowledge API on port ${PORT}..."
nohup "$PYTHON_BIN" main.py >> "$LOG_FILE" 2>&1 &
echo "$!" > "$PID_FILE"

for _ in $(seq 1 30); do
  if is_healthy; then
    echo "Video Knowledge API is running."
    echo "Health: http://127.0.0.1:${PORT}/health"
    echo "Logs: tail -f ${LOG_FILE}"
    exit 0
  fi
  if ! kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
    echo "Video Knowledge API failed to start. Recent logs:"
    tail -80 "$LOG_FILE"
    exit 1
  fi
  sleep 1
done

echo "Video Knowledge API did not become healthy within 30 seconds. Recent logs:"
tail -80 "$LOG_FILE"
exit 1
