#!/bin/bash
# 切换：把"试跑(generate-only)"正式上线为"全自动(full)"，并停掉旧的 DeepSeek 链路。
# 试跑稳定 1-2 天、确认产出无误后再执行。可逆（见末尾回滚说明）。
set -euo pipefail
LA="$HOME/Library/LaunchAgents"
OLD="$LA/com.frontier.daily.plist"
NEW="$LA/com.frontier.daily.v2.plist"

echo "== 1. 停用并卸载旧 DeepSeek 链路 com.frontier.daily =="
launchctl unload "$OLD" 2>/dev/null && echo "  旧任务已卸载" || echo "  旧任务未在运行（忽略）"
# 重命名旧 plist 为 .disabled，保留可回滚
[ -f "$OLD" ] && mv "$OLD" "$OLD.disabled" && echo "  旧 plist 备份为 $(basename "$OLD").disabled"

echo "== 2. 把 v2 改成 full 模式、11:00 触发 =="
launchctl unload "$NEW" 2>/dev/null || true
cat > "$NEW" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.frontier.daily.v2</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/amber/ai-frontier-insight/scripts/frontier_daily.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>11</integer><key>Minute</key><integer>0</integer></dict>
    <key>RunAtLoad</key><false/>
    <key>StandardOutPath</key><string>/Users/amber/ai-frontier-insight/logs/launchd-auto.out</string>
    <key>StandardErrorPath</key><string>/Users/amber/ai-frontier-insight/logs/launchd-auto.err</string>
</dict>
</plist>
PLIST
launchctl load "$NEW" && echo "  v2 已切 full 模式、11:00 触发并加载"

echo "== 完成 =="
launchctl list | grep frontier || true
echo
echo "回滚：mv $OLD.disabled $OLD && launchctl load $OLD ；并把 v2 改回 generate-only/11:40。"
