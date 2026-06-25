## ⚠️ AI 前沿日报 · X 数据健康提示（6/25）

今日 X 数据**正常**：raw_cache 实采到 **101 条 twitter**，已照常入选出报。

但 `~/x-monitor/data/.health.json` 仍报 **softblock / tweet_count=0**（检查于 10:45，采集在 11:12 成功）。两者矛盾，**大概率是健康监控文件过期、未跟上当次成功采集**，非真实数据缺失。

供留意：若后续某天 twitter 真为 0，softblock 通常=代理出口疑似机房 IP 被 X 风控，建议 Clash 切住宅节点。今天无需处理，日报已正常生成。
