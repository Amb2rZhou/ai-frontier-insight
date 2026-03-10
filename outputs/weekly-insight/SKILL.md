---
name: weekly-insight
description: "Generate a weekly AI deep insight report (AI Frontier Weekly Insight) from daily AI news digests and raw source data. Use this skill whenever the user mentions weekly report, weekly insight, AI周报, 周报, weekly summary of AI trends, or wants to synthesize daily AI news into strategic analysis. Also trigger when the user asks to analyze AI industry trends, write a deep dive on AI developments, or create a strategic briefing from collected AI news data. This skill focuses on trend analysis and strategic implications — not just news aggregation."
---

# AI Frontier Weekly Insight Generator

## Overview

This skill generates a weekly deep insight report for AI strategy teams. It reads structured daily brief data, X/Twitter monitoring data, and long-term memory (trends, historical predictions) from the `ai-frontier-insight` project, then synthesizes them into a strategic intelligence document.

The target audience is an internet/AI strategy team. The report delivers trend analysis and strategic implications — not just news recaps.

**Core principle: ONE trend, told well.** Each weekly report picks the single most important trend of the week and tells a complete, compelling story about it. The report is an essay with a thesis, not a template with slots to fill.

## Project Data Structure

The project root is the user's mounted folder. The key data locations:

```
ai-frontier-insight/
├── data/
│   ├── daily/{YYYY-MM-DD}/
│   │   ├── brief.json          ← Primary data source (signals + insights + trends)
│   │   └── sources.json        ← Raw source items (optional, for deep detail)
│   ├── weekly/                  ← Output directory for weekly reports
│   └── x-monitor/{YYYY-MM-DD}.json  ← Raw X/Twitter data (14-day retention)
├── memory/
│   ├── weekly_signals.json      ← Signals accumulated by week
│   ├── trends.json              ← Long-term trend tracking (up to 50 trends)
│   └── history_insights.json    ← Historical predictions archive
└── docs/
    └── weekly-report-skill-prompt.md  ← Full data schema reference
```

## Workflow

### Step 1: Determine Date Range

Figure out the week to cover. The weekly cycle is **last Tuesday → this Monday (inclusive, 7 days)**. For example, if today is Monday March 10, the report covers Tuesday March 4 through Monday March 10. Use the current date to calculate.

### Step 2: Read Source Data

**Two-pass reading strategy** to keep input volume manageable:

**Pass 1 — Always read (core inputs):**

1. **`data/daily/{date}/brief.json`** for each day in range — PRIMARY data source. Each contains:
   - `insights[]` — array of signals with `title`, `signal_text`, `signal_strength` (0-1), `insight`, `implication`, `category`, `sources[]`, `tags[]`
   - `trend_summary` — daily trend observations
   - `signal_count` and `raw_item_count`

2. **`memory/trends.json`** — long-term trend tracking. Each trend has `trajectory` (accelerating/stable/fading), `signal_count`, `weekly_counts[]`, and `key_events[]`.

3. **`memory/history_insights.json`** — past predictions for review.

4. **Previous week's report** — `data/weekly/{prev-year}-W{prev-week}.md`. Read for cross-week continuity: what trend was analyzed, what predictions were made, what threads can be continued.

**Pass 2 — On-demand only (DO NOT bulk-read):**

5. **`data/x-monitor/{date}.json`** — Raw X/Twitter data (~110KB each). Only read when a specific signal needs deeper context.

6. **`data/daily/{date}/sources.json`** — Raw source items. Only read when a specific signal needs deeper detail.

**Important data notes:**
- `signal_strength > 0.85` = the day's most important events
- Signals appearing on multiple days may have `[Update]` prefix — merge them
- `category` values: `model_release` | `research_breakthrough` | `strategic_move` | `ecosystem_shift` | `infrastructure` | `open_source` | `product_launch` | `model_benchmark`

### Step 3: Find the Story

**Do NOT start from a type/framework. Start from the data.**

Read all the signals, then ask: **What is the single most important thing that happened this week?** Not the most numerous category — the most *meaningful* pattern. Sometimes it's a single event with deep implications. Sometimes it's three unrelated signals that, when connected, reveal something nobody else has articulated.

The goal is to find a thesis — one sentence that captures what changed this week and why it matters. Examples of good theses:
- "AI产业正在经历一次'控制权迁移'——从人类实时操控到Agent后台自主执行"
- "本周三条独立研究线同时证明了同一件事：Agent的推理能力已经跨过了'辅助'到'自主'的门槛"
- "Anthropic用72小时证明了一件事：在AGI竞赛中，'安全'不是约束条件，而是竞争武器"

Bad theses (too broad, no point of view):
- "本周AI行业发生了很多重要事件"
- "Agent、安全、硬件三个方向都有进展"

Tell the user your thesis before writing. One sentence.

### Step 4: Deep Analysis & Fact-Check

Build the argument for your thesis:

- **Cross-day synthesis**: Connect signals across days into a narrative arc.
- **Trend context**: Use `memory/trends.json` to show whether this week's signals confirm, accelerate, or contradict existing trends.
- **Prediction validation**: Check `memory/history_insights.json` — did any past predictions get confirmed or invalidated?
- **Second-order thinking**: What are the non-obvious consequences?

**Fact-check all verifiable claims via web search** before writing.详细核查范围见下方"Fact-Check Requirement"一节。核查重点：
- 事件日期与时间线（搜索官方页面确认）
- 金额与技术参数（确认具体数字）
- 排他性声明——"第一个""唯一""最大"等（搜索确认无先例）
- 因果归因——确保有证据支撑，推测必须标注为推测
- 比较与程度——"史无前例""彻底改变"等需确认历史无类似先例
- 如果某项声明无法核实，加限定词或删除，不允许留在报告中

### Step 5: Write the Report

Write it like an essay, not a form. The structure below is a guideline, not a straitjacket — sections can be merged, reordered, or adjusted to serve the story.

```
# AI Frontier Weekly Insight

**主题：** [Your thesis — one sentence]
**类型：** [Post-hoc tag, freely generated based on content — not limited to fixed categories]
**日期：** YYYY.MM.DD - YYYY.MM.DD

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 核心摘要 Executive Summary
3-5 sentences. Lead with conclusion, not events. State the "so what" upfront.

## 深度分析 Deep Analysis
The core of the report (~50% of total length). This is where you make your argument.
Structure it however serves the thesis best — chronological, cause-and-effect, comparison, whatever works. Use subheadings if the argument has distinct parts, but don't force artificial structure.
Draw from trends.json trajectory data to support claims.
Inline-cite signals naturally in the narrative (e.g. "Anthropic拒绝五角大楼合同条款（详见信号1）") — the reader gets the full story here, and can jump to the appendix for sourced details.

## So What — 战略启示
What should the reader DO with this insight? Be specific and actionable.
Organized by audience (Builders / Investors / Companies) only if all three have distinct takeaways. Otherwise, just write the implications naturally.

## 预测与验证 Predictions & Review
1. Review past predictions against this week's evidence (if any exist).
2. Make 1-2 NEW predictions based on this week's thesis. Each with:
   - Qualitative confidence (高/中/低) + explicit reasoning basis
   - Specific timeframe

## 未来关注 Signals to Watch
2-3 forward-looking indicators. Each with verified dates where applicable.

## 本周信号 Key Signals（附录）
Moved to the END of the report as a factual reference appendix. NOT the narrative — the evidence base.
List the signals that support the thesis. Each signal: concise factual summary + source links.
Format: > 来源：[Source Name](url) · [Source Name 2](url2)
Readers who want sourced details come here; readers who only want the analysis can stop at "未来关注".
```

**About the 类型 tag:** This is a POST-HOC label, not a writing instruction. Write the report first, then generate a tag that best describes what you wrote. You are NOT limited to the four reference types (Research / Technology Trend / Company Strategy / Meta) — those are just examples. Create whatever label fits the content most accurately (e.g. "Geopolitics & Power", "Market Structure Shift", "Regulation", "Infrastructure", etc.). The tag helps readers and the memory system categorize the report — it should NOT influence how you write it.

### Step 6: Generate Output Files

Save to `data/weekly/`:
- `data/weekly/{year}-W{week}.md` — markdown report
- `data/weekly/{year}-W{week}.json` — structured JSON
- `data/weekly/{year}-W{week}.docx` — Word document (use docx skill patterns)

**One report per week. No reference reports.**

**Cross-week continuity**: When writing next week, read the previous week's report for context.

**Structured JSON schema:**

```json
{
  "week": "2026-W09",
  "date_range": "2026-02-23 ~ 2026-03-01",
  "generated_at": "ISO timestamp",
  "type_tag": "Meta",
  "theme": "Your thesis",
  "key_signals": [
    {
      "title": "...",
      "signal_strength": 0.9,
      "category": "...",
      "dates_appeared": ["2026-02-25"],
      "sources": [{"name": "...", "url": "..."}],
      "relevance_to_thesis": "How this signal supports the thesis"
    }
  ],
  "trend_context": [
    {
      "trend_name": "...",
      "trajectory": "accelerating",
      "this_week_signals": 5,
      "relationship_to_thesis": "How this trend relates to the thesis"
    }
  ],
  "prediction_review": [],
  "new_predictions": [
    {
      "prediction": "...",
      "confidence_level": "高",
      "timeframe": "6 months",
      "basis": "..."
    }
  ],
  "watchlist": ["...", "..."]
}
```

**Critical**: Do NOT modify any files in `memory/`. Only write to `data/weekly/`.

### Step 7: Git Push

After all files are saved, run:

```bash
cd /Users/zhouzhile/ai-frontier-insight && git add data/weekly/ && git commit -m "weekly: $(date +%Y)-W$(date +%V) insight" && git push
```

This ensures the weekly report is immediately available on GitHub for downstream consumers (e.g. OpenClaw).

## Language Guidelines

- Primary language: Chinese (中文)
- Keep English for: technical terms, product names, company names, paper titles, industry jargon
- Section headers: bilingual Chinese + English
- Tone: senior analyst briefing leadership — professional but not stiff. Write like you're explaining something important to a smart person, not filling out a form.
- Length target: 3000-5000 Chinese characters. Quality over quantity — if the thesis can be made in 3000 chars, don't pad to 5000.
- **标点符号：统一使用中文全角标点。** 逗号用"，"不用","；句号用"。"不用"."；冒号用"："不用":"；分号用"；"不用";"；括号用"（）"不用"()"；破折号用"——"不用"--"或"—"；引号用""" """不用"" ""。英文产品名、技术术语内部的标点保持英文原样（如"GPT-4"中的连字符），但中文句子中的标点一律全角。生成报告后须检查全文标点一致性。

## Scheduling

Designed for automated Monday morning runs via the `schedule-task` skill:
- Cron: `0 8 * * 1` (Monday 8 AM local time)
- Output goes to `data/weekly/` automatically

## Quantitative Data Policy

**Do NOT expose raw numerical scores in reader-facing outputs.** Use `signal_strength` internally for ranking only.

**Predictions — qualitative confidence with basis:**
- 高: 3+ independent signals cross-verify, clear causal logic
- 中: 2+ signals point same direction, but important unknowns remain
- 低: Weak signal or single-source, significant uncertainty

## Fact-Check Requirement

**所有事实性陈述都必须核查，不仅限于数字和日期。**

核查范围包括但不限于：

1. **数字与日期**：金额、人数、时间线、技术参数等——必须能追溯到具体来源。
2. **排他性/首创性声明**：任何包含"第一个""首次""唯一""最大""最早"等表述的句子，必须通过搜索确认没有先例。例如，说某模型是"第一个具备原生计算机操作能力的"之前，必须确认之前没有其他模型已经具备类似能力（如Anthropic的Claude computer use）。
3. **因果关系与归因**：A导致了B、A是为了换取B——这类因果或动机归因必须有证据支撑。如果是分析者自己的推测，必须用"可能""或许""一种解读是"等限定词明确标注。不能把推测写成事实。
4. **比较与程度**：说某事"史无前例""前所未有""彻底改变了"等，必须确认历史上确实没有类似先例。如果无法确认，降级为更审慎的表述。
5. **共识性判断**：说"产业共识""普遍认为""广泛赞誉"等，必须有多个独立来源佐证，不能仅凭单一评论或个人印象。

**核查方法**：优先使用web search验证。如果搜索后仍无法确认，有两个选择：（a）加限定词（"据目前公开信息""在主要通用模型中"）；（b）删除该断言。绝不允许将未经核实的事实性声明留在报告中。

## Conclusion & Prediction Writing Rules

**核心原则：只写有把握的结论，善用限定词。**

1. **数字必须有依据。** 预测中出现的任何数字（公司数量、时间窗口、百分比等）必须能追溯到具体信号或可验证的事实。如果没有可靠依据，用形容词代替数字（例如"多家头部SaaS公司"而非"5家Top 20 SaaS公司"；"未来数月"而非"6个月内"）。
2. **限定时间范围。** 不要对整个年度下判断（除非已接近年底）。用"至今""当前""近期"等限定词缩小断言范围。例如："2026年至今最值得关注的"而非"2026年最值得关注的"。
3. **限定确定性。** 区分"已经发生的事实"和"推测性结论"。事实直接陈述；推测加限定词（"可能""有望""初步迹象表明"等）。
4. **预测要可证伪但不要过度精确。** 好的预测："头部SaaS公司将跟进类似的后台Agent功能"。坏的预测："6个月内至少5家Top 20 SaaS公司推出类似Copilot Tasks的后台Agent功能"——除非你有5家公司的具体线索。
5. **宁可保守不可冒进。** 一个准确的、有限定的结论，比一个宏大但站不住脚的结论更有价值。读者信任建立在每句话都经得起推敲的基础上。

## Fresh Writing Rule

**每次生成报告都必须从原始数据出发重新构思，禁止在旧稿上修改。**

当数据范围变更（如新增一天的数据）时，不能在已有报告上"打补丁"——这会导致新内容像是硬塞进去的，行文不连贯。正确流程：

1. 丢弃之前的草稿，回到 Step 2（读所有原始数据）
2. 重新执行 Step 3（从全部数据中重新提炼主题和论点）
3. 从空白开始写 Step 5（全新行文）

即使主题不变，论证结构、信号选取、行文顺序都应基于完整数据集重新设计。读者不应能分辨出哪些内容是"先写的"、哪些是"后加的"。

## Important Reminders

- This is a STRATEGIC document, not a news digest. Every sentence should present evidence or draw an analytical conclusion.
- ONE trend per week, told well. Resist the urge to cover everything.
- If data is thin, that's fine — go deeper on fewer signals rather than padding.
- Always cite specific signals and sources.
- The report should read like a well-argued essay, not a filled-in template.
- **每次都从原始数据重新构思，不在旧稿上打补丁。**
