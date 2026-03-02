# AI Frontier Insight Bot — 产品技术文档

> 自动化 AI 前沿情报采集、分析与推送系统

---

## 一、产品概述

**AI Frontier Insight Bot** 是一个自动化 AI 前沿情报系统，每日从多个数据源采集原始信息，通过多层过滤与 AI 分析，提炼出高价值信号与深度洞察，并自动推送至团队群聊。

**核心价值**：从噪声中提取信号、从信号中生成洞察。

**当前运行规模**：

| 指标 | 数值 |
|------|------|
| 数据源平台 | 5 个（X/Twitter、RSS、GitHub、ArXiv、HuggingFace） |
| 日均原始数据 | 100–350 条 |
| 日均精选输出 | 10 条信号 + 洞察 |
| 推送频率 | 每日 08:00 CST |

---

## 二、系统架构总览

### 架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                        AI Frontier Insight Bot                   │
│                                                                  │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐        │
│  │ X/Twitter│   │  RSS    │   │ GitHub  │   │ ArXiv   │ ...     │
│  │(x-monitor)│  │ 23 feeds│   │ trending│   │ 5 cats  │        │
│  └────┬─────┘   └────┬────┘   └────┬────┘   └────┬────┘        │
│       │              │             │              │              │
│       ▼              ▼             ▼              ▼              │
│  ┌──────────────────────────────────────────────────┐           │
│  │              采集层 (Collectors)                   │           │
│  │         统一输出格式: RawItem                      │           │
│  └──────────────────────┬───────────────────────────┘           │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │          信号提取 (Signal Extraction)              │           │
│  │      AI 模型: DeepSeek V3 / Claude Haiku          │           │
│  │      输出: ≤10 条信号 + signal_strength            │           │
│  └──────────────────────┬───────────────────────────┘           │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │          洞察生成 (Insight Generation)             │           │
│  │      AI 模型: DeepSeek V3 / Claude Sonnet         │           │
│  │      输出: insight + implication + category        │           │
│  └──────────────────────┬───────────────────────────┘           │
│                         │                                        │
│                    ┌────┴────┐                                   │
│                    ▼         ▼                                   │
│  ┌──────────────────┐ ┌────────────────┐                        │
│  │  记忆层 (Memory)  │ │  输出层 (Output)│                        │
│  │ trends.json      │ │ Markdown 日报   │                        │
│  │ weekly_signals   │ │ RedCity Webhook │                        │
│  │ history_insights │ │                │                        │
│  └──────────────────┘ └────────────────┘                        │
└──────────────────────────────────────────────────────────────────┘
```

### 关键设计决策

| 项目 | 选择 | 原因 |
|------|------|------|
| 子系统 | x-monitor（X 爬虫）+ ai-frontier-insight（多源分析引擎） | 职责分离，独立迭代 |
| 部署 | 本地 macOS + launchd 定时任务 | 零服务器成本，本地代理可用 |
| AI 模型 | DeepSeek V3（主力）/ Claude Sonnet + Haiku（备选） | DeepSeek 性价比高，Claude 作为 fallback |
| 输出语言 | 混合模式（英文技术术语 + 中文分析） | 适合双语技术团队 |

---

## 三、数据来源与管理

### 3.1 X/Twitter（核心来源）

**采集架构**：独立项目 `x-monitor`，通过 Playwright 无头浏览器监控 X List 页面。

**已实现：**

- **X List 机制**：通过单个 X List 聚合所有监控账号，单次请求读取整个列表，避免逐账号请求触发风控
- **API 响应拦截**：不依赖 DOM 渲染（X 在 headless 模式下阻止 DOM 渲染），而是拦截 `ListLatestTweetsTimeline` GraphQL API 响应，提取结构化数据
- **智能调度**：2–5 小时随机间隔 + 0–5 分钟抖动，日报前（07:00–07:25）强制采集保证数据时效
- **失败重试**：最多 2 次，10 分钟间隔；Cookie 过期自动检测 + webhook 告警
- **三层过滤**：硬规则（低价值/低互动）→ DeepSeek 语义分类（AI 相关性）→ seen_ids 去重
- **分页支持**：自动分页最多 5 页，最多 500 条推文；连续已知推文时提前终止

**当前监控规模**：X List 含 ~200 个 AI 领域账号，通过 MIT Bunny 半自动筛选入库，代表人物包括：

| 类别 | 代表人物 |
|------|---------|
| OpenAI | Sam Altman, Mark Chen, Gabor Melis |
| Anthropic | Dario Amodei, Amanda Askell, Jack Clark |
| Google DeepMind | Demis Hassabis, Jeff Dean |
| 独立研究者 | Andrej Karpathy, Yann LeCun, Jim Fan, David Ha |
| AI 生态 | Swyx, Simon Willison |
| 以及更多 | 覆盖 OpenAI / Anthropic / Google / Meta / NVIDIA / 独立研究者 / KOL 等约 200 个账号 |

**来源发现（半自动）：**

- 通过 [MIT Bunny](https://x.mitbunny.ai) 开源项目发现 AI 领域账号
- 按角色关键词（Research、Scientist、Engineer、Professor、Founder 等）+ 粉丝量（≥5000）筛选
- `sync.py` 脚本辅助对比差异，通过 Playwright 模拟人工操作添加/移除 List 成员
- 每次最多添加 10 个 / 移除 5 个，操作间隔 5–12 秒，避免触发风控

**计划中：**

- 全自动来源维护流程：定期爬取 Bunny 名单 → 对比本地 → 自动增减
- 账号质量标注系统：基于历史内容质量自动调整优先级
- 多账号轮换机制

### 3.2 RSS 订阅源

23 个活跃 RSS 源，覆盖 9 个分组：

| 分组 | 数量 | 代表来源 |
|------|------|---------|
| 付费科技媒体 | 1 | The Information |
| 英文科技媒体 | 6 | TechCrunch, The Verge, Ars Technica, Wired, VentureBeat, MIT Tech Review |
| 官方博客 | 4 | OpenAI, Google AI, Meta Engineering, Anthropic |
| 技术社区 | 3 | Hacker News, Reddit ML, Reddit AI |
| ML 平台 | 1 | HuggingFace Blog |
| AI 安全/对齐 | 2 | LessWrong (Curated), Alignment Forum |
| VC / 行业洞察 | 3 | a16z Podcast, a16z 16 Minutes, a16z Live |
| 中文播客 | 2 | 硅谷101, 海外独角兽 |
| 研究博客 | 1 | Lil'Log (Lilian Weng) |

采集参数：并行抓取，24 小时时间窗口。

### 3.3 GitHub

- **Trending**：6 个 AI 相关 topic（artificial-intelligence, machine-learning, llm, agents, deep-learning, generative-ai）
- **Releases**：12 个核心 repo 监控

| 类别 | 项目 |
|------|------|
| 模型 SDK | openai-python, anthropic-sdk-python |
| 框架 | LangChain, LangGraph, AutoGen, CrewAI |
| 模型/推理 | Transformers, vLLM, Ollama |
| 前沿项目 | OpenHands, browser-use, AutoGPT |

### 3.4 ArXiv

- 5 个类别：cs.AI, cs.CL (NLP), cs.LG (ML), cs.CV (CV), cs.MA (多智能体)
- 按提交日期排序，最多 25 篇/天

### 3.5 HuggingFace

- Trending Models: 15 个
- New Models: 10 个
- Trending Spaces: 10 个

---

## 四、信息处理流水线

### 4.1 采集层 → 统一数据格式

所有来源统一为 `RawItem`：

```
RawItem {
    title:       str    # 标题
    content:     str    # 正文内容
    source_type: str    # 来源平台 (twitter/rss/github/arxiv/huggingface)
    source_name: str    # 来源名称
    url:         str    # 原始链接
    published:   str    # 发布时间 (ISO 8601)
    metadata:    dict   # 平台特定元数据（stars, likes 等）
}
```

典型日产量：100–350 条 RawItem。

### 4.2 X-Monitor 三层过滤

| 层级 | 类型 | 方法 | 规则 |
|------|------|------|------|
| 硬规则 | 确定性 | 规则引擎 | 去除纯转推（RT @...）、纯链接（正文 <10 字符）、互动量过低 |
| 语义过滤 | AI | DeepSeek V3 | 判断是否与 AI/ML/科技相关，不相关的剔除 |
| 去重 | 状态 | seen_ids | 已处理过的推文 ID 不重复入库 |

**互动量阈值**：
- 新推文（<3h）：likes ≥ 1 或 views ≥ 100
- 老推文（≥3h）：likes ≥ 3 或 views ≥ 500
- 无互动数据时保留（信任推荐账号）

### 4.3 信号提取（Signal Extraction）

- **AI 模型**：DeepSeek V3（主力）/ Claude Haiku（备选），成本优先
- **输入**：全部 RawItem + 当前趋势 + 近期信号标题（去重参考）
- **输出**：最多 10 条信号，每条含 `signal_strength`（0–1）
- **优先级排序**：突破性研究 > 重要发布 > 头部公司战略 > 新兴模式 > 重要开源
- **去重规则**：已报道事件仅在有实质新信息时以 `[Update]` 形式再入选

### 4.4 洞察生成（Insight Generation）

- **AI 模型**：DeepSeek V3（主力）/ Claude Sonnet（备选），深度推理
- **输入**：信号 + 过往预测（4 周回溯）+ 趋势上下文
- **输出**：每条信号附加：
  - `insight`：为什么重要
  - `implication`：意味着什么
  - `category`：分类标签

### 4.5 趋势更新

- **AI 模型**：DeepSeek V3 / Claude Haiku
- 维护最多 50 条趋势，跟踪 `trajectory`（加速 / 稳定 / 衰退 / 消退）
- 12 周滚动计数，自动标记无信号 >2 周的趋势为"消退"

---

## 五、记忆与数据存储

### 5.1 目录结构

```
data/
├── x-monitor/{date}.json      # 推文原始数据（14 天保留）
├── daily/{date}/
│   ├── brief.json              # 当日信号+洞察（永久保留）
│   └── sources.json            # 被引用原始数据（30 天保留）
└── weekly/{week}.json|md       # 周报（永久保留）

memory/
├── weekly_signals.json         # 周信号累积器（12 周滚动）
├── trends.json                 # 趋势数据库（最多 50 条）
└── history_insights.json       # 预测历史（最近 100 条）

config/
├── settings.yaml               # 系统配置
├── sources.yaml                # 数据源定义
└── drafts/{date}_daily.json    # 日报草稿（生命周期管理）
```

### 5.2 数据生命周期

| 数据类型 | 保留策略 | 清理机制 |
|---------|---------|---------|
| 推文原始数据 | 14 天 | 自动清理 |
| 引用的原始数据 | 30 天 | 自动清理 |
| 日报洞察 | 永久 | — |
| 周报 | 永久 | — |
| 趋势数据库 | 持续更新 | 超 50 条淘汰消退趋势 |
| 信号累积 | 12 周滚动 | 按周自动归档 |

### 5.3 记忆系统的自我修正

- **预测回溯**：生成新洞察时参考 4 周前的预测，对比实际发展，提升预测准确度
- **趋势自适应**：trajectory 随信号频率自动调整，长期无信号的趋势自动标记为消退

---

## 六、输出与推送

### 6.1 日报（已实现，全自动）

| 项目 | 详情 |
|------|------|
| 推送时间 | 每日 08:00 CST |
| 推送渠道 | RedCity webhook（小红书内部群聊机器人） |
| 内容格式 | Markdown |
| 内容结构 | 10 条精选信号 + insight + implication + 趋势总结 |
| 消息分割 | 分 2 条消息发送（8KB/条限制），末条 @all |

### 6.2 周报（已实现，自动生成）

- **自动化**：通过 Claude Cowork 定时读取周数据，自动生成周报
- **三个分析维度**：Research Insight / Tech Trend / Company Strategy
- **主题轮换**：每月 4 周依次覆盖 research → tech_trend → company_strategy → meta_reflection
- **输出格式**：JSON + Markdown + DOCX
- **当前局限**：生成后转为 Redoc 格式仍需手动操作

---

## 七、筛选依据与质量控制

### 7.1 来源质量分层

| 层级 | 描述 | 代表人物/来源 |
|------|------|-------------|
| Tier 1 | AI 领域核心人物 | Sam Altman, Andrej Karpathy, Demis Hassabis, Yann LeCun, Dario Amodei, Jeff Dean, Jim Fan |
| Tier 2 | 知名研究者、技术 KOL | Amanda Askell, Jack Clark, David Ha, Swyx, Simon Willison, Gabor Melis, Mark Chen |
| Tier 3 | 行业观察者、新闻聚合 | AI News |

权威度（Tier）直接影响信号提取时的 `signal_strength` 评分。

### 7.2 内容过滤原则

- **排除**：日常更新、小版本迭代、无实质内容的个人观点、纯营销内容
- **保留**：突破性研究、重要产品发布、战略变化、新兴技术模式
- **去重**：同一事件多条信息合并为一条信号，多来源交叉验证提升可信度

---

## 八、技术特性

### 8.1 健壮性

| 机制 | 实现方式 |
|------|---------|
| SSL 兜底 | Python LibreSSL 失败时自动 fallback 到 curl（系统原生 TLS） |
| 失败重试 | x-monitor 最多 2 次重试，10 分钟间隔 |
| Cookie 过期检测 | 自动检测 + RedCity webhook 运维告警 |
| 代理兼容 | 支持通过本地代理采集 |
| AI 模型 fallback | 主模型失败自动切换备选模型 |
| JSON 修复 | AI 返回格式异常时自动修复 |

### 8.2 反检测（X/Twitter）

| 策略 | 说明 |
|------|------|
| API 响应拦截 | 不依赖 DOM 渲染，绕过 X 的反爬机制 |
| Playwright Stealth | 伪装浏览器指纹，规避自动化检测 |
| 随机调度 | 2–5 小时随机间隔 + 0–5 分钟抖动，避免模式化请求 |
| 人类模拟 | 随机滚动距离、页面间随机延迟 |

---

## 九、核心优势：持续进化的系统

与传统静态信息聚合工具不同，AI Frontier Insight Bot 是一个**随时间自我进化**的系统：

### 9.1 记忆积累驱动质量提升

- **趋势数据库越用越准**：随着信号持续积累，趋势的 trajectory 判断（加速/稳定/衰退）基于更长的历史数据，预测准确度不断提高
- **预测回溯自我修正**：每次生成新洞察时参考 4 周前的预测，与实际发展对比，系统自动学习哪些类型的预测更可靠
- **去重与信号识别增强**：历史信号标题库不断扩充，重复事件的识别更精准，真正的新信号更容易被识别出来

### 9.2 LLM 能力红利

- **零成本享受模型升级**：系统的分析质量直接取决于底层大语言模型的能力——每一次模型迭代（更强的推理、更好的中文理解、更长的上下文），系统产出质量自动提升，无需修改任何代码
- **灵活切换模型**：架构支持 DeepSeek / Claude 动态切换，可随时采用性价比最优或能力最强的模型

---

## 十、局限性与改进方向

### 当前局限

| 局限 | 影响 | 缓解措施 |
|------|------|---------|
| X 采集依赖 Playwright 爬虫 | Cookie 过期、反爬风控 | 重试 + 告警机制 |
| X 来源发现依赖 MIT Bunny | 时效性不够，筛选不够严格 | sync.py 半自动化流程 |
| 本地部署依赖电脑开机 | 关机期间无法采集 | GitHub Actions 备用流程 |
| macOS Python 3.9 + LibreSSL | SSL 兼容性问题 | curl fallback 已缓解 |
| DeepSeek V3 稳定性与质量 | 偶发返回错误、分析深度不及 Claude | 现阶段测试为控制成本优先使用，正式上线可切换 Claude |
| 周报 Redoc 转换需手动 | 生成后仍需人工发布 | 计划中自动化 |

### 改进方向

- **X 采集升级**：订阅 X API，替代 Playwright 爬虫方案，彻底消除 Cookie/反爬问题
- **来源自动化管理**：自动发现、添加、评分、淘汰，形成闭环
- **云端部署**：消除本地依赖，7×24 运行
- **周报 Redoc 发布自动化**：打通从生成到发布的完整流程

---

*文档生成日期：2026-03-02*
