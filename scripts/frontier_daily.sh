#!/bin/bash
# AI 前沿日报 · headless Claude 全链路（个人版 + 部门版）
# 采集走 Python（src.main collect），分析/筛选/洞察/发布走 headless claude（读 prompts/auto/daily_run.md，不再用 DeepSeek）。
# 由 launchd 触发。
#
# 环境变量：
#   FRONTIER_MODE=generate-only|full   默认 full。generate-only=不 git push、不推任何钉钉（试跑用）。
#   SKIP_COLLECT=1                     复用已有 raw_cache，不重新采集（试跑与旧链路并存时用）。
#
# 两个代理（都是本机 GUI 代理，按需起）：
#   - 7897 HTTP  → claude 访问 Anthropic API 必须走它（硬依赖，挂了整条链失败）
#   - 13659 SOCKS → 采集 HF/Reddit 走它（可选，没开则降级直连）
# 注意：采集的 SOCKS 代理只在 collect 子进程内生效，绝不能泄漏进 claude 调用。
set -uo pipefail
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

REPO="$HOME/ai-frontier-insight"
PY="$REPO/venv/bin/python"
CLAUDE_BIN="$HOME/.local/bin/claude"
CLAUDE_PROXY="http://127.0.0.1:7897"      # claude→Anthropic API 走的 HTTP 代理（与采集的 SOCKS 分开）
DATE=$(date +%Y-%m-%d)
MODE="${FRONTIER_MODE:-full}"
mkdir -p "$REPO/logs"
LOG="$REPO/logs/auto-$DATE.log"
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

cd "$REPO" || exit 1
[ -f .env ] && { set -a; source .env; set +a; }

log "===== 自动日报 ($DATE) MODE=$MODE ====="

# --- 1. 采集（纯 Python，SOCKS 代理仅在此子进程内生效，不外泄）---
if [ "${SKIP_COLLECT:-0}" = "1" ] && [ -f "$REPO/data/raw_cache/$DATE.json" ]; then
    log "复用已有 raw_cache（SKIP_COLLECT=1）"
else
    PROXY_PORT="${PROXY_PORT:-13659}"
    COLLECT_PROXY=""
    if nc -z -G2 127.0.0.1 "$PROXY_PORT" 2>/dev/null; then
        COLLECT_PROXY="socks5h://127.0.0.1:$PROXY_PORT"
        log "采集代理 on :$PROXY_PORT（HF/Reddit 可用）"
    else
        log "采集代理 off（直连降级，HF/Reddit 可能拿不到，不影响其它源）"
    fi
    log "采集中..."
    # 代理 env 仅传给这一条命令，不 export 到全局（避免泄漏进 claude）
    env ALL_PROXY="$COLLECT_PROXY" HTTPS_PROXY="$COLLECT_PROXY" HTTP_PROXY="$COLLECT_PROXY" \
        all_proxy="$COLLECT_PROXY" https_proxy="$COLLECT_PROXY" http_proxy="$COLLECT_PROXY" \
        "$PY" -m src.main collect >> "$LOG" 2>&1
    RC=$?
    if [ "$RC" -ne 0 ]; then log "采集失败 exit=$RC，终止"; exit "$RC"; fi
fi

# --- 2. headless claude：分析两版 + 发布 ---
MODE_NOTE=""
if [ "$MODE" = "generate-only" ]; then
    MODE_NOTE="【本次为 GENERATE-ONLY 试跑】完成分析与本地产出、可写语雀文档（便于人工审阅），但绝对不要 git push、不要推送任何钉钉消息（个人版全文与部门版头条都不推）。"
fi

PROMPT="按 $REPO/prompts/auto/daily_run.md 的指令，为日期 $DATE 跑完整每日日报：个人版 + 部门版。先读该指令文件，再读 data/raw_cache/$DATE.json，然后执行两版的筛选/排序/洞察与发布。${MODE_NOTE} 完成后用一句话汇报每版结果（成功/失败/语雀链接）。若遇到自己无法解决的结构性错误（skylark/语雀鉴权过期、代码 bug、API key 失效、网络全断等），用蚂蚁钉单聊 MCP sendSingleChatCardMessage 把简短故障报告私信给用户（衹月）后再退出，不要强行半推。"

# 探测 claude 的 HTTP 代理是否在（claude 硬依赖它）
if ! nc -z -G2 127.0.0.1 7897 2>/dev/null; then
    log "⚠️ claude 代理 7897 未开，Anthropic API 不可达——本次很可能失败（需人工起代理）"
fi

log "唤起 headless claude（permission=bypass）..."
env HTTP_PROXY="$CLAUDE_PROXY" HTTPS_PROXY="$CLAUDE_PROXY" NO_PROXY="localhost,127.0.0.1" \
    "$CLAUDE_BIN" -p "$PROMPT" \
    --permission-mode bypassPermissions \
    --add-dir "$REPO" \
    >> "$LOG" 2>&1
RC=$?
if [ "$RC" -ne 0 ]; then
    log "❌ claude 运行 exit=$RC（详见本日志，必要时人工介入）"
else
    log "✅ claude 运行结束 exit=0"
fi

find "$REPO/logs" -name "auto-*.log" -mtime +14 -delete 2>/dev/null || true
log "===== 完成 MODE=$MODE ====="
