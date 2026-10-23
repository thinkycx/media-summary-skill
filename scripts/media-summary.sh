#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$SKILL_DIR/scripts"
CONFIG_DIR="$HOME/.config/media-summary"
CONFIG_FILE="$CONFIG_DIR/config.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*" >&2; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()   { err "$@"; exit 1; }

cmd_init() {
    info "Checking dependencies..."

    local missing=()

    # Check system deps
    if ! command -v ffmpeg &>/dev/null; then
        missing+=("ffmpeg (brew install ffmpeg)")
    fi
    if ! command -v ffprobe &>/dev/null; then
        missing+=("ffprobe (comes with ffmpeg)")
    fi
    if ! command -v python3 &>/dev/null; then
        missing+=("python3")
    fi

    # Check optional deps
    if ! command -v axel &>/dev/null; then
        warn "axel not found (brew install axel). Will use curl as fallback."
    fi

    # Check Python deps
    if ! python3 -c "import faster_whisper" 2>/dev/null; then
        missing+=("faster-whisper (pip install faster-whisper)")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        err "Missing dependencies:"
        for dep in "${missing[@]}"; do
            echo "  - $dep" >&2
        done
        echo "" >&2
        echo "Install all Python deps:" >&2
        echo "  pip install faster-whisper opencc-python-reimplemented" >&2
        exit 1
    fi

    # Create config
    if [ ! -f "$CONFIG_FILE" ]; then
        mkdir -p "$CONFIG_DIR"
        cp "$SKILL_DIR/references/config-example.json" "$CONFIG_FILE"
        info "Created config: $CONFIG_FILE"
    else
        info "Config already exists: $CONFIG_FILE"
    fi

    info "All dependencies OK!"
    info "Optional: opencc-python-reimplemented (pip install opencc-python-reimplemented) for Traditional→Simplified Chinese"
}

cmd_transcribe() {
    if [ $# -lt 1 ]; then
        die "Usage: media-summary.sh transcribe [options] <url_or_path>"
    fi

    # Pass all args to Python script
    python3 "$SCRIPT_DIR/transcribe.py" "$@"
}

cmd_info() {
    if [ $# -lt 1 ]; then
        die "Usage: media-summary.sh info <file_path>"
    fi

    python3 "$SCRIPT_DIR/transcribe.py" --info-only "$@"
}

cmd_help() {
    cat <<'EOF'
media-summary - 视频/音频转写工具

Usage:
  media-summary.sh <command> [options] [args]

Commands:
  init                    Check dependencies and create config
  transcribe <input>      Transcribe video/audio to text
  info <file>             Show media file info (duration, format)
  help                    Show this help

Transcribe Options:
  --model <name>          Whisper model (tiny/base/small/medium/large-v3)
  --language <code>       Language code (zh/en/ja/...)
  --device <dev>          Compute device (auto/cpu/cuda)
  --compute-type <type>   Precision (auto/int8/float16)
  --keep                  Keep temporary files
  --summary               Include metadata header in output

Examples:
  media-summary.sh transcribe "https://example.com/video.mp4"
  media-summary.sh transcribe --model medium --language en ./lecture.mp4
  media-summary.sh transcribe --summary ./podcast.mp3
  media-summary.sh info ./video.mp4
EOF
}

# Main dispatch
case "${1:-help}" in
    init)       shift; cmd_init "$@" ;;
    transcribe) shift; cmd_transcribe "$@" ;;
    info)       shift; cmd_info "$@" ;;
    help|--help|-h) cmd_help ;;
    *) die "Unknown command: $1. Run 'media-summary.sh help' for usage." ;;
esac
