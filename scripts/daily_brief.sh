#!/bin/bash
# 每天一次：跑完整日报 → 推钉钉 → push 到 GitHub（更新个人网站）
# 由 launchd com.frontier.daily 每天 11:00 触发（在 x-monitor 10:45 抓取之后）
set -uo pipefail
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:$PATH"

REPO="$HOME/ai-frontier-insight"
PY="$REPO/venv/bin/python"
DATE=$(date +%Y-%m-%d)
mkdir -p "$REPO/logs"
LOG="$REPO/logs/daily-$DATE.log"
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

cd "$REPO" || exit 1
[ -f .env ] && { set -a; source .env; set +a; }

log "===== 每日日报 ($DATE) ====="

# 代理探测：SOCKS 代理开着就让采集走代理（HF/Reddit 才通），没开则直连（优雅降级）
PROXY_PORT="${PROXY_PORT:-13659}"
if nc -z -G2 127.0.0.1 "$PROXY_PORT" 2>/dev/null; then
    P="socks5h://127.0.0.1:$PROXY_PORT"
    export ALL_PROXY="$P" HTTPS_PROXY="$P" HTTP_PROXY="$P"
    export all_proxy="$P" https_proxy="$P" http_proxy="$P"
    log "检测到 SOCKS 代理 :${PROXY_PORT}，采集走代理（HF/Reddit 可用）"
else
    log "未检测到代理 :${PROXY_PORT}，采集走直连（HF/Reddit 可能拿不到，不影响其它源）"
fi

# 1. 完整日报：采集所有源 → DeepSeek 信号/洞察 → 写 markdown + Jekyll（不发 RedCity webhook）
log "运行 daily pipeline..."
"$PY" -m src.main daily >> "$LOG" 2>&1
RC=$?
if [ "$RC" -ne 0 ]; then log "daily 失败 exit=$RC，终止"; exit "$RC"; fi

# 2. 推送到钉钉（加签）
log "推送钉钉..."
"$PY" scripts/push_dingtalk.py >> "$LOG" 2>&1 || log "钉钉推送失败（不阻断后续）"

# 3. push 到 GitHub（含 x-monitor 数据 + 日报产物 + Jekyll 帖子 → 触发个人网站重建）
log "提交并推送..."
git pull --no-edit -q >> "$LOG" 2>&1 || log "git pull 告警（继续）"
git add -A
if git diff --cached --quiet; then
    log "无变更，跳过 push"
else
    git commit -q -m "daily: $DATE brief + x-monitor (auto)"
    git push >> "$LOG" 2>&1 && log "push 完成" || log "push 失败"
fi

find "$REPO/logs" -name "daily-*.log" -mtime +14 -delete 2>/dev/null || true
log "===== 完成 ====="
