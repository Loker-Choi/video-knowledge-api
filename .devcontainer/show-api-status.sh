#!/usr/bin/env bash
set -u

PORT="${PORT:-8000}"
LOG_FILE="/tmp/video-knowledge-api.log"
CODESPACE_NAME="${CODESPACE_NAME:-your-codespace-name}"
PUBLIC_URL="https://${CODESPACE_NAME}-${PORT}.app.github.dev"

echo ""
echo "Video Knowledge API Codespaces 状态"
echo "-------------------------------------"

if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "服务已在 ${PORT} 端口运行。"
  echo "请打开 Ports 面板，把 ${PORT} 端口设置为 Public，然后复制公网链接。"
  echo "公网链接格式：${PUBLIC_URL}"
  echo "健康检查路径：/health"
  echo "视频解析接口：/api/generate_note"
else
  echo "服务还没有运行。"
  echo "可以手动执行下面的命令启动："
  echo "  bash .devcontainer/start-api.sh"
fi

echo ""
echo "配置说明"
echo "-------------"
echo "第一次使用时，请在终端依次输入："
echo "  cp .env.example .env"
echo "    作用：复制配置模板，生成自己的 .env 文件。"
echo "  code .env"
echo "    作用：打开 .env 文件，填写自己的配置。"
echo ""
echo ".env 里需要填写："
echo "  GLM_API_KEY=your_zhipu_api_key"
echo "  BILIBILI_COOKIE=\"SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx\""
echo ""
echo "保存 .env 后，执行下面的命令重启服务："
echo "  RESTART=1 bash .devcontainer/start-api.sh"
echo ""
