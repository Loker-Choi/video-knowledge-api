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
echo "当前项目默认启用 GLM-ASR 和视频画面理解，必须先配置 GLM_API_KEY。"
echo "Bilibili 视频也必须配置 BILIBILI_COOKIE，用于读取字幕、音频和视频。"
echo "请创建或编辑 .env："
echo "  cp .env.example .env"
echo "    复制一份配置模板，生成自己的 .env 配置文件。"
echo "  code .env"
echo "    在编辑器中打开 .env，然后填写自己的 GLM_API_KEY 或 BILIBILI_COOKIE。"
echo "必填配置示例："
echo "  GLM_API_KEY=your_zhipu_api_key"
echo "  BILIBILI_COOKIE=\"SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx\""
echo "fallback_to_glm_stt 和 include_visual_analysis 默认都是 true。"
echo ""
echo "修改 .env 后，请执行下面的命令重启服务，让配置生效："
echo "  RESTART=1 bash .devcontainer/start-api.sh"
echo ""
echo "也可以通过接口临时写入 Cookie："
echo "  POST ${PUBLIC_URL}/v1/auth/cookies"
echo "  请求体：{\"platform\":\"bilibili\",\"cookie\":\"SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx\"}"
echo ""
echo "查看启动日志："
echo "  tail -f ${LOG_FILE}"
echo ""
