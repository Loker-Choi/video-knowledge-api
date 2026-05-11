<div align="center">
  <h1>Video Analysis API</h1>
  <p><strong>面向 Dify 的 Bilibili / YouTube 字幕与时间轴解析服务</strong></p>
  <p><em>A lightweight Bilibili / YouTube transcript API for Dify workflows</em></p>
</div>

<p align="center">
  <img src="https://img.shields.io/badge/backend-FastAPI-009688" alt="FastAPI" />
  <img src="https://img.shields.io/badge/deploy-GitHub%20Codespaces-181717" alt="GitHub Codespaces" />
  <img src="https://img.shields.io/badge/workflow-Dify-4B7BEC" alt="Dify" />
  <img src="https://img.shields.io/badge/platform-Bilibili%20%7C%20YouTube-ff69b4" alt="Platforms" />
  <img src="https://img.shields.io/badge/no%20database-v1-success" alt="No database" />
</p>

<p align="center">
  <a href="#中文">中文</a> ·
  <a href="#english">English</a> ·
  <a href="#api-reference">API Reference</a>
</p>

---

## 中文

### 项目简介

这个服务用于课堂里的 Dify 视频分析实验：学生把仓库部署到自己的 GitHub Codespaces，公开 `8000` 端口，然后让 Dify 云端通过 HTTP Request 调用。

它参考了 BiliNote 的关键思路，但保留最小可教学版本：

- 有字幕时，直接返回字幕和时间轴。
- YouTube 优先使用 `youtube-transcript-api`。
- Bilibili 优先尝试官方 player API 字幕直拉，再回退到 `yt-dlp`。
- 如果 Bilibili 字幕需要登录态，可以配置 Cookie。
- 不做前端、不做数据库、不做本地 Whisper、不做 LLM 总结。

### 功能特性

- **Dify 友好输出**：返回 `timeline_text`、`plain_text`、`segments` 和 `chunks`。
- **时间轴保留**：每段字幕包含 `start`、`end`、`duration` 和 `timestamp`。
- **长视频分块**：`max_chars_per_chunk` 避免一次性把长文本塞进 LLM。
- **Bilibili 登录态**：支持保存 Cookie，用于读取需要登录态的 AI 字幕。
- **Codespaces 友好**：提供 `.devcontainer`，自动安装依赖并启动服务。
- **OpenAPI 可导入**：Dify 自定义 API Tool 可导入 `/openapi.json`。

### 快速开始：GitHub Codespaces

1. 在 GitHub 打开这个仓库。
2. 点击 `Code -> Codespaces -> Create codespace`。
3. 等待依赖安装完成。
4. 服务会自动尝试在后台启动。如果没有启动，手动运行：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. 打开 Codespaces 的 `Ports` 面板。
6. 找到 `8000` 端口。
7. 将 Visibility 改成 `Public`。
8. 复制公网地址，形如：

```text
https://<codespace-name>-8000.app.github.dev
```

测试连通性：

```bash
curl https://<codespace-name>-8000.app.github.dev/health
```

预期返回：

```json
{"ok":true,"service":"video-analysis-api"}
```

### Dify HTTP Request 配置

URL:

```text
https://<codespace-name>-8000.app.github.dev/v1/video/extract
```

Method:

```text
POST
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "url": "{{video_url}}",
  "languages": ["zh-Hans", "zh-CN", "zh", "en"],
  "include_metadata": true,
  "max_chars_per_chunk": 5000
}
```

Dify 后续节点优先使用：

```text
{{api_response.dify_payload.timeline_text}}
{{api_response.dify_payload.plain_text}}
{{api_response.dify_payload.chunks}}
```

### 推荐安全配置

如果端口设为 Public，建议一定设置 `VIDEO_API_TOKEN`：

```bash
export VIDEO_API_TOKEN="replace-with-a-long-random-token"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Dify Header 增加：

```text
Authorization: Bearer replace-with-a-long-random-token
```

### Bilibili Cookie 登录态

有些 Bilibili 视频未登录时只暴露弹幕，不暴露 AI 字幕。此时可以配置 Cookie。这个服务不接收账号密码，也不做扫码登录，只保存学生自己提供的 Cookie 字符串。

Cookie 管理接口要求已经设置 `VIDEO_API_TOKEN`，否则会返回 `403`。

写入 Bilibili Cookie：

```bash
curl -X POST "https://<codespace-name>-8000.app.github.dev/v1/auth/cookies" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer replace-with-a-long-random-token" \
  -d '{
    "platform": "bilibili",
    "cookie": "SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx"
  }'
```

查看 Cookie 状态，接口不会返回 Cookie 明文：

```bash
curl "https://<codespace-name>-8000.app.github.dev/v1/auth/cookies/bilibili" \
  -H "Authorization: Bearer replace-with-a-long-random-token"
```

删除 Cookie：

```bash
curl -X DELETE "https://<codespace-name>-8000.app.github.dev/v1/auth/cookies/bilibili" \
  -H "Authorization: Bearer replace-with-a-long-random-token"
```

本地保存位置：

```text
.secrets/cookies.json
```

`.secrets/` 已加入 `.gitignore`。不要把 Cookie 提交到 GitHub。

### 与 BiliNote 的关系

本项目借鉴 BiliNote 的这些设计：

- 平台字幕优先。
- Bilibili 需要登录态时用 Cookie。
- Bilibili 可通过 player API 直拉字幕。
- `yt-dlp` 作为通用元信息和字幕兜底工具。
- 预留 `frame_interval=6` 与 `grid_size=[2,2]` 给后续关键帧能力。

但本项目刻意不复制 BiliNote 的完整产品形态：

- 不做 React 前端。
- 不做任务队列。
- 不做数据库。
- 不做模型供应商配置。
- 不做本地转写器。
- 不生成 Markdown 笔记。
- 不做浏览器扩展。

### 本地开发

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## English

### Overview

This service is a lightweight video transcript API for Dify classroom workflows. Students deploy it in their own GitHub Codespaces, expose port `8000`, and call it from Dify Cloud through an HTTP Request node or a custom API tool.

It borrows the practical parts of BiliNote, but keeps the implementation small:

- Return subtitles and timestamps directly when available.
- Use `youtube-transcript-api` first for YouTube.
- Use Bilibili player API first for Bilibili subtitles, then fall back to `yt-dlp`.
- Support Cookie-based login state for Bilibili subtitle access.
- No frontend, no database, no local Whisper, and no LLM summarization in v1.

### Features

- **Dify-ready JSON**: `timeline_text`, `plain_text`, `segments`, and `chunks`.
- **Timestamp preservation**: each segment includes `start`, `end`, `duration`, and `timestamp`.
- **Long-video chunking**: `max_chars_per_chunk` keeps LLM inputs manageable.
- **Bilibili Cookie support**: access login-only AI subtitles when the student provides Cookie.
- **Codespaces deployment**: `.devcontainer` installs dependencies and starts the API.
- **OpenAPI support**: Dify can import `/openapi.json`.

### Quick Start: GitHub Codespaces

1. Open this repository on GitHub.
2. Click `Code -> Codespaces -> Create codespace`.
3. Wait for dependency installation.
4. The service should start automatically. If it does not, run:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. Open the Codespaces `Ports` panel.
6. Find port `8000`.
7. Set visibility to `Public`.
8. Copy the public URL:

```text
https://<codespace-name>-8000.app.github.dev
```

Health check:

```bash
curl https://<codespace-name>-8000.app.github.dev/health
```

Expected:

```json
{"ok":true,"service":"video-analysis-api"}
```

### Dify HTTP Request

URL:

```text
https://<codespace-name>-8000.app.github.dev/v1/video/extract
```

Method:

```text
POST
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "url": "{{video_url}}",
  "languages": ["zh-Hans", "zh-CN", "zh", "en"],
  "include_metadata": true,
  "max_chars_per_chunk": 5000
}
```

Recommended Dify fields:

```text
{{api_response.dify_payload.timeline_text}}
{{api_response.dify_payload.plain_text}}
{{api_response.dify_payload.chunks}}
```

### Bearer Token

For a public Codespaces port, set `VIDEO_API_TOKEN`:

```bash
export VIDEO_API_TOKEN="replace-with-a-long-random-token"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then add this Dify header:

```text
Authorization: Bearer replace-with-a-long-random-token
```

### Bilibili Cookie Login State

Some Bilibili videos expose AI subtitles only when logged in. This service does not handle usernames, passwords, or QR-code login. It only stores a Cookie string provided by the student.

Cookie management requires `VIDEO_API_TOKEN`.

Set Bilibili Cookie:

```bash
curl -X POST "https://<codespace-name>-8000.app.github.dev/v1/auth/cookies" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer replace-with-a-long-random-token" \
  -d '{
    "platform": "bilibili",
    "cookie": "SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx"
  }'
```

Check Cookie status. The raw Cookie is never returned:

```bash
curl "https://<codespace-name>-8000.app.github.dev/v1/auth/cookies/bilibili" \
  -H "Authorization: Bearer replace-with-a-long-random-token"
```

Delete Cookie:

```bash
curl -X DELETE "https://<codespace-name>-8000.app.github.dev/v1/auth/cookies/bilibili" \
  -H "Authorization: Bearer replace-with-a-long-random-token"
```

Local storage:

```text
.secrets/cookies.json
```

`.secrets/` is ignored by Git. Never commit Cookies.

---

## API Reference

### `GET /health`

Returns:

```json
{
  "ok": true,
  "service": "video-analysis-api"
}
```

### `POST /v1/video/extract`

Request:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "languages": ["zh-Hans", "zh-CN", "zh", "en"],
  "include_metadata": true,
  "max_chars_per_chunk": 5000,
  "include_keyframes": false,
  "frame_interval": 6,
  "grid_size": [2, 2]
}
```

Success response shape:

```json
{
  "ok": true,
  "platform": "youtube",
  "video_id": "VIDEO_ID",
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "metadata": {
    "title": "Video title",
    "duration": 1234.5,
    "uploader": "Channel",
    "webpage_url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "thumbnail": "https://...",
    "chapters": []
  },
  "transcript": {
    "source": "youtube_transcript_api",
    "language": "zh-CN",
    "is_generated": false,
    "segments": [
      {
        "index": 0,
        "start": 0.0,
        "end": 3.2,
        "duration": 3.2,
        "timestamp": "00:00:00",
        "text": "..."
      }
    ],
    "plain_text": "...",
    "timeline_text": "[00:00:00 - 00:00:03] ..."
  },
  "dify_payload": {
    "timeline_text": "...",
    "plain_text": "...",
    "segments": [],
    "chunks": []
  },
  "warnings": [],
  "error": null
}
```

Failure responses keep HTTP `200` for Dify workflow branching:

```json
{
  "ok": false,
  "platform": "bilibili",
  "url": "https://www.bilibili.com/video/BV...",
  "transcript": null,
  "dify_payload": {
    "timeline_text": "",
    "plain_text": "",
    "segments": [],
    "chunks": []
  },
  "warnings": ["No usable subtitle/timeline track found"],
  "error": "NO_TRANSCRIPT"
}
```

### `POST /v1/auth/cookies`

Requires:

```text
Authorization: Bearer <VIDEO_API_TOKEN>
```

Request:

```json
{
  "platform": "bilibili",
  "cookie": "SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx"
}
```

Response:

```json
{
  "ok": true,
  "platform": "bilibili",
  "configured": true,
  "cookie_count": 3,
  "required_keys_present": ["SESSDATA", "bili_jct", "DedeUserID"],
  "required_keys_missing": []
}
```

### `GET /openapi.json`

FastAPI generates this automatically:

```text
https://<codespace-name>-8000.app.github.dev/openapi.json
```
