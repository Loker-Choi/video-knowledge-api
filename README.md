<div align="center">
  <h1>Video Knowledge API</h1>
  <p><strong>YouTube / Bilibili 视频字幕与画面理解 API</strong></p>
</div>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-API-009688" alt="FastAPI" />
  <img src="https://img.shields.io/badge/YouTube-supported-red" alt="YouTube" />
  <img src="https://img.shields.io/badge/Bilibili-supported-00A1D6" alt="Bilibili" />
  <img src="https://img.shields.io/badge/Codespaces-ready-181717" alt="Codespaces" />
</p>

---

## 🎬 项目简介

Video Knowledge API 是一个基于 FastAPI 开发的轻量视频解析服务，用于把 YouTube 或 Bilibili 视频链接解析为结构化 JSON，返回视频元信息、时间轴字幕、纯文本字幕、分块文本，并可按需启用 GLM 音频转写和 GLM 视觉解析。

项目参考并致谢：

- [BiliNote](https://github.com/JefferyHcool/BiliNote)：字幕优先、登录态 Cookie、视频帧拼图理解等设计思路
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)：视频元信息、字幕轨道、音频和视频下载能力
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api)：YouTube 字幕读取能力
- [FastAPI](https://fastapi.tiangolo.com/)：API 服务和 OpenAPI 文档

主要能力包括：优先读取平台已有字幕，支持 YouTube 人工字幕和自动生成字幕，支持 Bilibili 官方字幕和 AI 字幕，支持通过 Bilibili Cookie 获取需要登录态的 AI 字幕；平台字幕缺失时可以使用 GLM-ASR 做语音转文字，需要理解画面时可以下载视频、抽取静态帧、拼成网格图并交给 GLM 视觉模型分析。

## 🚀 打开方式一：GitHub Codespaces

推荐使用 GitHub Codespaces，适合课堂、演示和快速部署。

在 GitHub 仓库页面：

1. 点击 `Code`
2. 选择 `Codespaces`
3. 点击 `Create codespace on main`
4. 等待 Codespaces 打开
5. 等待依赖安装完成

服务通常会自动运行在 `8000` 端口。也可以在终端手动启动：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

在 Codespaces 的 `Ports` 面板中找到 `8000`，将 Visibility 改为 `Public`，复制公开地址：

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

## 🐳 打开方式二：Docker

Docker 适合有经验的开发者。示例命令如下：

```bash
docker build -t video-knowledge-api .
docker run --rm -p 8000:8000 \
  -e GLM_API_KEY="你的智谱 API Key" \
  video-knowledge-api
```

容器内需要可用的 `ffmpeg`，用于音频切分和关键帧抽取。

## 📚 字幕解析

核心接口：

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
| `url` | string | YouTube 或 Bilibili 视频链接 |
| `languages` | array | 字幕语言优先级 |
| `include_metadata` | boolean | 返回标题、时长、作者等信息 |
| `max_chars_per_chunk` | number | 单个文本分块最大字符数 |

返回内容包括 `metadata`、`transcript.segments`、`transcript.plain_text`、`transcript.timeline_text` 和分块文本等字段，后续应用可以按结构化字段继续处理视频内容。

## 🎞️ YouTube 字幕读取

YouTube 字幕优先使用 `youtube-transcript-api` 读取，会按 `languages` 设置的语言优先级查找字幕，优先读取人工字幕；人工字幕缺失时读取 YouTube 自动生成字幕，`youtube-transcript-api` 失败时再使用 `yt-dlp` 尝试读取字幕轨道和自动字幕轨道。

YouTube 字幕读取主要受视频字幕可用性和网络环境影响。

## 🍪 Bilibili 字幕与登录态

Bilibili 字幕优先通过官方接口读取，优先读取官方字幕和 AI 字幕；字幕需要登录态时，服务会使用已配置的 Bilibili Cookie，官方接口失败时再使用 `yt-dlp` 尝试读取字幕轨道。

Bilibili AI 字幕需要 Cookie 登录态。浏览器登录 Bilibili 后可以看到字幕，API 读取字幕时也需要同一份登录态。

### 网页端提取 Cookie

推荐使用 Chrome 或 Edge 浏览器：

1. 打开 Bilibili 网页版
2. 登录自己的 Bilibili 账号
3. 进入 Bilibili 首页
4. 按 `F12` 打开开发者工具
5. 点击 `Network` 或 `网络`
6. 点击 `文档`，也可能显示为 `Doc` 或 `Document`
7. 刷新页面
8. 在左侧请求列表里点击 `www.bilibili.com`
9. 点击右侧的 `Headers` 或 `标头`
10. 找到 `Request Headers` 或 `请求标头`
11. 找到 `Cookie`
12. 复制 `Cookie:` 后面的完整内容

<p align="center">
  <img src="assets/bilibili-cookie.png" alt="Bilibili Cookie 提取示意图" width="900" />
</p>

复制出来的 Cookie 通常是一长串文本，中间包含很多用分号分隔的字段，例如：

```text
SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx
```

Cookie 属于个人登录凭证，请妥善保存。泄露后建议退出 Bilibili 登录或刷新登录态。

### 写入 Bilibili Cookie

```bash
curl -X POST "https://你的-codespace-名字-8000.app.github.dev/v1/auth/cookies" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "bilibili",
    "cookie": "SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx"
  }'
```

查看 Cookie 状态：

```bash
curl "https://你的-codespace-名字-8000.app.github.dev/v1/auth/cookies/bilibili"
```

删除 Cookie：

```bash
curl -X DELETE "https://你的-codespace-名字-8000.app.github.dev/v1/auth/cookies/bilibili"
```

Cookie 保存位置：

```text
.secrets/cookies.json
```

`.secrets/` 已写入 `.gitignore`。

## 🧠 GLM 音频转写与视觉解析

平台字幕缺失时，可以启用 GLM-ASR 做语音转文字；需要理解视频画面时，可以启用 GLM 视觉解析。使用这些能力前需要在运行环境中设置 `GLM_API_KEY`。

```bash
export GLM_API_KEY="换成你的智谱 API Key"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

<p align="center">
  <img src="assets/glm-api-key.png" alt="GLM API Key 配置示意图" width="900" />
</p>

启用 GLM-ASR：

```json
{
  "url": "https://www.bilibili.com/video/BVxxxxxx",
  "fallback_to_glm_stt": true
}
```

GLM-ASR 会先下载音频，再按模型限制切成短片段。默认参数：

- `stt_segment_seconds`: 25
- `stt_max_segment_mb`: 20

启用视觉解析：

```json
{
  "url": "https://www.bilibili.com/video/BVxxxxxx",
  "include_visual_analysis": true,
  "frame_interval": 6,
  "grid_size": [2, 2],
  "max_keyframes": 16
}
```

视觉解析流程：

```text
yt-dlp 下载低清视频
-> ffmpeg 每 6 秒抽取静态帧
-> Pillow 将 4 张帧拼成 2x2 网格图
-> GLM 视觉模型分析拼图
```

只抽帧和拼图：

```json
{
  "url": "https://www.bilibili.com/video/BVxxxxxx",
  "include_keyframes": true,
  "frame_interval": 6,
  "grid_size": [2, 2],
  "max_keyframes": 16
}
```

临时音频、视频、静态帧和拼图文件保存在：

```text
.cache/video-knowledge-api/
```

## ⚠️ 注意事项 & 限制

- 支持平台：YouTube、Bilibili
- YouTube 字幕读取可能受网络环境影响
- Bilibili AI 字幕需要 Cookie 登录态
- 平台字幕可用性会影响解析结果
- GLM-ASR 和 GLM 视觉解析需要设置 `GLM_API_KEY`

## 🧾 接口列表

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | 检查服务状态 |
| `POST` | `/v1/video/extract` | 解析视频 |
| `POST` | `/v1/auth/cookies` | 保存 Cookie |
| `GET` | `/v1/auth/cookies/bilibili` | 查看 Cookie 状态 |
| `DELETE` | `/v1/auth/cookies/bilibili` | 删除 Cookie |
| `GET` | `/openapi.json` | 查看 OpenAPI 文档 |

## 📄 License

本项目采用 MIT License。详见 [LICENSE](LICENSE)。
