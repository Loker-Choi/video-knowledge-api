from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from yt_dlp import YoutubeDL

from .cookies import configured_cookie_store, write_temp_cookiefile
from .extractors import cleanup_temp_cookiefile
from .models import FrameGridInfo, KeyframeInfo
from .text_utils import seconds_to_timestamp
from config import get_settings


class MediaError(RuntimeError):
    pass


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise MediaError("ffmpeg is required for media download, audio splitting, and keyframe extraction")


def cache_dir_for_url(url: str, platform: str, root: str | Path = ".cache/video-knowledge-api") -> Path:
    digest = hashlib.sha256(f"{platform}:{url}".encode("utf-8")).hexdigest()[:16]
    path = Path(root) / digest
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_media(url: str, platform: str, output_dir: Path, *, media_type: str) -> Path:
    ensure_ffmpeg()
    settings = get_settings()
    output_dir.mkdir(parents=True, exist_ok=True)

    if media_type == "audio":
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": str(output_dir / "audio.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "64",
                }
            ],
        }
        expected = output_dir / "audio.mp3"
    elif media_type == "video":
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bv*[height<=480]+ba/b[height<=480]/best[height<=480]/best",
            "merge_output_format": "mp4",
            "outtmpl": str(output_dir / "video.%(ext)s"),
        }
        expected = output_dir / "video.mp4"
    else:
        raise MediaError(f"Unsupported media_type: {media_type}")

    options["socket_timeout"] = settings.yt_dlp_timeout_seconds

    if settings.ytdlp_cookies_file:
        options["cookiefile"] = str(settings.ytdlp_cookies_file)
    else:
        cookie = configured_cookie_store().get(platform)
        if cookie:
            options["cookiefile"] = write_temp_cookiefile(platform, cookie)

    try:
        with YoutubeDL(options) as ydl:
            ydl.download([url])
    except Exception as exc:
        raise MediaError(f"yt-dlp failed to download {media_type}: {exc}") from exc
    finally:
        cleanup_temp_cookiefile(options.get("cookiefile"))

    if expected.exists():
        return expected

    candidates = sorted(output_dir.glob(f"{media_type}.*"))
    if candidates:
        return candidates[0]
    raise MediaError(f"Downloaded {media_type} file was not found")


def split_audio(
    audio_path: Path,
    output_dir: Path,
    *,
    segment_seconds: int = 25,
    max_segment_mb: int = 20,
) -> list[Path]:
    ensure_ffmpeg()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = output_dir / "segment_%03d.mp3"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-f",
        "segment",
        "-segment_time",
        str(segment_seconds),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "48k",
        str(output_pattern),
    ]
    run_command(command)
    segments = sorted(output_dir.glob("segment_*.mp3"))
    oversized = [path for path in segments if path.stat().st_size > max_segment_mb * 1024 * 1024]
    if oversized and segment_seconds > 5:
        for path in segments:
            path.unlink(missing_ok=True)
        return split_audio(
            audio_path,
            output_dir,
            segment_seconds=max(5, segment_seconds // 2),
            max_segment_mb=max_segment_mb,
        )
    if oversized:
        names = ", ".join(path.name for path in oversized[:3])
        raise MediaError(f"Audio segment exceeds {max_segment_mb}MB after splitting: {names}")
    return segments


def extract_keyframes(
    video_path: Path,
    output_dir: Path,
    *,
    frame_interval: int,
    max_keyframes: int,
) -> list[KeyframeInfo]:
    ensure_ffmpeg()
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame_%04d.jpg"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{frame_interval},scale=640:-1",
        "-frames:v",
        str(max_keyframes),
        "-q:v",
        "4",
        str(pattern),
    ]
    run_command(command)

    frames: list[KeyframeInfo] = []
    for index, frame_path in enumerate(sorted(output_dir.glob("frame_*.jpg"))):
        timestamp = float(index * frame_interval)
        frames.append(
            KeyframeInfo(
                index=index,
                timestamp=timestamp,
                timestamp_text=seconds_to_timestamp(timestamp),
                path=str(frame_path),
            )
        )
    return frames


def build_frame_grids(
    keyframes: list[KeyframeInfo],
    output_dir: Path,
    *,
    grid_size: list[int],
    unit_width: int = 640,
    unit_height: int = 360,
    save_quality: int = 80,
) -> list[FrameGridInfo]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if len(grid_size) != 2:
        raise MediaError("grid_size must have two numbers")

    cols, rows = int(grid_size[0]), int(grid_size[1])
    group_size = cols * rows
    if group_size <= 0:
        raise MediaError("grid_size must be positive")

    grids: list[FrameGridInfo] = []
    for start_index in range(0, len(keyframes), group_size):
        group = keyframes[start_index : start_index + group_size]
        if not group:
            continue
        grid_path = output_dir / f"grid_{len(grids):04d}.jpg"
        compose_grid_image(
            group,
            grid_path,
            cols=cols,
            rows=rows,
            unit_width=unit_width,
            unit_height=unit_height,
            save_quality=save_quality,
        )
        start = group[0].timestamp
        end = group[-1].timestamp
        grids.append(
            FrameGridInfo(
                index=len(grids),
                start=start,
                end=end,
                timestamp_text=f"{seconds_to_timestamp(start)} - {seconds_to_timestamp(end)}",
                path=str(grid_path),
                keyframes=group,
            )
        )
    return grids


def compose_grid_image(
    keyframes: list[KeyframeInfo],
    output_path: Path,
    *,
    cols: int,
    rows: int,
    unit_width: int,
    unit_height: int,
    save_quality: int,
) -> None:
    grid_img = Image.new("RGB", (unit_width * cols, unit_height * rows), (255, 255, 255))
    font = ImageFont.load_default()

    for offset, frame in enumerate(keyframes[: cols * rows]):
        if not frame.path:
            continue
        image = Image.open(frame.path).convert("RGB").resize((unit_width, unit_height), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), frame.timestamp_text, fill="yellow", font=font, stroke_width=1, stroke_fill="black")
        x = (offset % cols) * unit_width
        y = (offset // cols) * unit_height
        grid_img.paste(image, (x, y))

    grid_img.save(output_path, quality=save_quality)


def run_command(command: list[str]) -> None:
    process = subprocess.run(command, capture_output=True, text=True, check=False, timeout=get_settings().yt_dlp_timeout_seconds)
    if process.returncode != 0:
        stderr = (process.stderr or process.stdout or "").strip()
        raise MediaError(stderr or f"Command failed: {' '.join(command)}")
