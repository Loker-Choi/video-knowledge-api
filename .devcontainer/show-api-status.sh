#!/usr/bin/env bash
set -u

PORT="${PORT:-8000}"
LOG_FILE="/tmp/video-knowledge-api.log"
CODESPACE_NAME="${CODESPACE_NAME:-your-codespace-name}"
PUBLIC_URL="https://${CODESPACE_NAME}-${PORT}.app.github.dev"

echo ""
echo "Video Knowledge API Codespaces status"
echo "-------------------------------------"

if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "Service is running on port ${PORT}."
  echo "Open the Ports panel, set port ${PORT} to Public, then copy the public URL."
  echo "Public URL format: ${PUBLIC_URL}"
  echo "Health check path: /health"
  echo "API path: /api/generate_note"
else
  echo "Service is not running yet."
  echo "Start it manually with:"
  echo "  bash .devcontainer/start-api.sh"
fi

echo ""
echo "Configuration"
echo "-------------"
echo "For subtitle-only videos, no API key is required."
echo "For GLM-ASR or visual analysis, create or edit .env:"
echo "  cp .env.example .env"
echo "  code .env"
echo "Then set:"
echo "  GLM_API_KEY=your_zhipu_api_key"
echo "GLM is used when a request sets fallback_to_glm_stt=true or include_visual_analysis=true."
echo ""
echo "After editing .env, restart the service with:"
echo "  RESTART=1 bash .devcontainer/start-api.sh"
echo ""
echo "Bilibili AI subtitles may require login cookies."
echo "Use the public URL after setting port ${PORT} to Public:"
echo "  POST ${PUBLIC_URL}/v1/auth/cookies"
echo "  Body: {\"platform\":\"bilibili\",\"cookie\":\"SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx\"}"
echo ""
echo "View startup logs with:"
echo "  tail -f ${LOG_FILE}"
echo ""
