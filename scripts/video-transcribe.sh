#!/usr/bin/env bash
# B 站视频转写：URL/BV 号 → 元数据 + 音频下载 + whisper 文字稿
# 用法: video-transcribe.sh <视频URL或BV号> [输出前缀，默认 /tmp/bilibili_<BV>]
# 依赖: curl / yt-dlp（Chrome 需登录过 B 站）/ uvx（mlx-whisper，Apple Silicon）
# 产物: <前缀>.txt（逐行转写稿）；stdout 打印 aid/cid/title 等 iframe 参数
set -euo pipefail

INPUT="${1:?用法: $0 <bilibili视频URL或BV号> [输出前缀]}"
BV=$(echo "$INPUT" | grep -oE 'BV[0-9A-Za-z]+' | head -1)
[ -n "$BV" ] || { echo "[error] 无法从输入提取 BV 号: $INPUT" >&2; exit 1; }
URL="https://www.bilibili.com/video/$BV/"
PREFIX="${2:-/tmp/bilibili_${BV}}"

# ── 1. 元数据（aid/cid 供 iframe 使用）──────────────────────────
META_JSON=$(curl -s "https://api.bilibili.com/x/web-interface/view?bvid=$BV" -H "User-Agent: Mozilla/5.0")
echo "$META_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)['data']
print(f\"[meta] bvid={d['bvid']} aid={d['aid']} cid={d['cid']} duration={d['duration']}s\")
print(f\"[meta] title={d['title']} owner={d['owner']['name']}\")
" || { echo "[error] 获取视频信息失败（视频不存在或网络问题）" >&2; exit 1; }

# ── 2. 音频下载（已有则跳过）───────────────────────────────────
if [ ! -f "$PREFIX.m4a" ]; then
  echo "[dl] 下载音频 → $PREFIX.m4a"
  yt-dlp --no-update --cookies-from-browser chrome -f "ba[ext=m4a]/ba" -x --audio-format m4a -o "$PREFIX.%(ext)s" "$URL" >&2
else
  echo "[dl] 音频已存在，跳过: $PREFIX.m4a"
fi

# ── 3. whisper 转写（已有则跳过）───────────────────────────────
# 网络要点：pypi 走清华镜像且绕过系统代理；HF 模型走 hf-mirror.com
if [ ! -f "$PREFIX.txt" ]; then
  echo "[stt] whisper-large-v3-turbo 转写中（约视频时长的 1/8）..."
  NO_PROXY='*' no_proxy='*' HF_ENDPOINT=https://hf-mirror.com \
    uvx --system-certs --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --from mlx-whisper mlx_whisper \
    --model mlx-community/whisper-large-v3-turbo --language zh \
    --output-dir "$(dirname "$PREFIX")" --output-format txt "$(cd "$(dirname "$PREFIX")" && pwd)/$(basename "$PREFIX").m4a" >&2
else
  echo "[stt] 转写稿已存在，跳过: $PREFIX.txt"
fi

LINES=$(wc -l < "$PREFIX.txt" | tr -d ' ')
echo "[done] 文字稿: $PREFIX.txt（$LINES 行）"
