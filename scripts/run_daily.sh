#!/bin/bash
# AI Frontier Insight Bot — 每日流水线
# 由 launchd 定时调用：先采集+分析，等到发送时间后推送
#
# 时间线（以 send_hour=8:00 为例）：
#   07:30  launchd 触发本脚本
#   07:30  采集 + AI 分析（约 3-5 分钟）
#   07:35  等待到 08:00
#   08:00  发送日报到 webhook

set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/daily-$(date +%Y-%m-%d).log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "========== Daily Pipeline 开始 =========="

# 加载环境变量（API keys）
ENV_FILE="$DIR/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
    log "已加载 .env"
else
    log "[!] 未找到 .env 文件，请确保环境变量已设置"
    exit 1
fi

# Step 1: 采集 + 分析
log "Step 1: 采集 + 分析..."
if /usr/bin/python3 -m src.main daily >> "$LOG" 2>&1; then
    log "采集分析完成"
else
    log "[!] 采集分析失败"
    exit 1
fi

# Step 2: 等待到发送时间
SEND_HOUR=$(/usr/bin/python3 -c "
import yaml
cfg = yaml.safe_load(open('$DIR/config/settings.yaml'))
print(cfg['schedule']['daily']['send_hour'])
")
SEND_MIN=$(/usr/bin/python3 -c "
import yaml
cfg = yaml.safe_load(open('$DIR/config/settings.yaml'))
print(cfg['schedule']['daily'].get('send_minute', 0))
")

# 计算目标时间戳
TARGET=$(date -j -f "%H:%M" "${SEND_HOUR}:$(printf '%02d' $SEND_MIN)" "+%s" 2>/dev/null || echo "0")
NOW=$(date "+%s")

if [ "$TARGET" -gt "$NOW" ]; then
    WAIT=$((TARGET - NOW))
    log "Step 2: 等待 ${WAIT} 秒到 ${SEND_HOUR}:$(printf '%02d' $SEND_MIN) 发送..."
    sleep "$WAIT"
else
    log "Step 2: 已过发送时间，立即发送"
fi

# Step 3: 发送
log "Step 3: 发送日报..."
if /usr/bin/python3 -m src.main send-daily >> "$LOG" 2>&1; then
    log "发送完成"
else
    log "[!] 发送失败"
    exit 1
fi

# Step 4: 提交 draft 和 memory 到 git
log "Step 4: 提交到 Git..."
cd "$DIR"
/usr/bin/git add config/drafts/ memory/ 2>/dev/null || true
if ! /usr/bin/git diff --cached --quiet 2>/dev/null; then
    /usr/bin/git commit -m "daily: $(date +%Y-%m-%d) brief"
    /usr/bin/git push
    log "Git 提交推送完成"
else
    log "无变更需要提交"
fi

# 清理 7 天前的日志
find "$LOG_DIR" -name "daily-*.log" -mtime +7 -delete 2>/dev/null || true

log "========== Daily Pipeline 结束 =========="
