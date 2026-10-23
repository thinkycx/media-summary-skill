#!/usr/bin/env python3
"""Media transcription: download, extract audio, transcribe with faster-whisper."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse


def load_config():
    config_path = os.path.expanduser("~/.config/media-summary/config.json")
    defaults = {
        "whisper_model": "base",
        "language": "zh",
        "device": "auto",
        "compute_type": "auto",
        "download_tool": "axel",
        "temp_dir": "/tmp/media-summary",
        "keep_temp_files": False,
        "vad_filter": True,
    }
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            user_config = json.load(f)
        defaults.update(user_config)
    return defaults


def is_url(path):
    return path.startswith("http://") or path.startswith("https://")


def is_audio_file(path):
    audio_exts = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".wma"}
    return os.path.splitext(path)[1].lower() in audio_exts


def is_platform_url(url):
    """Check if URL is from a video platform that requires special downloaders."""
    platform_hosts = [
        "bilibili.com", "www.bilibili.com", "b23.tv",
        "youtube.com", "www.youtube.com", "youtu.be",
        "douyin.com", "www.douyin.com",
        "ixigua.com", "www.ixigua.com",
    ]
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    return any(host == h or host.endswith("." + h) for h in platform_hosts)


def download_platform_video(url, output_dir):
    """Download video from platforms (Bilibili, YouTube, etc.) using you-get or yt-dlp."""
    out_file = os.path.join(output_dir, "platform_video.mp4")

    print(f"[平台下载] {url}", file=sys.stderr)

    # Try yt-dlp first (more robust)
    if shutil.which("yt-dlp"):
        print("[使用 yt-dlp]", file=sys.stderr)
        result = subprocess.run(
            ["yt-dlp", "-f", "worst[ext=mp4]/worst", "-o", out_file, url],
            capture_output=True, text=True, timeout=600
        )
        if result.returncode == 0 and os.path.exists(out_file) and os.path.getsize(out_file) > 0:
            size_mb = os.path.getsize(out_file) / (1024 * 1024)
            print(f"[下载完成] {size_mb:.1f} MB", file=sys.stderr)
            return out_file

    # Fallback to you-get
    if shutil.which("you-get"):
        print("[使用 you-get]", file=sys.stderr)
        result = subprocess.run(
            ["you-get", "-o", output_dir, "-O", "platform_video", url],
            capture_output=True, text=True, timeout=600
        )
        if result.returncode == 0:
            # you-get may produce different extensions, find the file
            import glob
            candidates = glob.glob(os.path.join(output_dir, "platform_video.*"))
            video_exts = {".mp4", ".mkv", ".flv", ".webm", ".avi", ".mov"}
            for f in candidates:
                if os.path.splitext(f)[1].lower() in video_exts and os.path.getsize(f) > 0:
                    size_mb = os.path.getsize(f) / (1024 * 1024)
                    print(f"[下载完成] {size_mb:.1f} MB", file=sys.stderr)
                    return f

    raise RuntimeError(
        f"Platform video download failed. Install yt-dlp (pip install yt-dlp) "
        f"or you-get (pip install you-get) to download from this platform."
    )


def validate_media_file(file_path):
    """Validate downloaded file is a valid media file using ffprobe."""
    if not shutil.which("ffprobe"):
        return True  # Skip validation if ffprobe not available

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", file_path],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        return False
    try:
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        return duration > 0
    except (json.JSONDecodeError, ValueError):
        return False


def download_media(url, output_dir, tool="axel"):
    """Download media file from URL. Returns local file path."""
    # Route platform URLs to specialized downloaders
    if is_platform_url(url):
        return download_platform_video(url, output_dir)

    parsed = urllib.parse.urlparse(url)
    filename = os.path.basename(parsed.path) or "downloaded_media"
    out_file = os.path.join(output_dir, filename)

    print(f"[下载] {url}", file=sys.stderr)

    if tool == "axel" and shutil.which("axel"):
        result = subprocess.run(
            ["axel", "-n", "4", "-o", out_file, url],
            capture_output=True, text=True, timeout=600
        )
        if result.returncode != 0:
            raise RuntimeError(f"axel download failed: {result.stderr}")
    elif shutil.which("curl"):
        result = subprocess.run(
            ["curl", "-L", "-o", out_file, url],
            capture_output=True, text=True, timeout=600
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl download failed: {result.stderr}")
    else:
        raise RuntimeError("Neither axel nor curl found. Install one of them.")

    if not os.path.exists(out_file) or os.path.getsize(out_file) == 0:
        raise RuntimeError(f"Download produced empty or missing file: {out_file}")

    # Validate the downloaded file is valid media
    if not validate_media_file(out_file):
        raise RuntimeError(
            f"Downloaded file is not valid media: {out_file}. "
            f"The URL may require a specialized downloader (yt-dlp or you-get)."
        )

    size_mb = os.path.getsize(out_file) / (1024 * 1024)
    print(f"[下载完成] {size_mb:.1f} MB", file=sys.stderr)
    return out_file


def extract_audio(video_path, output_path):
    """Extract audio from video as 16kHz mono WAV."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found. Install it: brew install ffmpeg")

    print(f"[提取音频] {os.path.basename(video_path)}", file=sys.stderr)

    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            output_path
        ],
        capture_output=True, text=True, timeout=600
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")

    if not os.path.exists(output_path):
        raise RuntimeError("Audio extraction produced no output file")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[音频就绪] {size_mb:.1f} MB", file=sys.stderr)
    return output_path


def get_media_info(file_path):
    """Get duration and format info via ffprobe."""
    if not shutil.which("ffprobe"):
        return None

    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size,format_name",
            "-of", "json",
            file_path
        ],
        capture_output=True, text=True, timeout=10
    )

    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            return {
                "duration": float(fmt.get("duration", 0)),
                "size_bytes": int(fmt.get("size", 0)),
                "format": fmt.get("format_name", "unknown"),
            }
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    return None


def transcribe_audio(audio_path, model_name="base", language="zh", device="auto",
                     compute_type="auto", vad_filter=True):
    """Transcribe audio file using faster-whisper. Returns (text, duration, segments_data)."""
    from faster_whisper import WhisperModel

    print(f"[加载模型] whisper-{model_name}", file=sys.stderr)
    model = WhisperModel(model_name, device=device, compute_type=compute_type)

    segments, info = model.transcribe(
        audio_path,
        language=language,
        vad_filter=vad_filter,
    )

    duration = info.duration
    print(f"[转写中] 语言={info.language}, 时长={duration:.1f}s", file=sys.stderr)

    # OpenCC for Traditional→Simplified Chinese
    cc = None
    if language == "zh":
        try:
            from opencc import OpenCC
            cc = OpenCC("t2s")
        except ImportError:
            pass

    LOW_CONFIDENCE_THRESHOLD = -0.8

    text_parts = []
    segments_data = []
    low_conf_count = 0
    total_logprob_sum = 0.0
    total_segments = 0

    for segment in segments:
        seg_text = segment.text
        if cc:
            seg_text = cc.convert(seg_text)

        avg_logprob = segment.avg_logprob
        no_speech_prob = segment.no_speech_prob
        is_low_conf = avg_logprob < LOW_CONFIDENCE_THRESHOLD

        if is_low_conf:
            low_conf_count += 1
            text_parts.append(f"{seg_text}[?]")
        else:
            text_parts.append(seg_text)

        segments_data.append({
            "start": round(segment.start, 1),
            "end": round(segment.end, 1),
            "text": seg_text,
            "avg_logprob": round(avg_logprob, 3),
            "no_speech_prob": round(no_speech_prob, 3),
            "low_confidence": is_low_conf,
        })

        total_logprob_sum += avg_logprob
        total_segments += 1

    text = "".join(text_parts)
    avg_confidence = total_logprob_sum / total_segments if total_segments > 0 else 0

    print(f"[转写完成] {len(text)} 字符, {total_segments} 片段, "
          f"平均logprob={avg_confidence:.3f}, 低置信片段={low_conf_count}",
          file=sys.stderr)

    return text, duration, {
        "segments": segments_data,
        "total_segments": total_segments,
        "low_confidence_count": low_conf_count,
        "avg_logprob": round(avg_confidence, 3),
    }


def main():
    parser = argparse.ArgumentParser(description="媒体转写工具")
    parser.add_argument("input", help="视频/音频文件路径或 URL")
    parser.add_argument("--model", help="Whisper 模型 (tiny/base/small/medium/large-v3)")
    parser.add_argument("--language", help="转写语言 (zh/en/ja/...)")
    parser.add_argument("--device", help="计算设备 (auto/cpu/cuda)")
    parser.add_argument("--compute-type", help="计算精度 (auto/int8/float16)")
    parser.add_argument("--keep", action="store_true", help="保留临时文件")
    parser.add_argument("--summary", action="store_true", help="输出时附带元信息 header")
    parser.add_argument("--info-only", action="store_true", help="只输出媒体信息，不转写")
    parser.add_argument("--no-vad", action="store_true",
                        help="关掉 VAD 语音活动检测（音乐/歌唱内容被误滤成空结果时用）")
    args = parser.parse_args()

    config = load_config()

    # Override config with CLI args
    model_name = args.model or config["whisper_model"]
    language = args.language or config["language"]
    device = args.device or config["device"]
    compute_type = args.compute_type or config["compute_type"]
    download_tool = config["download_tool"]
    temp_dir = config["temp_dir"]
    keep = args.keep or config["keep_temp_files"]
    vad_filter = config.get("vad_filter", True) and not args.no_vad

    os.makedirs(temp_dir, exist_ok=True)
    work_dir = tempfile.mkdtemp(dir=temp_dir)

    try:
        # Resolve input to a local file
        input_path = args.input

        if is_url(input_path):
            input_path = download_media(input_path, work_dir, tool=download_tool)

        if not os.path.exists(input_path):
            print(f"Error: file not found: {input_path}", file=sys.stderr)
            sys.exit(1)

        # Info only mode
        if args.info_only:
            info = get_media_info(input_path)
            if info:
                print(json.dumps(info, indent=2))
            else:
                print("Unable to get media info", file=sys.stderr)
                sys.exit(1)
            return

        # Determine if we need audio extraction
        if is_audio_file(input_path):
            audio_path = input_path
        else:
            audio_path = os.path.join(work_dir, "audio.wav")
            extract_audio(input_path, audio_path)

        # Transcribe
        text, duration, quality_info = transcribe_audio(
            audio_path,
            model_name=model_name,
            language=language,
            device=device,
            compute_type=compute_type,
            vad_filter=vad_filter,
        )

        # 空结果保护（2026-10-23）：VAD 把音乐/歌唱段滤光时静默输出空串——
        # 显式报错并给出 --no-vad 提示，避免下游拿空转写稿继续跑
        if not text.strip():
            print("Error: 转写结果为空（0 字符）。若内容含大量音乐/歌唱，"
                  "VAD 可能把非纯语音段全部滤除，请加 --no-vad 重试。",
                  file=sys.stderr)
            sys.exit(2)

        # Output
        if args.summary:
            print(f"---")
            print(f"source: {args.input}")
            print(f"duration: {duration:.1f}s ({duration/60:.1f}min)")
            print(f"model: whisper-{model_name}")
            print(f"language: {language}")
            print(f"characters: {len(text)}")
            print(f"avg_logprob: {quality_info['avg_logprob']}")
            print(f"low_confidence_segments: {quality_info['low_confidence_count']}/{quality_info['total_segments']}")
            if quality_info['low_confidence_count'] > 0:
                print(f"quality_warning: 存在低置信度片段（标记为[?]），建议用更大模型重新转写")
            print(f"---")
            print()

        print(text)

    finally:
        if not keep and os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
