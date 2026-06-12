#!/bin/bash
# 部门版日报（团队视角，prompt 不入库），与个人版并行、状态隔离。
# 由 daily_brief.sh 在个人版跑完后链式调用（复用其 raw 缓存），也可手动单独跑。
# 产物：data/dept_daily/{date}/{date}_daily.md（gitignored）+ 钉钉推送（标「部门版试运行」）
set -uo pipefail
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:$PATH"

REPO="$HOME/ai-frontier-insight"
PY="$REPO/venv/bin/python"
DATE=$(date +%Y-%m-%d)
mkdir -p "$REPO/logs"
LOG="$REPO/logs/dept-$DATE.log"
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

cd "$REPO" || exit 1
[ -f .env ] && { set -a; source .env; set +a; }

# 关键：dept profile —— prompts/dept/ + memory_dept/，与个人版完全隔离
export PIPELINE_PROFILE=dept

log "===== 部门版日报 ($DATE) ====="

# 代理探测（仅在缓存缺失需要兜底自采时才用得上）
PROXY_PORT="${PROXY_PORT:-13659}"
if nc -z -G2 127.0.0.1 "$PROXY_PORT" 2>/dev/null; then
    P="socks5h://127.0.0.1:$PROXY_PORT"
    export ALL_PROXY="$P" HTTPS_PROXY="$P" HTTP_PROXY="$P"
    export all_proxy="$P" https_proxy="$P" http_proxy="$P"
    log "检测到 SOCKS 代理 :${PROXY_PORT}"
fi

"$PY" -m src.main dept-daily >> "$LOG" 2>&1
RC=$?
if [ "$RC" -ne 0 ]; then log "dept-daily 失败 exit=$RC"; exit "$RC"; fi

log "推送钉钉（部门版试运行）..."
"$PY" scripts/push_dingtalk.py --dept >> "$LOG" 2>&1 || log "部门版钉钉推送失败（产物仍在本地）"

log "===== 完成，产物在 data/dept_daily/$DATE/ ====="
find "$REPO/logs" -name "dept-*.log" -mtime +14 -delete 2>/dev/null || true
