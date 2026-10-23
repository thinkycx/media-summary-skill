---
name: media-summary-2.0.0
description: >
  视频/音频媒体转写与结构化总结工具。下载视频/音频，提取音频，用 faster-whisper 本地转写为文字，
  产出结构化总结（元数据/核心结论/内容结构/原文引用/完整文字版）。
  只管"媒体→结构化内容"，不管文章组织格式（笔记格式由 ai-notes 的 styles/video-summary.md 定义）。
  Triggers: "总结视频", "总结音频", "视频总结", "音频总结", "transcribe video", "summarize video", "summarize audio", "媒体总结", "转写视频", "转写音频", "video summary", "audio summary", "听一下这个", "帮我听", "这个视频讲了什么", "帮我看看这个视频".
  NOT for: 文本文件总结、PDF总结、图片识别、视频编辑、音频编辑、笔记发布流程（用 ai-notes）.
---

# Media Summary - 视频/音频转写与结构化总结

本地转写视频/音频为文字，产出与呈现无关的结构化总结内容。

## Config

配置文件：`~/.config/media-summary/config.json`

```json
{
  "whisper_model": "base",
  "language": "zh",
  "device": "auto",
  "compute_type": "auto",
  "download_tool": "axel",
  "temp_dir": "/tmp/media-summary",
  "keep_temp_files": false
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| whisper_model | Whisper 模型大小 (tiny/base/small/medium/large-v3) | base |
| language | 转写语言 | zh |
| device | 计算设备 (auto/cpu/cuda) | auto |
| compute_type | 计算精度 (auto/int8/float16/float32) | auto |
| download_tool | 下载工具 (axel/curl) | axel |
| temp_dir | 临时文件目录 | /tmp/media-summary |
| keep_temp_files | 是否保留临时文件 | false |

## Script Location

```
~/.claude/skills/media-summary-2.0.0/scripts/media-summary.sh
```

## Workflow

### 初始化（首次使用）

```bash
bash ~/.claude/skills/media-summary-2.0.0/scripts/media-summary.sh init
```

### 转写视频/音频

```bash
# 视频 URL（B站/YouTube 等平台自动用 yt-dlp/you-get 下载）
bash ~/.claude/skills/media-summary-2.0.0/scripts/media-summary.sh transcribe "https://www.bilibili.com/video/BVxxxx"

# 本地文件 / 指定模型和语言 / 带质量元信息
bash ~/.claude/skills/media-summary-2.0.0/scripts/media-summary.sh transcribe /path/to/video.mp4
bash ~/.claude/skills/media-summary-2.0.0/scripts/media-summary.sh transcribe --model small --language en "URL"
bash ~/.claude/skills/media-summary-2.0.0/scripts/media-summary.sh transcribe --summary "URL"
# 需要段落时间戳（写 video-seek 跳转 chips 必用）：--segments 追加 JSONL（start/end/text）
bash ~/.claude/skills/media-summary-2.0.0/scripts/media-summary.sh transcribe --segments "URL"
```

## 定位与分工

本 skill 是**工具层**：媒体 → 结构化内容。只负责下载、转写、质量元信息和结构化总结产物，**不规定最终文章的组织格式**（四部分结构、采访 QA 形式、折叠、文件名、标签等呈现层要求由消费方定义）。

| 消费方 | 格式权威 |
|---|---|
| 写入 ai-notes 笔记 | ai-notes 的 `styles/video-summary.md`（视频总结笔记格式，含采访类 QA 变体） |
| 直接对话回复 | 无格式约束，按用户要求组织 |

本 skill 自带两条转写管线，按场景选择：

| 脚本 | 引擎 | 适用 |
|---|---|---|
| `scripts/media-summary.sh` | faster-whisper（CPU） | 多平台（YouTube/抖音/西瓜）、本地文件、需要质量元信息（置信度/低置信片段，`--summary`） |
| `scripts/video-transcribe.sh` | mlx-whisper large-v3-turbo（Apple Silicon GPU，约 8× 快） | B 站专用：cookies 下载绕反爬、幂等可重跑、stdout 直接吐 aid/cid 供 iframe 使用 |

## 结构化输出规范（总结产物）

转写后 Claude 产出的**结构化总结**应包含以下要素（呈现形式由消费方决定）：

1. **元数据** — 标题、来源、时长、作者、语言、转写模型、字符数、平均置信度、低置信片段数
2. **核心结论** — 3~5 条最重要观点（金字塔：一句话一条，数据支撑）
3. **内容结构** — 按视频自身逻辑组织：
   - 课程/演讲类：章节划分 + 每章要点 + 关键推导/案例/数据
   - **采访/对话类**：按"问 → 答"组织，答保留原汁原味表达（语气、比喻、口头禅），不提炼成干巴要点
   - **英文内容**：翻译以中文表达为主，专有名词/产品名保留英文，避免中英混杂的句子
4. **原文引用** — 从转写原文直接摘录的金句/关键原话（采访类按 QA 组织：问可转述，答必须逐字）
5. **原视频文字版** — 完整转写稿（作为附录交给消费方，消费方决定折叠/展示方式）

**质量原则**（任何消费方下都必须遵守）：

- 转写原文必须**直接引用不改写**；推测修正须标注 `[原文: xxx → 推测: yyy]`
- 引用时保留 `[?]` 低置信标记；`low_confidence_segments > 0` 时在总结开头提示置信度风险
- 区分"事实"（视频原话/数据）与"判断"（AI 推断），判断需显式标注
- 转写元信息注明在产物头部，便于回溯质量

## Rules

1. 使用前必须先运行 `init` 确认依赖已安装
2. `transcribe` 只负责转写，不做总结 —— 总结由 Claude 按上述格式完成
3. 总结时必须使用 `--summary` 参数，以获取质量元信息（置信度、低置信片段数）
4. 转写文字超过 8000 字时提醒用户，仍进行完整总结
5. URL 下载的临时文件默认自动清理，加 `--keep` 可保留

## Common Traps

- **依赖版本必须钉死（2026-10-23 实测）**：`pip install faster-whisper==1.1.1` +
  `av==14.0.0` **+ `requests`**（faster-whisper 1.1.1 未声明 requests 但运行时直接
  import，干净环境必踩；faster-whisper 1.2.1 + av 19.x 不兼容：`av.open()` 已删
  `metadata_errors` 参数）。ffmpeg/yt-dlp/you-get 走 brew 或 pip 均可
- **音乐/MV 内容转写为空**：默认开 VAD（Silero 把歌唱段当非语音滤掉），音乐 MV 会得到
  0 字符结果——脚本现在会显式报错退出（exit 2），此时加 `--no-vad` 重试
- **模型下载（国内网络）**：huggingface.co / hf-mirror.com 都可能不可达——用 ModelScope：
  `pip install modelscope && modelscope download --local_dir ./whisper-base
  pengzhendong/faster-whisper-base`，然后 `--model ./whisper-base`（本地路径直接支持）
- **B 站下载通道**：yt-dlp 常被 412 反爬拦截（加 UA/referer 无效）——先 you-get：
  `you-get -o <dir> <url>`（下载视频后脚本自动提取音频）；axel/curl 直链只会得到 HTML
- 长视频（>1小时）转写耗时较长，base 模型约 1:10（1 分钟处理 10 分钟音频）；small 模型更准但更慢
- **语言判断**：中文页面 ≠ 中文内容（如央视专访马斯克实为英文），强制错误语言会产生大量幻觉乱码——发现乱码/大量低置信片段时改用 `--language en` 或 auto 重转
- Apple Silicon 上 device=auto 使用 CPU（不支持 CUDA），仍然较快
- 低置信片段（`[?]`）常见于专有名词、品牌名、技术术语
- **PATH 陷阱**：多 python 共存（系统 3.9 / brew / pyenv）时脚本里的 `python3` 可能解析到
  没有 faster-whisper 的解释器——统一用一个解释器装依赖并在同一 PATH 下运行
