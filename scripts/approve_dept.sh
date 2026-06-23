#!/bin/bash
# 部门版"人工审批后一键推老板群"。
# 用法：bash scripts/approve_dept.sh [YYYY-MM-DD]   （不传日期=今天）
# 看过 webhook 发来的预览、确认 OK 后再跑这个；它把当天 headlines.md 推到老板 bot（DINGTALK_DEPT_WEBHOOK）。
set -euo pipefail
REPO="$HOME/ai-frontier-insight"
cd "$REPO"
DATE="${1:-$(date +%Y-%m-%d)}"
HL="data/dept_daily/$DATE/headlines.md"

if [ ! -f "$HL" ]; then
  echo "❌ 找不到当天头条：$HL（先确认部门版已生成）"; exit 1
fi

echo "== 审批推送：$DATE 部门版头条 → 老板群 =="
[ -f .env ] && { set -a; source .env; set +a; }
venv/bin/python scripts/push_dingtalk.py --dept --text-file "$HL"
echo "== 已推送（如上 errcode=0 即成功）=="
