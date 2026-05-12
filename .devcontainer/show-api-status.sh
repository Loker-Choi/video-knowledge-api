#!/usr/bin/env bash
set -u

PORT="${PORT:-8000}"
LOG_FILE="/tmp/video-knowledge-api.log"

echo ""
echo "Video Knowledge API Codespaces status"
echo "-------------------------------------"

if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "Service is running on port ${PORT}."
  echo "Open the Ports panel, set port ${PORT} to Public, then copy the public URL."
  echo "Health check path: /health"
  echo "API path: /api/generate_note"
else
  echo "Service is not running yet."
  echo "Start it manually with:"
  echo "  bash .devcontainer/start-api.sh"
fi

echo ""
echo "View startup logs with:"
echo "  tail -f ${LOG_FILE}"
echo ""
