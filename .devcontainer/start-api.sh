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
  if "$PYTHON_BIN" -c "import uvicorn, fastapi, yt_dlp, zhipuai, PIL, dotenv, pydantic_settings" >/dev/null 2>&1; then
    return
  fi

  echo "检测到 Python 依赖缺失，正在安装 requirements.txt..."
  "$PYTHON_BIN" -m pip install -r requirements.txt
}

ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1; then
    return
  fi

  echo "检测到 ffmpeg 缺失，正在安装 ffmpeg..."
  if ! sudo apt-get update; then
    echo "apt-get update 失败，正在使用 Debian 官方源重试..."
    install_ffmpeg_from_debian_sources
    return
  fi
  if ! sudo apt-get install -y ffmpeg; then
    echo "apt-get install 失败，正在使用 Debian 官方源重试..."
    install_ffmpeg_from_debian_sources
    return
  fi
  verify_ffmpeg
}

install_ffmpeg_from_debian_sources() {
  codename="$(. /etc/os-release && echo "${VERSION_CODENAME:-bullseye}")"
  temp_sources="/tmp/video-knowledge-api-debian.sources.list"
  cat > "$temp_sources" <<EOF
deb http://deb.debian.org/debian ${codename} main
deb http://deb.debian.org/debian-security ${codename}-security main
deb http://deb.debian.org/debian ${codename}-updates main
EOF

  if ! sudo apt-get \
    -o Dir::Etc::sourcelist="$temp_sources" \
    -o Dir::Etc::sourceparts="-" \
    -o APT::Get::List-Cleanup="0" \
    update; then
    echo "ffmpeg 安装失败：Debian 官方源 update 执行失败。"
    exit 1
  fi

  if ! sudo apt-get \
    -o Dir::Etc::sourcelist="$temp_sources" \
    -o Dir::Etc::sourceparts="-" \
    -o APT::Get::List-Cleanup="0" \
    install -y ffmpeg; then
    echo "ffmpeg 安装失败：Debian 官方源 install 执行失败。"
    exit 1
  fi

  verify_ffmpeg
}

verify_ffmpeg() {
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg 安装后仍未检测到，请检查 Codespaces 环境。"
    exit 1
  fi
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
    echo "正在停止已有的 Video Knowledge API 进程 ${existing_pid}..."
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

stop_leftovers() {
  echo "正在清理残留的 Video Knowledge API worker..."
  pkill -TERM -f "[m]ultiprocessing.spawn" >/dev/null 2>&1 || true
  pkill -TERM -f "[m]ultiprocessing.resource_tracker" >/dev/null 2>&1 || true
  pkill -TERM -f "[p]ython3 main.py" >/dev/null 2>&1 || true
  pkill -TERM -f "[p]ython main.py" >/dev/null 2>&1 || true
  sleep 2
  pkill -KILL -f "[m]ultiprocessing.spawn" >/dev/null 2>&1 || true
  pkill -KILL -f "[m]ultiprocessing.resource_tracker" >/dev/null 2>&1 || true
  pkill -KILL -f "[p]ython3 main.py" >/dev/null 2>&1 || true
  pkill -KILL -f "[p]ython main.py" >/dev/null 2>&1 || true
  rm -f "$PID_FILE"
}

if [ "$RESTART" = "1" ] || [ "$RESTART" = "true" ]; then
  stop_existing
  stop_leftovers
fi

if is_healthy; then
  echo "Video Knowledge API 已经在 ${PORT} 端口运行。"
  exit 0
fi

mkdir -p "$(dirname "$LOG_FILE")"
: > "$LOG_FILE"

ensure_dependencies
ensure_ffmpeg

echo "正在启动 Video Knowledge API，端口：${PORT}..."
nohup "$PYTHON_BIN" main.py >> "$LOG_FILE" 2>&1 &
echo "$!" > "$PID_FILE"

for _ in $(seq 1 30); do
  if is_healthy; then
    echo "Video Knowledge API 已启动。"
    echo "健康检查：http://127.0.0.1:${PORT}/health"
    exit 0
  fi
  if ! kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
    echo "Video Knowledge API 启动失败，最近日志如下："
    tail -80 "$LOG_FILE"
    exit 1
  fi
  sleep 1
done

echo "Video Knowledge API 在 30 秒内没有通过健康检查，最近日志如下："
tail -80 "$LOG_FILE"
exit 1
