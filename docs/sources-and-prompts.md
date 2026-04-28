# AI Frontier Insight Bot — 数据源与筛选逻辑

## 一、数据源

### 1. X/Twitter（~200 账号）

通过 X List 监控 AI 领域关键人物的推文，来源池约 300 人，实际同步到 List 约 200 人（筛选条件：粉丝 ≥5000，角色为 Research/Scientist/Engineer/Professor/Founder/CEO/CTO/Director/Lead）。过去一周活跃账号约 116 个，日均采集 ~90 条推文。

账号按机构/身份分布：

| 类别 | 数量 | 代表 |
|------|------|------|
| NVIDIA | ~39 | Jim Fan, Jensen Huang 等 |
| OpenAI | ~30 | Sam Altman, Mark Chen 等 |
| Google / DeepMind | ~32 | Jeff Dean, Demis Hassabis 等 |
| Founders/CEOs | ~21 | 各 AI 创业公司创始人 |
| Independent Researchers | ~19 | Andrej Karpathy 等 |
| Academia (Stanford/CMU/MIT/Harvard/Berkeley) | ~36 | 各校 AI 教授 |
| HuggingFace | ~15 | 模型/平台团队成员 |
| Anthropic | ~9 | Dario Amodei, Amanda Askell 等 |
| Microsoft | ~6 | 研究/产品团队 |
| Meta | ~2 | Yann LeCun 等 |
| Other | ~92 | AI 博主、工程师、生态参与者 |

账号按权威性分 3 级（Tier 1 > 2 > 3），影响 signal 评分。

### 2. RSS Feeds（28 个源）

| 分组 | 源 |
|------|-----|
| 付费科技媒体 | The Information |
| 英文科技媒体 | TechCrunch, The Verge, Ars Technica, Wired, VentureBeat, MIT Technology Review |
| AI 公司博客 | OpenAI Blog, Google AI Blog, Meta Engineering, Anthropic Blog |
| 技术社区 | Hacker News, Reddit ML, Reddit AI |
| ML 平台 | HuggingFace Blog |
| AI Safety | LessWrong (Curated), Alignment Forum |
| VC 洞察 | a16z Podcast, a16z 16 Minutes, a16z Live |
| 中文播客 | 硅谷101, 海外独角兽 |
| 研究博客 | Lil'Log (Lilian Weng) |
| Benchmark | LMSYS Arena Blog, Scale AI Blog, Aider Leaderboard, ARC Prize |

### 3. GitHub

- **Trending**: 每日搜索 6 个 topic（artificial-intelligence, machine-learning, llm, agents, deep-learning, generative-ai）的热门仓库，取 top 30
- **Watch Repos**: 监控 13 个核心仓库的 release（openai-python, anthropic-sdk-python, LangChain, LangGraph, AutoGen, CrewAI, Transformers, vLLM, Ollama, OpenHands, browser-use, AutoGPT, SWE-bench）

### 4. Arxiv 论文

通过 HuggingFace Daily Papers API 获取经社区投票筛选的论文（≥5 upvotes），覆盖 cs.AI / cs.CL / cs.LG / cs.CV / cs.MA 五个类别，取 top 25。

### 5. HuggingFace 模型 & Spaces

- Trending 模型 top 15
- 新发布模型 top 10
- Trending Spaces top 10

### 6. Benchmark 排行榜（5 个）

| 排行榜 | 衡量能力 |
|--------|---------|
| Open LLM Leaderboard | 开源模型综合能力 |
| SWE-bench Verified | 代码工程能力 |
| ARC-AGI-2 | 抽象推理能力 |
| OSWorld | 电脑操控能力 |
| Terminal-Bench 2.0 | 终端编程能力 |

自动监控排行榜变动（榜首更替、新模型上榜等），重大变化纳入日报。

---

## 二、筛选流程

```
350+ 条/天 原始信息
      ↓
 Signal Extraction (AI)  →  提取 15 条候选信号
      ↓
 代码去重（与近 3 天信号对比，60% 词重叠即过滤）
      ↓
 按 signal_strength 排序  →  取 top 10
      ↓
 Insight Generation (AI)  →  为每条生成 insight + implication
      ↓
 Trend Update + Summary
      ↓
 最终日报：10 条信号 + 洞察 + 趋势观察
```

---

## 三、Prompt

### Prompt 1: Signal Extraction

**模型**: DeepSeek (Haiku 级别，高吞吐低成本)

**角色**: AI 战略组研究员，从海量信息中挖掘与业务相关的重要内容

**关注视角**:
- 内容创作与理解（多模态生成、AI 辅助创作、风格迁移）
- 搜索与推荐（LLM 增强搜索、RAG、向量检索、个性化推荐）
- 内容安全与治理（AIGC 检测、对抗攻击、审核自动化）
- 技术突破（新架构、推理效率、端侧部署、长上下文、多模态）
- Agent 与新交互范式（Agent 框架、工具调用、自主任务）
- 头部公司战略动作（Google/OpenAI/Anthropic/Meta/字节/腾讯/百度/阿里）
- 开源生态（模型发布、社区工具、框架更新）
- 行业风险与监管（政策法规、伦理争议、版权、数据安全）

**排除**:
- 纯学术无应用前景的论文
- 与内容平台无关的垂直领域（纯生物/化学/药物 AI）
- 加密货币/Web3
- 无实质内容的观点争论

**论文筛选（严格）**: 只收录来自知名机构（Google DeepMind、OpenAI、Anthropic、Meta FAIR、Microsoft Research、Apple MLR、NVIDIA Research、字节、腾讯、阿里、百度、华为、商汤、MIT、Stanford、CMU、UC Berkeley、清华、北大、中科院）或知名学者的论文。无法判断来源 → 不选入。

**优先级**: 突破性研究 > 重要模型/产品发布 > 头部公司战略 > 新兴模式 > 重要开源

**signal_strength 评分 (0-1)**: 来源权威性 × 互动指标 × 新颖度

**去重（最高优先级）**: 逐条对照近几天已报道的 signal，相同/相似 → 跳过。唯一例外：重大后续进展加 `[Update]` 标记。宁可只输出 7-8 条，也不凑满 10 条。

**权威性标注**: signal_text 中必须标注来源权威性（论文标机构、推文标身份和互动量、GitHub 标 star 数、博客标媒体来源）。信息搬运账号（如 @omarsar0、@_akhaliq）必须溯源到原始发布者。

**输出**: JSON，每条含 title / signal_text / signal_strength / sources / tags / raw_item_indices

---

### Prompt 2: Insight Generation

**模型**: DeepSeek (Sonnet 级别，深度分析)

**角色**: AI 战略组资深分析师

**输出格式**:
- **Insight（为什么重要）**: 一句话 ≤50 字，直接下判断
- **Implication（意味着什么）**: 一句话 ≤50 字，落到具体可探索方向

**语气**: 不出现"小红书"，用内容平台/电商平台/社区平台等角色替代。用建议性表达（可以考虑/值得关注），不用指示性词汇（必须/应该）。

**输出**: JSON，每条含 signal_index / insight / implication / category

---

### Prompt 3: Trend Update

**模型**: DeepSeek

根据当日信号更新趋势数据库:
- 已有趋势 + 新信号 → 更新 trajectory（accelerating / stable / decelerating / fading）
- 新模式（3+ 信号或 1 条强信号）→ 创建新趋势
- 超过 2 周无信号 → 标记 fading

---

### Prompt 4: Trend Summary

**模型**: DeepSeek

基于当日信号和历史趋势数据，识别跨源模式（多个 signal 共同指向但尚未被明确表述的趋势），输出 3-5 个核心趋势观察，每个一句话。
