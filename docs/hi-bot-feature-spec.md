# Frontier Insight Bot — Hi 应用功能设计

## 概述

将 AI Frontier Insight Bot 部署为 Hi 内部应用，在群聊和私聊中提供 AI 前沿情报的推送、查询和协作能力。

---

## 架构选型

### 网络约束

| | MacBook (外网) | 公司服务器 (内网) |
|---|---|---|
| Twitter/X | ✅ | ❌ |
| HuggingFace | ✅ | ❌ |
| Google | ✅ | ❌ |
| 所有 RSS | ✅ | ⚠️ 部分 |
| OpenAI API | ✅ | ❌ |
| GitHub API | ✅ | ✅ |
| arXiv | ✅ | ✅ |
| DeepSeek API | ✅ | ✅ |
| Moonshot/Kimi API | ✅ | ✅ |
| 字节火山 API | ✅ | ✅ |
| 内部 AI (hibo/Darwin) | ❌ | ✅ |
| Hi API (redcity-open) | ❌ | ✅ |

---

### 方案 A：统一处理（MacBook 采集+处理，服务器仅转发）

MacBook 完成全部采集和 AI 处理，产出成品 JSON，服务器只做格式化和推送。

```
MacBook                              GitHub                 公司服务器
┌────────────────────────┐      ┌──────────┐          ┌──────────────────┐
│ 采集层                  │      │          │          │ Hi Bot (转发层)   │
│ x-monitor / RSS / arXiv│      │ brief.   │ git pull │                  │
│ GitHub / HuggingFace   │      │ json     │────────→ │ • 读成品 JSON     │
│          ↓             │ push │          │          │ • 创建 Redoc 文档 │
│ AI 处理层 (DeepSeek)    │────→ │ trends.  │          │ • 发卡片到群      │
│ • 信号提取              │      │ json     │          │ • 应用号私信      │
│ • 洞察生成              │      │          │          │ • WebSocket 问答  │
│ • 趋势更新              │      │ weekly/  │          │   (基于已有数据)  │
│          ↓             │      │          │          │                  │
│ 成品: brief.json       │      └──────────┘          └──────────────────┘
└────────────────────────┘
```

| 维度 | 评估 |
|---|---|
| 改动量 | **小**。现有 pipeline 不动，服务器端只写推送逻辑 |
| AI 依赖 | MacBook 上的 DeepSeek，服务器端问答也用 DeepSeek |
| 定制化 | ❌ 弱。所有人看同一份日报，筛选逻辑写死在 MacBook |
| 可用性 | ⚠️ MacBook 关机/断网 = 当天无数据 |
| 成本 | DeepSeek API 费用（约 ¥2-5/天） |
| 适合场景 | 快速上线，团队 <10 人，统一信息需求 |

---

### 方案 B：分离架构（MacBook 仅采集 raw data，服务器做 AI 处理+推送）

MacBook 只负责采集原始数据上传，服务器用内部 AI 或外部 API 做全部处理和分发。

```
MacBook (数据泵)              GitHub                 公司服务器
┌──────────────────┐      ┌──────────┐      ┌─────────────────────────┐
│ 纯采集，零 AI     │      │          │      │ Hi Bot (处理+分发层)     │
│                  │      │ raw/     │ pull │                         │
│ • x-monitor      │      │ twitter/ │────→ │ AI 处理层                │
│ • RSS feeds      │ push │ rss/     │      │ 内部AI/DeepSeek/Kimi:   │
│ • GitHub trending│────→ │ github/  │      │ • 信号提取（可定制prompt）│
│ • arXiv papers   │      │ arxiv/   │      │ • 洞察生成（可定制视角） │
│ • HuggingFace    │      │ hf/      │      │ • 趋势更新              │
│                  │      │          │      │         ↓               │
│ 产出:            │      └──────────┘      │ 分发层                   │
│ raw items JSON   │                        │ • 群A: 战略视角,8条      │
│ (未经AI处理)     │                        │ • 群B: 技术视角,12条     │
└──────────────────┘                        │ • 个人: 按关注领域筛选    │
                                            └─────────────────────────┘
```

| 维度 | 评估 |
|---|---|
| 改动量 | **中**。MacBook pipeline 改为只输出 raw items；服务器新增 AI 处理 |
| AI 依赖 | 内部 AI (hibo/Darwin) 或 DeepSeek/Kimi/火山（服务器均可访问） |
| 定制化 | ✅ 每个群/每个人可以有不同 prompt、条数、视角、筛选规则 |
| 可用性 | ✅ MacBook 关机只影响采集，不影响处理和推送 |
| 成本 | 内部 AI = 免费；外部 API 按需 |
| 适合场景 | 多团队/多人使用，需个性化，长期运营 |

#### 方案 B 的 raw data 格式

```json
{
  "date": "2026-04-09",
  "collected_at": "2026-04-09T08:35:00",
  "sources": {
    "twitter": {
      "item_count": 128,
      "items": [
        {
          "source": "twitter",
          "source_name": "@JeffDean",
          "text": "推文全文...",
          "url": "https://x.com/...",
          "timestamp": "2026-04-09T02:30:00Z",
          "engagement": {"likes": 1200, "retweets": 300, "views": 85000}
        }
      ]
    },
    "rss": { "item_count": 40, "items": [...] },
    "github": { "item_count": 27, "items": [...] },
    "arxiv": { "item_count": 25, "items": [...] },
    "huggingface": { "item_count": 25, "items": [...] }
  },
  "total_items": 245
}
```

#### 方案 B 的定制化能力

| 定制维度 | 示例 | 实现方式 |
|---|---|---|
| 信号条数 | 群 A 看 8 条精选，群 B 看 15 条全量 | 配置 `max_signals` per group |
| 筛选视角 | 战略组看商业动态，技术组看论文和开源 | 不同 prompt per group |
| 来源权重 | 某群只关心 Twitter + arXiv | 配置 `enabled_sources` per group |
| 信号强度阈值 | 只推 ≥0.8 的高质量信号 | 配置 `min_strength` per group |
| 语言 | 中文日报 / 英文日报 | prompt 控制输出语言 |
| 推送时间 | 群 A 早 9:30，群 B 下午 2:00 | scheduler per group |
| 关注标签 | 某人只关注 "Agent" "多模态" | 个人订阅 + tag 过滤 |

---

### 方案对比

| 维度 | 方案 A (统一处理) | 方案 B (分离架构) |
|---|---|---|
| MacBook 职责 | 采集 + AI 处理 | 仅采集 |
| 服务器 AI 处理 | 仅问答 | 全链路（信号/洞察/趋势/周报/问答） |
| 上线速度 | ⚡ 快（1-2 周） | 🔧 中（2-4 周） |
| 定制化 | ❌ 所有人同一份 | ✅ 按群/按人定制 |
| MacBook 依赖 | 高（处理链路在本地） | 低（只是数据泵） |
| AI 模型灵活性 | 仅 DeepSeek | 内部 AI / DeepSeek / Kimi / 火山 |
| 适合阶段 | MVP / 快速验证 | 正式运营 / 多团队推广 |

**建议**：先用方案 A 快速上线验证，同步准备方案 B 的 raw data 上传。一旦需要给第二个群或第二个人定制内容，切到方案 B。

---

### 未来演进：X API 付费版

购买 X (Twitter) API 后的能力变化：

#### 当前 vs X API

| | 当前 (x-monitor 浏览器抓取) | X API 付费版 |
|---|---|---|
| 运行依赖 | MacBook + Cookie 登录态 | 服务器直接调 API，无需浏览器 |
| 认证 | Cookie 过期需手动更新 | API Key 长期有效 |
| 覆盖范围 | List 页面可见的推文（受滚动深度限制） | 精确查询任意用户/关键词/时间段 |
| 数据稳定性 | 受 X 反爬限制，数量波动大 | API 配额明确，数据稳定 |
| 上下文 | 无法获取 reply/thread | 完整 conversation thread |
| 实时性 | 定时抓取（2-5h 间隔） | Filtered Stream 实时推送 |
| 账号数 | ~200 账号，每天 80-200 条 | 不限账号数 |

#### 新增功能

| 功能 | API 等级 | 说明 |
|---|---|---|
| 去掉 MacBook x-monitor | Basic ($100/月) | 服务器直接采集，Cookie 问题消失 |
| 精确时间查询 | Basic | 不依赖页面滚动，精确 24h 推文 |
| 扩大到 500+ 账号 | Basic | 不受 List 限制 |
| 实时告警 | Pro ($5000/月) | 重大事件（模型发布/收购）分钟级推送 |
| 关键词全网监控 | Pro | 监控 "Claude"/"GPT-5" 等关键词 |
| Thread 上下文 | Basic | 完整讨论串，信号质量更高 |
| 方案 B 完全落地 | Basic | 服务器自己采集 Twitter，MacBook 只剩 HF 和被墙 RSS |

#### 投入产出

| 方案 | 月费 | 核心收益 | 建议时机 |
|---|---|---|---|
| 维持现状 | ¥0 | MacBook 需在线，Cookie 偶尔过期 | 当前 |
| Basic ($100/月) | ~¥700 | 去掉 MacBook 依赖，数据稳定 | 用户 >5 人 |
| Pro ($5000/月) | ~¥35000 | 实时告警 + 全网监控 | 成为部门级基础设施 |

---

## 数据处理与知识管理

### 数据处理流水线

```
MacBook 采集
  raw data (~250条/天)
      │
      │ git push
      ▼
服务器 git pull
      │
      │ 硬规则排除（纯代码，无 AI）
      │  - 纯转发/无实质内容
      │  - 跨天去重
      │  - 互动量过低
      │  - 来源不可信（非知名机构论文）
      │  - 非 AI 相关
      │  - CSR/公益/纯观点
      ▼
  signal pool (~50-80条/天)
      │
      │ 同时做两件事：
      │
      ├──→ 更新共享记忆层（轻量 AI）
      │      entities/ topics/ timeline
      │      写入 Hi 搜索平台索引
      │
      └──→ 各群各自的 AI 处理
             │
             ├─ 群A prompt (战略视角) → AI 打分 → 8条 → 推送
             ├─ 群B prompt (技术视角) → AI 打分 → 12条 → 推送
             └─ 个人C (Agent关注) → AI 打分 → 5条 → 私信
```

**关键设计**：
- signal pool 的筛选是**排除法**（客观质量底线），不打分，跟谁看没关系
- signal_strength 由**各群自己的 AI** 根据自己的 prompt 打，不用全局分数
- 同一条信号对不同群的 strength 可能完全不同（如 Safetensors：基础设施组 0.95 vs 战略组 0.5）

### 多群定制（一个 Hi 应用，多套 prompt）

一个 Frontier Insight Bot 应用可以加入多个群。服务器端根据 chatId 路由到不同配置：

```yaml
# bot_config.yaml
groups:
  CHAT_A:
    name: "战略组"
    prompt_template: "strategy"     # 对应 prompts/strategy.txt
    max_signals: 8
    focus_tags: ["strategic_move", "funding", "acquisition"]
    push_time: "09:30"

  CHAT_B:
    name: "技术组"
    prompt_template: "tech"         # 对应 prompts/tech.txt
    max_signals: 12
    focus_tags: ["open_source", "infrastructure", "research"]
    push_time: "09:30"

  CHAT_C:
    name: "产品组"
    prompt_template: "product"
    max_signals: 10
    focus_tags: ["product_launch", "user_experience", "new_paradigm"]
    push_time: "10:00"
```

Hi 平台只负责消息收发，所有 prompt/筛选/打分逻辑在服务器端，一个应用支持任意数量的群。

### 共享知识库

记忆层索引 signal pool（质量过滤后的共享池），不索引 raw data，也不索引各群的定制输出。

```
memory/
├── entities/              # 公司/模型/人物 — 累积更新
│   ├── anthropic.json
│   ├── openai.json
│   └── qwen.json
├── topics/                # 技术话题
│   ├── multi-agent.json
│   └── open-source-models.json
├── trends.json            # 趋势排名
└── timeline.json          # 事件链（A→B→C）
```

- **推送是定制的，知识是共享的**
- 群 A 只推了 8 条战略信号，但群 A 用户问"最近有什么开源模型"时，搜索的是完整 signal pool
- 每天从 signal pool 自动提取实体/事件，更新 entities/ 和 topics/

### 检索方式（三层，无需向量库）

| 层 | 触发条件 | 方式 | 示例 |
|---|---|---|---|
| 结构化查找 | 实体名匹配 | 文件名 → 读 JSON | "Anthropic 最近在干嘛" |
| Hi 搜索平台 | 关键词问题 | `redcity:search` API | "多模态相关进展" |
| AI 路由 | 分析/比较型问题 | AI 读索引 → 选文件 → 生成 | "开源和闭源的差距在缩小吗" |

### 数据衰减

signal pool 按时间自动衰减（不依赖 strength，因为 strength 是各群独立打分的）：

| 时间范围 | 策略 |
|---|---|
| 30 天内 | 全部保留 |
| 30-90 天 | 保留被 ≥2 个群选中过的信号 |
| 90-180 天 | 只保留进入 entities/topics 记忆的信号 |
| 180 天+ | 删除 signal pool 原文，entities/topics 记忆永久保留 |

预计稳态规模：~3000-5000 条 signal pool + 几百个 entity/topic 文件，Hi 搜索平台完全覆盖。

---

## 功能清单

### AI 能力标注

| 功能 | 需要 AI | AI 用途 | 可用模型 |
|---|---|---|---|
| F1 日报推送 | ❌ | — | — |
| F2 周报生成 | ✅ | 一周信号总结为周报 | 内部AI / DeepSeek / Kimi |
| F3 私信推送 | ❌ | — | — |
| F4 群内问答 | ✅ | 意图理解 + 数据检索 + 生成回答 | 内部AI / DeepSeek / Kimi |
| F5 信号搜索 | ❌ | — | — |
| F6 创建待办 | ⚠️ | 简单场景关键词匹配即可 | — |
| F7 群管理 | ❌ | — | — |
| F8 文档空间 | ❌ | — | — |
| F9 图表推送 | ❌ | — | — |
| 方案B: 信号提取 | ✅ | raw items → signals | 内部AI / DeepSeek / Kimi |
| 方案B: 洞察生成 | ✅ | signals → insights | 内部AI / DeepSeek / Kimi |

---

### P0 — 核心推送（替代现有 webhook）

#### F1: 日报推送（Redoc 文档 + 群内卡片）

**用户体验**：每天定时，群内收到一张摘要卡片，点击跳转完整 Redoc 文档。不刷屏。

**流程**：
1. 服务器定时 git pull，读取 `data/daily/{today}/brief.json`
2. 调用 Redoc API，将日报 Markdown 创建为 Hi 文档
3. 构造摘要卡片（日期、信号数、Top 3 标题、文档链接按钮）
4. 通过 IM API 发送卡片到指定群

**所需权限**：
- `redoc:docinfo:readwrite` — 通过 Markdown 创建文档
- `redcity:card` — 创建卡片模版和卡片实体
- `im:message` — 发送卡片消息到群

**所需 API**：
| 步骤 | API 别名 | 说明 |
|---|---|---|
| 创建文档 | `redoc:docinfo:createDocByMarkdown:v1` | 日报 Markdown → Hi 文档 |
| 创建卡片模版 | `redcity:card.batchQueryEntitySchema:v1` | 获取/确认卡片模版 |
| 创建卡片实体 | `redcity:card.batchCreateEntity:v1` | 填充当天数据 |
| 发送到群 | `im:message.sendMessageToChat:v1`（卡片类型） | 推送卡片 |

**卡片内容设计**：
```
┌─────────────────────────────────────────┐
│  📊 AI Frontier Daily Brief             │
│  2026-04-09 · 10 signals · 251 items    │
│                                         │
│  🔴 0.95 Meta Launches Muse Spark...    │
│  🔴 0.88 a16z: 29% Fortune 500...      │
│  🟡 0.80 Qwen3.6-Plus Tops OpenRouter  │
│                                         │
│  趋势: Agent框架↑ 开源模型↑ AI安全→     │
│                                         │
│  [📄 查看完整日报]    [📈 趋势总览]      │
└─────────────────────────────────────────┘
```

**确定性**：✅ 高

---

#### F2: 周报自动生成为文档

**用户体验**：每周一自动生成周报文档，群内发卡片通知。

**流程**：
1. 读取 `data/weekly/` + `memory/trends.json`
2. 调用 AI 生成周报 Markdown
3. 创建 Redoc 文档，设置共享权限
4. 发卡片到群

**所需权限**：
- `redoc:docinfo:readwrite` — 创建周报文档
- `redoc:permission:readwrite` — 文档共享给团队
- `redcity:card` + `im:message` — 同 F1

**所需 API**：
| 步骤 | API 别名 | 说明 |
|---|---|---|
| 创建文档 | `redoc:docinfo:createDocByMarkdown:v1` | 写入周报 |
| 共享文档 | `redoc:permission:addMemberToShortcutForNewOpen:v2` | 添加协作者 |
| 查询可见性 | `redoc:permission:checkShortcutIsPublicForNewOpen:v1` | 确认可见 |

**确定性**：✅ 高

---

#### F3: 应用号私信推送

**用户体验**：订阅用户通过应用号私聊收到日报/周报通知。

**所需权限**：`redcity:asn:wr`

**所需 API**：
| 步骤 | API 别名 | 说明 |
|---|---|---|
| 发送消息 | `redcity:asn.asnSendMessageToPerson:v1` | Markdown 或卡片到个人 |
| 定时发送 | `redcity:asn.asnDelaySendMessageToPerson:v1` | 预设时间推送 |
| 查询历史 | `redcity:asn.pageQueryAsnChatMessageList:v1` | 调试用 |

**确定性**：✅ 高

---

### P1 — 交互查询

#### F4: 群内/私聊问答

**用户体验**：用户发消息（如"最近有什么 Agent 新闻"），Bot 流式回复。

**流程**：
1. WebSocket 长连接接收用户消息
2. 解析意图（关键词 + AI）
3. 检索本地数据（brief.json / trends.json / 历史信号）
4. 调用 AI 生成回答
5. 流式推送回复

**所需权限**：`im:message`

**所需 API**：
| 步骤 | API 别名 | 说明 |
|---|---|---|
| 创建流式会话 | `im:message.createStreamMessage:v1` | 获取 bizId |
| 推送流式内容 | `im:message.pushStreamMessage:v1` | 逐段输出 |
| 普通回复 | `im:message.sendMessageToChat:v1` | 简短回复 |

**支持的查询类型**：
| 查询示例 | 数据来源 | 处理方式 |
|---|---|---|
| "今天有什么新信号" | `data/daily/{today}/brief.json` | 直接读取 |
| "最近一周 Agent 相关" | 近 7 天 brief.json + trends.json | 关键词过滤 + AI 总结 |
| "趋势排名前 5" | `memory/trends.json` | 直接排序 |
| "Anthropic 最近在干嘛" | 历史信号全文搜索 | 搜索 + AI 总结 |

**确定性**：✅ 高

---

#### F5: 信号历史搜索（Hi 搜索平台）

**用户体验**：Hi 搜索栏搜"多模态模型"，直接出历史信号结果。

**所需权限**：`redcity:search:wr` + `redcity:search:readonly`

**所需 API**：
| 步骤 | API 别名 | 说明 |
|---|---|---|
| 写入信号 | `redcity:search.batchCreateDataItem:v1` | 每日批量写入 |
| 搜索 | `redcity:search.commonSearch:v1` | 关键词搜索 |
| 删除过期 | `redcity:search.deleteDataItemRequest:v1` | 可选 |

**确定性**：⚠️ 中。数据项 schema 和搜索效果需实测。

---

### P2 — 项目管理

#### F6: 从信号创建待办

**用户体验**：用户回复某条信号"跟进一下"，Bot 创建待办任务。

**所需权限**：`hitodo:content:write` + `im:message`

**所需 API**：
| 步骤 | API 别名 | 说明 |
|---|---|---|
| 创建待办 | `hitodo:content:createTask:v1` | 创建任务 |
| 查询待办 | `hitodo:content:pageQueryTaskList:v1` | "我的待办" |
| 完成待办 | `hitodo:content:closeTask:v1` | 关闭 |
| 更新待办 | `hitodo:content:updateTask:v1` | 改截止日期等 |

**确定性**：⚠️ 中。具体参数需调试。

---

#### F7: 群管理

**用户体验**：Bot 创建专题讨论群，自动拉入相关同事。

**所需权限**：`im:chat`

**所需 API**：
| 步骤 | API 别名 | 说明 |
|---|---|---|
| 创建群 | `im:chat.createGroupChat:v2` | 创建专题群 |
| 加人 | `im:chat.addMembers:v1` | 拉入成员 |
| 查询群信息 | `im:chat.queryGroupChat:v1` | 获取群状态 |

**确定性**：✅ 高

---

### P3 — 知识沉淀

#### F8: 文档空间管理

**用户体验**：日报/周报自动归档到统一文档空间。

**所需权限**：`redoc:menu:read` + `redoc:docinfo:readwrite` + `redoc:permission:readwrite`

**确定性**：✅ 高。F1/F2 的自然延伸。

---

#### F9: 图表/可视化推送

**用户体验**：趋势图、信号分布图以图片发到群里。

**所需权限**：`file:upload` + `im:message`

**确定性**：⚠️ 中。需服务端生成图表（matplotlib），工作量较大。

---

## 权限汇总

| 权限 | 使用功能 | 优先级 |
|---|---|---|
| `im:message` | F1, F2, F3, F4, F6, F7, F9 | P0 |
| `redcity:asn:wr` | F3 | P0 |
| `redcity:card` | F1, F2 | P0 |
| `redoc:docinfo:readwrite` | F1, F2, F8 | P0 |
| `im:chat` | F7 | P1 |
| `redoc:permission:readwrite` | F2, F8 | P1 |
| `redoc:menu:read` | F8 | P2 |
| `hitodo:content:write` | F6 | P2 |
| `redcity:search:wr` | F5 | P2 |
| `redcity:search:readonly` | F5 | P2 |
| `file:upload` | F9 | P3 |

---

## 卡点与依赖

| # | 卡点 | 状态 | 阻塞范围 | 负责人/说明 |
|---|---|---|---|---|
| 1 | **Hi 应用权限审批** | 🔴 未提交 | F1-F9 全部功能 | 需夏月审批 11 项权限（见权限汇总），SIT 可能免审，prod 需 OA 单 |
| 2 | **X API 购买** | 🔴 未启动 | 方案 B 完全落地、去掉 MacBook x-monitor 依赖 | Basic $100/月，需走采购流程。当前可用 x-monitor 替代，**非阻塞** |
| 3 | **AI API Key（服务器端）** | 🟡 部分就绪 | 方案 B 信号提取、F2 周报、F4 问答 | DeepSeek key 已有但在 MacBook .env 里；需在服务器 .env 配置。或申请内部 AI (hibo/Darwin) 接入 |
| 4 | App Secret | 🟡 已有未配置 | F1-F9 全部功能 | 开放平台基础信息页可复制，需写入服务器 .env |
| 5 | 测试群 / contactId | 🔴 未创建 | Phase 1 测试 | 建一个测试群把 bot 拉进去，或获取自己的 contactId |
| 6 | 服务器部署环境 | 🟡 待确认 | 全部服务器端功能 | 需一台内网机器/容器，Python 3.9+，能访问 Hi API + GitHub + DeepSeek |

### 卡点优先级

```
                      紧急
                       ↑
   ┌─────────────────────────────────────┐
   │  1. 权限审批（阻塞一切）              │
   │  5. 测试群（阻塞验证）               │
   ├─────────────────────────────────────┤
   │  4. App Secret（配置即可）            │
   │  6. 服务器环境（可先本地开发）         │
   │  3. AI API Key（方案A暂不需要）       │
   ├─────────────────────────────────────┤
   │  2. X API 购买（非阻塞，未来优化）    │
   └─────────────────────────────────────┘
                       ↓
                     不急
```

### 建议行动

1. **现在**：提交权限审批（找夏月）+ 建测试群 + App Secret 写入 .env
2. **权限通过后**：Phase 1 开发（方案 A，无 AI 依赖，纯 API 对接）
3. **Phase 1 上线后**：评估是否需要方案 B → 如需要，配置服务器端 AI Key
4. **用户 >5 人后**：评估 X API Basic 采购

---

## 实施路线

| 阶段 | 功能 | 依赖 |
|---|---|---|
| **Phase 1** | F1 日报推送 + F3 私信推送 | 卡点 1（权限）、4（Secret）、5（测试群） |
| **Phase 2** | F4 群内问答（WebSocket + 流式） | Phase 1、卡点 3（AI Key） |
| **Phase 3** | F2 周报 + F5 搜索索引 | Phase 1 复用 |
| **Phase 4** | F6 待办 + F7 群管理 | 按需 |
| **Phase 5** | F8 文档空间 + F9 图表 | file:upload 权限 |

---

## 技术要求

### 服务器端

```
hi-bot/
├── config/
│   ├── .env                    # App ID, Secret, Token, API keys
│   └── bot_config.yaml         # 推送群列表、定时规则、订阅者、定制化配置
├── src/
│   ├── auth.py                 # Token 管理（自动刷新 AppAccessToken）
│   ├── ws_handler.py           # WebSocket 长连接、心跳、消息接收
│   ├── hi_api.py               # Hi Open Platform API 封装
│   ├── scheduler.py            # 定时任务（日报推送、git pull）
│   ├── query_handler.py        # 用户查询处理
│   ├── data_sync.py            # git pull + 数据读取
│   ├── ai_client.py            # AI 调用（内部AI / DeepSeek / Kimi）
│   └── signal_processor.py     # [方案B] 信号提取+洞察（从 raw items）
├── data/                       # git clone of ai-frontier-insight
└── run.py                      # 主入口
```

### 关键技术点

| 项目 | 方案 |
|---|---|
| 常驻进程 | asyncio event loop: WebSocket + 定时任务并发 |
| Token 刷新 | AppAccessToken 2h 过期，后台定时刷新 |
| 数据同步 | 每 30 分钟 git pull，推送前强制 pull |
| 消息幂等 | eventId 去重 |
| 断线重连 | WebSocket 自动重连，指数退避 |
| 心跳 | 每 5 秒 PING |
| 流式回复 | chunk 10-20 字符，确保 controlFinish |
| 错误处理 | API 重试 3 次，持续失败告警 |

### 凭证

| 凭证 | 来源 |
|---|---|
| App ID | `app34e354c427a8d711f0c694f5ad722646` |
| App Secret | 开放平台基础信息页（待填入 .env） |
| Robot Access Token | 开放平台基础信息页 |
| DeepSeek API Key | 现有 |
