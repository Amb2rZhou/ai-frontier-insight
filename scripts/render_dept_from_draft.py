#!/usr/bin/env python3
# 从 draft_signals.json 渲染部门版 yuque_body.md（发布语雀用）。趋势总结从外部文件读入。
import json, sys, os

date = sys.argv[1] if len(sys.argv) > 1 else "2026-07-03"
base = os.path.expanduser(f"~/ai-frontier-insight/data/dept_daily/{date}")
draft = json.load(open(f"{base}/draft_signals.json"))
sigs = draft["signals"]

INTRO = ("> 本简报以「与团队关注面相关性 × 重要性」双门槛筛选，面向部门：把每日 AI 动态当作新业态、"
         "新模式的先导信号来读，落到 Agent Builder / 模型服务 / 数据标注中心 / 知识库（RAG）/ 评测 / "
         "私有化部署 / 桌面AI助手 等真实能力上。本简报依赖 Claude Code 自动化生成，选题、视角反馈请找衹月。")

lines = [INTRO, "", f"## 一、今日精选 {len(sigs)} 条", ""]
for s in sigs:
    src = s["sources"][0]
    title = s["title"]
    url = src["url"]
    lines.append(f"### {s['rank']}. [{title}]({url})")
    lines.append("")
    lines.append(s["signal_text"])
    lines.append(f"- 💡 {s['insight']}")
    lines.append(f"- 👉 {s['implication']}")
    src_links = "、".join(f"[{x['name']}]({x['url']})" for x in s["sources"])
    lines.append(f"- 🔗 原文：{src_links}")
    lines.append("")

# 趋势总结（外部文件，每行一条要点）
trend_file = f"{base}/trend_points.txt"
lines.append("## 二、趋势总结")
lines.append("")
lines.append("今日核心趋势观察：")
if os.path.exists(trend_file):
    for t in open(trend_file):
        t = t.strip()
        if t:
            lines.append(f"- {t}")
lines.append("")
lines.append("---")
lines.append("*AI Frontier Insight Bot*")

body = "\n".join(lines)
open(f"{base}/yuque_body.md", "w").write(body)

# 自检：### 行数 == 链接数（每条一个标题链接）
h = sum(1 for l in lines if l.startswith("### "))
print(f"渲染完成：{len(sigs)} 条 | ### 标题行={h} | 输出 {base}/yuque_body.md")
