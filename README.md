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

---

## 🎬 项目简介

Video Knowledge API 是基于bilinote开发的轻量视频解析服务。

输入一个 YouTube 或 Bilibili 视频链接，API 会返回结构化 JSON，包括：

- 视频标题、时长、作者等元信息
- 带时间轴的字幕分段
- 合并后的纯文本字幕
- 适合工作流处理的分块文本

### 项目简介

这个服务用于课堂里的 Dify 视频分析实验：学生把仓库部署到自己的 GitHub Codespaces，公开 `8000` 端口，然后让 Dify 云端通过 HTTP Request 调用。

它参考了 BiliNote 的关键思路，但保留最小可教学版本：

- 有字幕时，直接返回字幕和时间轴。
- YouTube 优先使用 `youtube-transcript-api`。
- Bilibili 优先尝试官方 player API 字幕直拉，再回退到 `yt-dlp`。
- 如果 Bilibili 字幕需要登录态，可以配置 Cookie。
- 不做前端、不做数据库、不做本地 Whisper、不做 LLM 总结。

## 基本流程

```text
视频链接 -> API 解析 -> 字幕 / 时间轴 / 分块文本 -> 下游应用分析
```

## 🚀 快速部署：GitHub Codespaces

在 GitHub 仓库页面：

1. 点击绿色的 Code
2. 选择 Codespaces
3. 点击 Create codespace on main
4. 等待 Codespaces 打开
5. 等待依赖安装完成

服务通常会自动运行在 8000 端口。

手动启动命令：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

在 Codespaces 的 Ports 面板中找到 8000，将 Visibility 改为 Public，复制公开地址：

```text
https://你的-codespace-名字-8000.app.github.dev
```

健康检查：

```bash
curl https://你的-codespace-名字-8000.app.github.dev/health
```

返回示例：

```json
{
  "ok": true,
  "service": "video-analysis-api"
}
```

## 📚 API 接口文档

### 健康检查

```http
GET /health
```

### 同步解析视频

```http
POST /v1/video/extract
```

请求头：

```http
Content-Type: application/json
```

请求体：

```json
{
  "url": "https://www.bilibili.com/video/BVxxxxxx",
  "languages": ["zh-Hans", "zh-CN", "zh", "en"],
  "include_metadata": true,
  "max_chars_per_chunk": 5000
}
```

参数说明：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| url | string | YouTube 或 Bilibili 视频链接 |
| languages | array | 字幕语言优先级 |
| include_metadata | boolean | 返回标题、时长、作者等信息 |
| max_chars_per_chunk | number | 单个文本分块最大字符数 |

返回示例：

```json
{
  "ok": true,
  "platform": "bilibili",
  "video_id": "BVxxxxxx",
  "metadata": {
    "title": "视频标题",
    "duration": 1234.5,
    "uploader": "作者名称"
  },
  "transcript": {
    "language": "zh-CN",
    "has_timeline": true,
    "segments": [
      {
        "index": 0,
        "start": 0.0,
        "end": 3.2,
        "timestamp": "00:00:00",
        "text": "第一句字幕"
      }
    ],
    "plain_text": "完整字幕文本",
    "timeline_text": "[00:00:00 - 00:00:03] 第一句字幕"
  },
  "dify_payload": {
    "timeline_text": "带时间轴的字幕文本",
    "plain_text": "普通字幕文本",
    "chunks": []
  },
  "warnings": []
}
```

### OpenAPI 文档

```http
GET /openapi.json
```

完整地址示例：

```text
https://你的-codespace-名字-8000.app.github.dev/openapi.json
```

## 🔐 VIDEO_API_TOKEN 访问密码

VIDEO_API_TOKEN 是这个 API 服务的访问密码。

Codespaces 端口设为 Public 后，设置 VIDEO_API_TOKEN 可以保护接口访问。

启动服务前设置：

```bash
export VIDEO_API_TOKEN="换成你自己的长密码"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

请求接口时添加：

```http
Authorization: Bearer 换成你自己的长密码
```

格式示例：

```http
Authorization: Bearer abc123456
```

## 🍪 Bilibili Cookie 登录态

部分 Bilibili 视频的 AI 字幕需要登录态。浏览器登录 Bilibili 后可以看到字幕，API 读取字幕时也需要同一份登录态。

可以把浏览器里的 Bilibili Cookie 保存到本服务中，让 API 使用登录态读取 AI 字幕。

Cookie 属于个人登录凭证，请妥善保存。泄露后建议退出 Bilibili 登录或刷新登录态。

### 网页端提取 Cookie

推荐使用 Chrome 或 Edge 浏览器：

1. 打开 Bilibili 网页版
2. 登录自己的 Bilibili 账号
3. 打开需要解析的视频页面
4. 按 F12 打开开发者工具
5. 点击 Network 或 网络
6. 刷新页面
7. 在请求列表里点击一个 bilibili.com 或 api.bilibili.com 请求
8. 点击右侧的 Headers 或 标头
9. 找到 Request Headers 或 请求标头
10. 找到 Cookie
11. 复制 Cookie: 后面的完整内容

复制出来的 Cookie 通常是一长串文本，中间包含很多用分号分隔的字段，例如：

```text
SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx
```

### 写入 Bilibili Cookie

使用前先设置 VIDEO_API_TOKEN。

```bash
curl -X POST "https://你的-codespace-名字-8000.app.github.dev/v1/auth/cookies" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 你的访问密码" \
  -d '{
    "platform": "bilibili",
    "cookie": "SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx"
  }'
```

示例里的 xxx 替换成浏览器复制出来的真实 Cookie 内容。

### 查看 Cookie 状态

```bash
curl "https://你的-codespace-名字-8000.app.github.dev/v1/auth/cookies/bilibili" \
  -H "Authorization: Bearer 你的访问密码"
```

返回示例：

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

状态接口只返回配置情况，原始 Cookie 内容保存在服务端。

### 删除 Cookie

```bash
curl -X DELETE "https://你的-codespace-名字-8000.app.github.dev/v1/auth/cookies/bilibili" \
  -H "Authorization: Bearer 你的访问密码"
```

Cookie 保存位置：

```text
.secrets/cookies.json
```

.secrets/ 已经写入 .gitignore，用于保存本地私密配置。

## ⚠️ 注意事项 & 限制

- 当前版本聚焦字幕解析和时间轴整理
- 支持平台：YouTube、Bilibili
- 平台字幕可用性会影响解析结果
- Bilibili AI 字幕可能需要 Cookie 登录态
- YouTube 字幕读取可能受网络环境影响
- 长视频建议使用 max_chars_per_chunk 控制分块大小
- Codespaces 免费资源适合课堂演示和轻量测试
- 主要依赖：FastAPI、yt-dlp、youtube-transcript-api

## 🧾 接口列表

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /health | 检查服务状态 |
| POST | /v1/video/extract | 解析视频字幕 |
| POST | /v1/auth/cookies | 保存 Cookie |
| GET | /v1/auth/cookies/bilibili | 查看 Cookie 状态 |
| DELETE | /v1/auth/cookies/bilibili | 删除 Cookie |
| GET | /openapi.json | 查看 OpenAPI 文档 |
