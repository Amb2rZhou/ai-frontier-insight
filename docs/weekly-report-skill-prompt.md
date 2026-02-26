# AI 前沿情报周报 — Cowork Skill Prompt

> 本文档描述了 ai-frontier-insight 项目的数据存储结构和记忆系统架构，供 Cowork skill 读取数据并生成周报使用。

---

## 项目位置

```
/Users/zhouzhile/ai-frontier-insight/
```

---

## 数据目录结构

```
ai-frontier-insight/
├── data/
│   ├── daily/                              ← 每日结构化存档
│   │   ├── 2026-02-25/
│   │   │   ├── brief.json                  ← 当日信号+洞察+趋势（永久保留）
│   │   │   └── sources.json                ← 被引用的原始数据（30天后自动清理）
│   │   ├── 2026-02-26/
│   │   │   ├── brief.json
│   │   │   └── sources.json
│   │   └── ...
│   ├── weekly/                             ← 周报输出目录（存放生成的周报）
│   └── x-monitor/                          ← Twitter/X 原始推文数据（14天后自动清理）
│       ├── 2026-02-25.json
│       └── 2026-02-26.json
│
├── memory/                                 ← 长期记忆系统
│   ├── weekly_signals.json                 ← 按周累积的信号（保留12周归档）
│   ├── trends.json                         ← 长期趋势追踪（最多50条）
│   └── history_insights.json               ← 历史预测存档（用于自校正）
│
├── config/
│   ├── drafts/                             ← 日报草稿（生命周期管理）
│   │   ├── 2026-02-25_daily.json
│   │   └── 2026-02-26_daily.json
│   ├── settings.yaml                       ← 全局配置
│   └── sources.yaml                        ← 数据源配置
│
└── prompts/                                ← AI prompt 模板
```

---

## 核心数据文件格式

### 1. `data/daily/{date}/brief.json` — 每日简报存档

这是写周报的**主要数据源**。每天一个文件，包含当日所有信号、洞察和趋势总结。

```json
{
  "date": "2026-02-26",
  "signal_count": 10,
  "raw_item_count": 362,
  "insights": [
    {
      "title": "Google's Aletheia AI Agent Solves 6/10 Unsolved Math Problems",
      "signal_text": "信号描述（中文，技术术语英文）...",
      "signal_strength": 0.9,
      "insight": "为什么重要（一句话，中文）...",
      "implication": "未来3-6个月的预测（一句话，中文）...",
      "category": "research_breakthrough",
      "sources": [
        {"name": "Reddit AI", "url": "https://..."},
        {"name": "@lmthang", "url": "https://x.com/..."}
      ],
      "tags": ["AI Research", "Autonomous Agents", "Reasoning"]
    }
  ],
  "trend_summary": "今日核心趋势观察：\n- **趋势要点1**：...\n- **趋势要点2**：..."
}
```

**category 枚举值**：`model_release` | `research_breakthrough` | `strategic_move` | `ecosystem_shift` | `infrastructure` | `open_source` | `product_launch` | `model_benchmark`

**signal_strength**：0.0-1.0，基于来源权威性、交互量、新颖性综合打分。

### 2. `memory/weekly_signals.json` — 本周信号累积

按天分组的信号列表，可作为 brief.json 的补充。结构：

```json
{
  "current_week": "2026-W08",
  "days": {
    "2026-02-25": [ {signal}, {signal}, ... ],
    "2026-02-26": [ {signal}, {signal}, ... ]
  },
  "archived_weeks": [
    {
      "week": "2026-W07",
      "days": { ... }
    }
  ]
}
```

每个 signal 的字段与 brief.json 中的 insight 基本一致（但不含 `insight` 和 `implication`）。

### 3. `memory/trends.json` — 长期趋势追踪

当前追踪的所有趋势（最多 50 条），包含走向和关键事件：

```json
{
  "last_updated": "2026-02-26T...",
  "trends": [
    {
      "id": "ai_safety_pivot_and_accelerated_agi_time",
      "name": "AI Safety Pivot and Accelerated AGI Timelines",
      "related_tags": ["AI Safety", "Corporate Strategy"],
      "trajectory": "accelerating",
      "signal_count": 8,
      "weekly_counts": [1, 2, 1, 1, 1, 1, 1],
      "key_events": [
        {"date": "2026-02-25", "event": "Anthropic drops key safety pledge"},
        {"date": "2026-02-26", "event": "Anthropic retires Opus 3, grants it a blog"}
      ],
      "created": "2026-02-25"
    }
  ]
}
```

**trajectory 枚举值**：`accelerating` | `stable` | `fading`

### 4. `memory/history_insights.json` — 历史预测存档

所有日报中的 implication 预测，用于周报的"预测回顾"环节：

```json
{
  "predictions": [
    {
      "date": "2026-02-25T18:08:43+08:00",
      "prediction_text": "未来3-6个月，...",
      "category": "strategic_move",
      "source_signal": "信号标题",
      "timeframe": "3-6 months"
    }
  ]
}
```

### 5. `data/daily/{date}/sources.json` — 原始数据引用（可选）

保存被信号引用的原始采集项（30天后自动删除）。近期数据可用于周报引用深度细节：

```json
{
  "date": "2026-02-26",
  "item_count": 45,
  "items": [
    {
      "index": 0,
      "source_type": "twitter",
      "source_name": "@karpathy",
      "title": "...",
      "content": "...",
      "url": "https://...",
      "published": "2026-02-26T...",
      "metadata": {"likes": 1200, "views": 50000}
    }
  ]
}
```

**source_type 枚举值**：`twitter` | `github` | `arxiv` | `rss` | `huggingface`

---

## 周报生成时的数据读取逻辑

```
1. 确定周报覆盖的日期范围（通常是上周一到周日）
2. 读取 data/daily/{每天}/brief.json → 获取所有信号和洞察
3. 读取 memory/trends.json → 获取趋势走向和关键事件
4. 读取 memory/history_insights.json → 获取本周做出的预测（可用于回顾）
5. 可选：读取 memory/weekly_signals.json → 补充当前周信号
6. 可选：读取 data/daily/{date}/sources.json → 获取原始数据细节
```

---

## 周报输出规范

生成的周报必须保存到以下位置：

### 周报文件

```
data/weekly/2026-W09.md              ← 周报正文（Markdown 格式，可直接发送）
data/weekly/2026-W09.json            ← 周报结构化数据（供后续分析）
```

命名规则：`{year}-W{week_number}`，使用 ISO 周编号。

### `data/weekly/{week}.json` 结构

```json
{
  "week": "2026-W09",
  "date_range": "2026-02-23 ~ 2026-03-01",
  "generated_at": "2026-03-01T10:00:00+08:00",
  "top_signals": [
    {
      "title": "...",
      "signal_strength": 0.9,
      "category": "research_breakthrough",
      "dates_appeared": ["2026-02-25", "2026-02-26"],
      "sources": [{"name": "...", "url": "..."}],
      "weekly_insight": "本周综合分析（不是日报 insight 的拼接）..."
    }
  ],
  "trend_analysis": [
    {
      "trend_name": "...",
      "trajectory": "accelerating",
      "this_week_signals": 5,
      "analysis": "深度分析段落..."
    }
  ],
  "prediction_review": [
    {
      "original_prediction": "...",
      "prediction_date": "2026-02-20",
      "status": "confirmed | partially_confirmed | too_early | invalidated",
      "evidence": "验证依据..."
    }
  ],
  "next_week_watchlist": ["关注点1", "关注点2"]
}
```

### 长期记忆更新

周报生成后，**不要修改** `memory/` 下的任何文件。这些文件由日报管道自动维护：
- `memory/trends.json` — 每天由 `update_trends()` 更新
- `memory/weekly_signals.json` — 每天由 `save_daily_signals()` 累积，周末自动归档
- `memory/history_insights.json` — 每天由 `generate_insights()` 追加

周报系统是**只读消费者**，只读取 memory/ 和 data/daily/ 的数据，输出到 data/weekly/。

---

## 当前数据统计（截至 2026-02-26）

| 数据 | 数值 |
|------|------|
| daily brief 存档天数 | 2 天 (02-25, 02-26) |
| 信号总数（本周） | ~30 条 |
| 活跃趋势数 | 22 条 |
| 历史预测数 | 88 条 |
| 数据源 | RSS 20+, Twitter 30+, GitHub 12, Arxiv 5类, HuggingFace |

---

## 周报风格建议

- **语言**：中文为主，技术术语保留英文
- **受众**：AI 行业从业者、技术决策者
- **结构**：
  1. 本周要闻 Top 5（最高 signal_strength 的跨日去重信号）
  2. 趋势深度分析（选 2-3 个 accelerating 趋势展开）
  3. 分类信号汇总（按 category 分组）
  4. 预测回顾（对比上周预测与本周实际）
  5. 下周关注点

---

## 注意事项

- brief.json 中的 `trend_summary` 是每日趋势总结，周报应做跨日综合而非拼接
- 多天出现的同一信号（如 Grok 4.20 在 02-25 和 02-26 都出现）有 `[Update]` 前缀标记，周报应合并为一条
- signal_strength > 0.85 的信号通常是当日最重要的事件
- trends.json 中 `trajectory: "fading"` 的趋势可以不在周报中重点展开
