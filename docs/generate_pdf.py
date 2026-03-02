#!/usr/bin/env python3
"""Generate product-overview.pdf from structured content using reportlab.

Usage: python3 docs/generate_pdf.py
Output: docs/product-overview.pdf
"""

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Preformatted,
)

# ── Paths ──────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PDF = SCRIPT_DIR / "product-overview.pdf"

# ── Font Registration ──────────────────────────────────────────
# Try multiple Chinese font paths (macOS)
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/STHeiti Light.ttc",
]

_cn_font = "Helvetica"
_cn_font_bold = "Helvetica-Bold"

for fp in _FONT_CANDIDATES:
    if os.path.exists(fp):
        try:
            pdfmetrics.registerFont(TTFont("CnFont", fp, subfontIndex=0))
            pdfmetrics.registerFont(TTFont("CnFontBold", fp, subfontIndex=0))
            _cn_font = "CnFont"
            _cn_font_bold = "CnFontBold"
            break
        except Exception:
            continue

# ── Color Palette ──────────────────────────────────────────────
C_PRIMARY = colors.HexColor("#1a1a2e")
C_ACCENT = colors.HexColor("#16213e")
C_HIGHLIGHT = colors.HexColor("#0f3460")
C_BLUE = colors.HexColor("#2563eb")
C_LIGHT_BG = colors.HexColor("#f8f9fa")
C_TABLE_HEADER = colors.HexColor("#1e3a5f")
C_TABLE_HEADER_TEXT = colors.white
C_TABLE_ALT = colors.HexColor("#f0f4f8")
C_BORDER = colors.HexColor("#d1d5db")
C_GRAY = colors.HexColor("#6b7280")

# ── Styles ─────────────────────────────────────────────────────
styles = getSampleStyleSheet()


def _s(name, **kw):
    """Create a named ParagraphStyle."""
    return ParagraphStyle(name, **kw)


S_TITLE = _s("DocTitle", fontName=_cn_font_bold, fontSize=22, leading=30,
             alignment=TA_CENTER, textColor=C_PRIMARY, spaceAfter=4*mm)
S_SUBTITLE = _s("DocSubtitle", fontName=_cn_font, fontSize=11, leading=16,
                alignment=TA_CENTER, textColor=C_GRAY, spaceAfter=12*mm)
S_H1 = _s("H1", fontName=_cn_font_bold, fontSize=16, leading=22,
          textColor=C_PRIMARY, spaceBefore=10*mm, spaceAfter=4*mm,
          borderWidth=0, borderPadding=0)
S_H2 = _s("H2", fontName=_cn_font_bold, fontSize=13, leading=18,
          textColor=C_ACCENT, spaceBefore=6*mm, spaceAfter=3*mm)
S_H3 = _s("H3", fontName=_cn_font_bold, fontSize=11, leading=15,
          textColor=C_HIGHLIGHT, spaceBefore=4*mm, spaceAfter=2*mm)
S_BODY = _s("Body", fontName=_cn_font, fontSize=9.5, leading=15,
            alignment=TA_JUSTIFY, spaceAfter=2*mm)
S_BULLET = _s("Bullet", fontName=_cn_font, fontSize=9.5, leading=15,
              leftIndent=12, bulletIndent=4, spaceAfter=1.5*mm)
S_BULLET2 = _s("Bullet2", fontName=_cn_font, fontSize=9, leading=14,
               leftIndent=24, bulletIndent=16, spaceAfter=1*mm)
S_CODE = _s("Code", fontName="Courier", fontSize=7.5, leading=11,
            leftIndent=8, textColor=colors.HexColor("#1f2937"),
            backColor=C_LIGHT_BG, borderWidth=0.5, borderColor=C_BORDER,
            borderPadding=6, spaceAfter=3*mm)
S_TABLE_H = _s("TH", fontName=_cn_font_bold, fontSize=8.5, leading=12,
               textColor=C_TABLE_HEADER_TEXT, alignment=TA_CENTER)
S_TABLE_C = _s("TC", fontName=_cn_font, fontSize=8.5, leading=12)
S_FOOTER = _s("Footer", fontName=_cn_font, fontSize=7.5, leading=10,
              textColor=C_GRAY, alignment=TA_CENTER)


# ── Helper Functions ───────────────────────────────────────────

def h1(text):
    return Paragraph(text, S_H1)

def h2(text):
    return Paragraph(text, S_H2)

def h3(text):
    return Paragraph(text, S_H3)

def p(text):
    return Paragraph(text, S_BODY)

def bullet(text, level=1):
    style = S_BULLET if level == 1 else S_BULLET2
    return Paragraph(f"<bullet>&bull;</bullet> {text}", style)

def spacer(h=3):
    return Spacer(1, h * mm)

def code_block(text):
    return Preformatted(text, S_CODE)

def make_table(headers, rows, col_widths=None):
    """Create a styled table."""
    page_width = A4[0] - 2 * 20 * mm
    header_row = [Paragraph(h, S_TABLE_H) for h in headers]
    data_rows = []
    for row in rows:
        data_rows.append([Paragraph(str(c), S_TABLE_C) for c in row])
    all_data = [header_row] + data_rows

    if col_widths is None:
        n = len(headers)
        col_widths = [page_width / n] * n

    t = Table(all_data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), C_TABLE_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_TABLE_HEADER_TEXT),
        ("FONTNAME", (0, 0), (-1, 0), _cn_font_bold),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("FONTNAME", (0, 1), (-1, -1), _cn_font),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    # Alternate row colors
    for i in range(1, len(all_data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), C_TABLE_ALT))
    t.setStyle(TableStyle(style_cmds))
    return t


# ── Page Templates ─────────────────────────────────────────────

def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    # Footer
    canvas.setFont(_cn_font, 7.5)
    canvas.setFillColor(C_GRAY)
    canvas.drawCentredString(w / 2, 12 * mm,
                             f"AI Frontier Insight Bot — 产品技术文档  |  第 {doc.page} 页")
    # Top line
    canvas.setStrokeColor(C_BORDER)
    canvas.setLineWidth(0.3)
    canvas.line(20 * mm, h - 14 * mm, w - 20 * mm, h - 14 * mm)
    # Bottom line
    canvas.line(20 * mm, 18 * mm, w - 20 * mm, 18 * mm)
    canvas.restoreState()


def _cover_footer(canvas, doc):
    canvas.saveState()
    w, _ = A4
    canvas.setFont(_cn_font, 7.5)
    canvas.setFillColor(C_GRAY)
    canvas.drawCentredString(w / 2, 12 * mm, "Confidential — Internal Use")
    canvas.restoreState()


# ── Document Content ───────────────────────────────────────────

def build_content():
    """Build the full document content as a list of Flowables."""
    pw = A4[0] - 2 * 20 * mm  # page width minus margins
    story = []

    # ── Cover Page ──
    story.append(Spacer(1, 50 * mm))
    story.append(Paragraph("AI Frontier Insight Bot", S_TITLE))
    story.append(Paragraph("产品技术文档", _s("CoverSub", fontName=_cn_font_bold,
                           fontSize=16, leading=22, alignment=TA_CENTER,
                           textColor=C_ACCENT, spaceAfter=8*mm)))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("自动化 AI 前沿情报采集、分析与推送系统",
                           S_SUBTITLE))
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("核心价值：从噪声中提取信号、从信号中生成洞察",
                           _s("CoverValue", fontName=_cn_font, fontSize=11,
                              leading=16, alignment=TA_CENTER,
                              textColor=C_HIGHLIGHT)))
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph("文档版本：v1.0 | 2026-03-02",
                           _s("CoverDate", fontName=_cn_font, fontSize=9,
                              leading=14, alignment=TA_CENTER,
                              textColor=C_GRAY)))
    story.append(NextPageTemplate("normal"))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # 一、产品概述
    # ═══════════════════════════════════════════════════════════
    story.append(h1("一、产品概述"))
    story.append(p(
        "<b>AI Frontier Insight Bot</b> 是一个自动化 AI 前沿情报系统，每日从多个数据源采集原始信息，"
        "通过多层过滤与 AI 分析，提炼出高价值信号与深度洞察，并自动推送至团队群聊。"
    ))
    story.append(spacer(2))
    story.append(make_table(
        ["指标", "数值"],
        [
            ["数据源平台", "5 个（X/Twitter、RSS、GitHub、ArXiv、HuggingFace）"],
            ["日均原始数据", "100–350 条"],
            ["日均精选输出", "10 条信号 + 洞察"],
            ["推送频率", "每日 08:00 CST"],
        ],
        col_widths=[pw * 0.3, pw * 0.7],
    ))

    # ═══════════════════════════════════════════════════════════
    # 二、系统架构总览
    # ═══════════════════════════════════════════════════════════
    story.append(h1("二、系统架构总览"))

    story.append(h2("2.1 数据流水线"))
    story.append(code_block(
        "Sources            Collectors         Analysis           Output\n"
        "---------      -----------      ----------      ---------\n"
        "X/Twitter -+                                              \n"
        "RSS       -|   Collectors      Signal         Markdown   \n"
        "GitHub    -+-> (RawItem) -->   Extraction --> Daily/Weekly\n"
        "ArXiv     -|   Unified         + Insight      + Webhook  \n"
        "HuggingFace+                   Generation     Delivery   \n"
        "                                   |                      \n"
        "                              +---------+                 \n"
        "                              | Memory  |                 \n"
        "                              | trends  |                 \n"
        "                              | signals |                 \n"
        "                              | history |                 \n"
        "                              +---------+                 "
    ))
    story.append(spacer(2))

    story.append(h2("2.2 关键设计决策"))
    story.append(make_table(
        ["项目", "选择", "原因"],
        [
            ["子系统划分", "x-monitor + ai-frontier-insight", "职责分离，独立迭代"],
            ["部署方式", "本地 macOS + launchd 定时任务", "零服务器成本，本地代理可用"],
            ["AI 模型", "DeepSeek V3（主力）/ Claude（备选）", "DeepSeek 性价比高，Claude 作为 fallback"],
            ["输出语言", "混合（英文术语 + 中文分析）", "适合双语技术团队"],
        ],
        col_widths=[pw * 0.18, pw * 0.38, pw * 0.44],
    ))

    # ═══════════════════════════════════════════════════════════
    # 三、数据来源与管理
    # ═══════════════════════════════════════════════════════════
    story.append(h1("三、数据来源与管理"))

    # 3.1 X/Twitter
    story.append(h2("3.1 X/Twitter（核心来源）"))
    story.append(p(
        "采集架构：独立项目 x-monitor，通过 Playwright 无头浏览器监控 X List 页面。"
    ))
    story.append(spacer(1))
    story.append(h3("已实现功能"))
    story.append(bullet(
        "<b>X List 机制</b>：通过单个 X List 聚合所有监控账号，单次请求读取整个列表，避免逐账号请求触发风控"
    ))
    story.append(bullet(
        "<b>API 响应拦截</b>：不依赖 DOM 渲染（X 在 headless 模式下阻止 DOM 渲染），"
        "拦截 ListLatestTweetsTimeline GraphQL API 响应，提取结构化数据"
    ))
    story.append(bullet(
        "<b>智能调度</b>：2–5 小时随机间隔 + 0–5 分钟抖动，日报前（07:00–07:25）强制采集"
    ))
    story.append(bullet(
        "<b>失败重试</b>：最多 2 次，10 分钟间隔；Cookie 过期自动检测 + webhook 告警"
    ))
    story.append(bullet(
        "<b>三层过滤</b>：硬规则（低价值/低互动）→ DeepSeek 语义分类 → seen_ids 去重"
    ))
    story.append(bullet(
        "<b>分页支持</b>：自动分页最多 5 页 / 500 条推文；连续已知推文时提前终止"
    ))

    story.append(spacer(2))
    story.append(h3("当前监控规模：X List 含 ~200 个 AI 领域账号"))
    story.append(p("通过 MIT Bunny 半自动筛选入库，代表人物包括："))
    story.append(make_table(
        ["类别", "代表人物"],
        [
            ["OpenAI", "Sam Altman, Mark Chen, Gabor Melis"],
            ["Anthropic", "Dario Amodei, Amanda Askell, Jack Clark"],
            ["Google DeepMind", "Demis Hassabis, Jeff Dean"],
            ["独立研究者", "Andrej Karpathy, Yann LeCun, Jim Fan, David Ha"],
            ["AI 生态", "Swyx, Simon Willison"],
            ["以及更多", "覆盖 OpenAI / Anthropic / Google / Meta / NVIDIA / 独立研究者 / KOL 等约 200 个账号"],
        ],
        col_widths=[pw * 0.25, pw * 0.75],
    ))

    story.append(spacer(2))
    story.append(h3("来源发现（半自动）"))
    story.append(bullet(
        "通过 MIT Bunny (x.mitbunny.ai) 开源项目发现 AI 领域账号"
    ))
    story.append(bullet(
        "按角色关键词（Research, Scientist, Engineer, Professor, Founder 等）+ 粉丝量（≥5000）筛选"
    ))
    story.append(bullet(
        "sync.py 脚本辅助对比差异，通过 Playwright 模拟人工操作添加/移除 List 成员"
    ))
    story.append(bullet(
        "每次最多添加 10 个 / 移除 5 个，操作间隔 5–12 秒，避免触发风控"
    ))

    story.append(spacer(2))
    story.append(h3("计划中"))
    story.append(bullet("全自动来源维护流程：定期爬取 Bunny 名单 → 对比本地 → 自动增减"))
    story.append(bullet("账号质量标注系统：基于历史内容质量自动调整优先级"))
    story.append(bullet("多账号轮换机制"))

    # 3.2 RSS
    story.append(h2("3.2 RSS 订阅源"))
    story.append(p("23 个活跃 RSS 源，覆盖 9 个分组："))
    story.append(spacer(1))
    story.append(make_table(
        ["分组", "数量", "代表来源"],
        [
            ["付费科技媒体", "1", "The Information"],
            ["英文科技媒体", "6", "TechCrunch, The Verge, Wired, Ars Technica, VentureBeat, MIT Tech Review"],
            ["官方博客", "4", "OpenAI, Google AI, Meta Engineering, Anthropic"],
            ["技术社区", "3", "Hacker News, Reddit ML, Reddit AI"],
            ["ML 平台", "1", "HuggingFace Blog"],
            ["AI 安全/对齐", "2", "LessWrong (Curated), Alignment Forum"],
            ["VC / 行业洞察", "3", "a16z Podcast, a16z 16 Minutes, a16z Live"],
            ["中文播客", "2", "硅谷101, 海外独角兽"],
            ["研究博客", "1", "Lil'Log (Lilian Weng)"],
        ],
        col_widths=[pw * 0.22, pw * 0.1, pw * 0.68],
    ))

    # 3.3 GitHub
    story.append(h2("3.3 GitHub"))
    story.append(bullet(
        "<b>Trending</b>：6 个 AI 相关 topic（artificial-intelligence, machine-learning, "
        "llm, agents, deep-learning, generative-ai）"
    ))
    story.append(bullet("<b>Releases</b>：12 个核心 repo 监控"))
    story.append(spacer(1))
    story.append(make_table(
        ["类别", "项目"],
        [
            ["模型 SDK", "openai-python, anthropic-sdk-python"],
            ["框架", "LangChain, LangGraph, AutoGen, CrewAI"],
            ["模型/推理", "Transformers, vLLM, Ollama"],
            ["前沿项目", "OpenHands, browser-use, AutoGPT"],
        ],
        col_widths=[pw * 0.25, pw * 0.75],
    ))

    # 3.4 ArXiv
    story.append(h2("3.4 ArXiv"))
    story.append(bullet("5 个类别：cs.AI, cs.CL (NLP), cs.LG (ML), cs.CV (CV), cs.MA (多智能体)"))
    story.append(bullet("按提交日期排序，最多 25 篇/天"))

    # 3.5 HuggingFace
    story.append(h2("3.5 HuggingFace"))
    story.append(bullet("Trending Models: 15 个"))
    story.append(bullet("New Models: 10 个"))
    story.append(bullet("Trending Spaces: 10 个"))

    # ═══════════════════════════════════════════════════════════
    # 四、信息处理流水线
    # ═══════════════════════════════════════════════════════════
    story.append(h1("四、信息处理流水线"))

    story.append(h2("4.1 采集层 → 统一数据格式"))
    story.append(p("所有来源统一为 RawItem 结构："))
    story.append(code_block(
        "RawItem {\n"
        "    title:       str    # Title\n"
        "    content:     str    # Body content\n"
        "    source_type: str    # Platform (twitter/rss/github/...)\n"
        "    source_name: str    # Source name\n"
        "    url:         str    # Original URL\n"
        "    published:   str    # Publish time (ISO 8601)\n"
        "    metadata:    dict   # Platform-specific metadata\n"
        "}"
    ))
    story.append(p("典型日产量：100–350 条 RawItem。"))

    story.append(h2("4.2 X-Monitor 三层过滤"))
    story.append(make_table(
        ["层级", "类型", "方法", "规则"],
        [
            ["硬规则", "确定性", "规则引擎", "去除纯转推 (RT @...)、纯链接 (<10 字符)、互动量过低"],
            ["语义过滤", "AI", "DeepSeek V3", "判断是否与 AI/ML/科技相关，不相关的剔除"],
            ["去重", "状态", "seen_ids", "已处理过的推文 ID 不重复入库"],
        ],
        col_widths=[pw * 0.12, pw * 0.12, pw * 0.16, pw * 0.60],
    ))
    story.append(spacer(2))
    story.append(h3("互动量阈值"))
    story.append(bullet("新推文（&lt;3h）：likes ≥ 1 或 views ≥ 100"))
    story.append(bullet("老推文（≥3h）：likes ≥ 3 或 views ≥ 500"))
    story.append(bullet("无互动数据时保留（信任推荐账号）"))

    story.append(h2("4.3 信号提取（Signal Extraction）"))
    story.append(bullet("<b>AI 模型</b>：DeepSeek V3（主力）/ Claude Haiku（备选），成本优先"))
    story.append(bullet("<b>输入</b>：全部 RawItem + 当前趋势 + 近期信号标题（去重参考）"))
    story.append(bullet("<b>输出</b>：最多 10 条信号，每条含 signal_strength（0–1）"))
    story.append(bullet(
        "<b>优先级</b>：突破性研究 &gt; 重要发布 &gt; 头部公司战略 &gt; 新兴模式 &gt; 重要开源"
    ))
    story.append(bullet("<b>去重规则</b>：已报道事件仅在有实质新信息时以 [Update] 形式再入选"))

    story.append(h2("4.4 洞察生成（Insight Generation）"))
    story.append(bullet("<b>AI 模型</b>：DeepSeek V3（主力）/ Claude Sonnet（备选），深度推理"))
    story.append(bullet("<b>输入</b>：信号 + 过往预测（4 周回溯）+ 趋势上下文"))
    story.append(p("每条信号附加："))
    story.append(bullet("insight — 为什么重要", level=2))
    story.append(bullet("implication — 意味着什么", level=2))
    story.append(bullet("category — 分类标签", level=2))

    story.append(h2("4.5 趋势更新"))
    story.append(bullet("<b>AI 模型</b>：DeepSeek V3 / Claude Haiku"))
    story.append(bullet("维护最多 50 条趋势，跟踪 trajectory（加速 / 稳定 / 衰退 / 消退）"))
    story.append(bullet('12 周滚动计数，自动标记无信号 &gt;2 周的趋势为\u201c消退\u201d'))

    # ═══════════════════════════════════════════════════════════
    # 五、记忆与数据存储
    # ═══════════════════════════════════════════════════════════
    story.append(h1("五、记忆与数据存储"))

    story.append(h2("5.1 目录结构"))
    story.append(code_block(
        "data/\n"
        "+-- x-monitor/{date}.json      # Raw tweets (14-day retention)\n"
        "+-- daily/{date}/\n"
        "|   +-- brief.json              # Signals + insights (permanent)\n"
        "|   +-- sources.json            # Source data (30-day retention)\n"
        "+-- weekly/{week}.json|md       # Weekly report (permanent)\n"
        "\n"
        "memory/\n"
        "+-- weekly_signals.json         # Weekly signals (12-week rolling)\n"
        "+-- trends.json                 # Trend database (max 50)\n"
        "+-- history_insights.json       # Prediction history (last 100)\n"
        "\n"
        "config/\n"
        "+-- settings.yaml               # System config\n"
        "+-- sources.yaml                # Data source definitions\n"
        "+-- drafts/{date}_daily.json    # Daily brief draft"
    ))

    story.append(h2("5.2 数据生命周期"))
    story.append(make_table(
        ["数据类型", "保留策略", "清理机制"],
        [
            ["推文原始数据", "14 天", "自动清理"],
            ["引用的原始数据", "30 天", "自动清理"],
            ["日报洞察", "永久", "—"],
            ["周报", "永久", "—"],
            ["趋势数据库", "持续更新", "超 50 条淘汰消退趋势"],
            ["信号累积", "12 周滚动", "按周自动归档"],
        ],
        col_widths=[pw * 0.30, pw * 0.30, pw * 0.40],
    ))

    story.append(h2("5.3 记忆系统的自我修正"))
    story.append(bullet(
        "<b>预测回溯</b>：生成新洞察时参考 4 周前的预测，对比实际发展，提升预测准确度"
    ))
    story.append(bullet(
        "<b>趋势自适应</b>：trajectory 随信号频率自动调整，长期无信号的趋势自动标记为消退"
    ))

    # ═══════════════════════════════════════════════════════════
    # 六、输出与推送
    # ═══════════════════════════════════════════════════════════
    story.append(h1("六、输出与推送"))

    story.append(h2("6.1 日报（已实现，全自动）"))
    story.append(make_table(
        ["项目", "详情"],
        [
            ["推送时间", "每日 08:00 CST"],
            ["推送渠道", "RedCity webhook（小红书内部群聊机器人）"],
            ["内容格式", "Markdown"],
            ["内容结构", "10 条精选信号 + insight + implication + 趋势总结"],
            ["消息分割", "分 2 条消息发送（8KB/条限制），末条 @all"],
        ],
        col_widths=[pw * 0.25, pw * 0.75],
    ))

    story.append(h2("6.2 周报（已实现，自动生成）"))
    story.append(bullet("<b>自动化</b>：通过 Claude Cowork 定时读取周数据，自动生成周报"))
    story.append(bullet("<b>三个分析维度</b>：Research Insight / Tech Trend / Company Strategy"))
    story.append(bullet(
        "<b>主题轮换</b>：每月 4 周依次覆盖 research → tech_trend → company_strategy → meta_reflection"
    ))
    story.append(bullet("<b>输出格式</b>：JSON + Markdown + DOCX"))
    story.append(bullet("<b>当前局限</b>：生成后转为 Redoc 格式仍需手动操作"))

    # ═══════════════════════════════════════════════════════════
    # 七、筛选依据与质量控制
    # ═══════════════════════════════════════════════════════════
    story.append(h1("七、筛选依据与质量控制"))

    story.append(h2("7.1 来源质量分层"))
    story.append(make_table(
        ["层级", "描述", "代表人物/来源"],
        [
            ["Tier 1", "AI 领域核心人物",
             "Sam Altman, Karpathy, Hassabis, LeCun, Amodei, Jeff Dean, Jim Fan"],
            ["Tier 2", "知名研究者、技术 KOL",
             "Askell, Jack Clark, David Ha, Swyx, Simon Willison, Melis, Mark Chen"],
            ["Tier 3", "行业观察者、新闻聚合", "AI News"],
        ],
        col_widths=[pw * 0.12, pw * 0.25, pw * 0.63],
    ))
    story.append(spacer(1))
    story.append(p("权威度（Tier）直接影响信号提取时的 signal_strength 评分。"))

    story.append(h2("7.2 内容过滤原则"))
    story.append(bullet("<b>排除</b>：日常更新、小版本迭代、无实质内容的个人观点、纯营销"))
    story.append(bullet("<b>保留</b>：突破性研究、重要产品发布、战略变化、新兴技术模式"))
    story.append(bullet("<b>去重</b>：同一事件多条信息合并为一条信号，多来源交叉验证提升可信度"))

    # ═══════════════════════════════════════════════════════════
    # 八、技术特性
    # ═══════════════════════════════════════════════════════════
    story.append(h1("八、技术特性"))

    story.append(h2("8.1 健壮性"))
    story.append(make_table(
        ["机制", "实现方式"],
        [
            ["SSL 兜底", "Python LibreSSL 失败时自动 fallback 到 curl（系统原生 TLS）"],
            ["失败重试", "x-monitor 最多 2 次重试，10 分钟间隔"],
            ["Cookie 过期检测", "自动检测 + RedCity webhook 运维告警"],
            ["代理兼容", "支持通过本地代理采集"],
            ["AI 模型 fallback", "主模型失败自动切换备选模型"],
            ["JSON 修复", "AI 返回格式异常时自动修复"],
        ],
        col_widths=[pw * 0.28, pw * 0.72],
    ))

    story.append(h2("8.2 反检测（X/Twitter）"))
    story.append(make_table(
        ["策略", "说明"],
        [
            ["API 响应拦截", "不依赖 DOM 渲染，绕过 X 的反爬机制"],
            ["Playwright Stealth", "伪装浏览器指纹，规避自动化检测"],
            ["随机调度", "2–5 小时随机间隔 + 0–5 分钟抖动"],
            ["人类模拟", "随机滚动距离、页面间随机延迟"],
        ],
        col_widths=[pw * 0.28, pw * 0.72],
    ))

    # ═══════════════════════════════════════════════════════════
    # 九、核心优势：持续进化的系统
    # ═══════════════════════════════════════════════════════════
    story.append(h1("九、核心优势：持续进化的系统"))
    story.append(p(
        "与传统静态信息聚合工具不同，AI Frontier Insight Bot 是一个<b>随时间自我进化</b>的系统。"
    ))

    story.append(h2("9.1 记忆积累驱动质量提升"))
    story.append(bullet(
        "<b>趋势数据库越用越准</b>：随着信号持续积累，趋势的 trajectory 判断基于更长的历史数据，预测准确度不断提高"
    ))
    story.append(bullet(
        "<b>预测回溯自我修正</b>：每次生成新洞察时参考 4 周前的预测，与实际发展对比，系统自动学习哪些预测更可靠"
    ))
    story.append(bullet(
        "<b>去重与信号识别增强</b>：历史信号标题库不断扩充，重复事件识别更精准，真正的新信号更容易被识别"
    ))

    story.append(h2("9.2 LLM 能力红利"))
    story.append(bullet(
        "<b>零成本享受模型升级</b>：系统分析质量直接取决于底层大语言模型能力——每一次模型迭代"
        "（更强的推理、更好的中文理解、更长的上下文），系统产出质量自动提升，无需修改任何代码"
    ))
    story.append(bullet(
        "<b>灵活切换模型</b>：架构支持 DeepSeek / Claude 动态切换，可随时采用性价比最优或能力最强的模型"
    ))

    # ═══════════════════════════════════════════════════════════
    # 十、局限性与改进方向
    # ═══════════════════════════════════════════════════════════
    story.append(h1("十、局限性与改进方向"))

    story.append(h2("10.1 当前局限"))
    story.append(make_table(
        ["局限", "影响", "缓解措施"],
        [
            ["X 采集依赖 Playwright 爬虫", "Cookie 过期、反爬风控", "重试 + 告警机制"],
            ["X 来源发现依赖 MIT Bunny", "时效性不够，筛选不够严格", "sync.py 半自动化流程"],
            ["本地部署依赖电脑开机", "关机期间无法采集", "GitHub Actions 备用流程"],
            ["Python 3.9 + LibreSSL", "SSL 兼容性问题", "curl fallback 已缓解"],
            ["DeepSeek V3 稳定性与质量", "偶发返回错误、分析深度不及 Claude", "现阶段控制成本，正式可切 Claude"],
            ["周报 Redoc 转换需手动", "生成后仍需人工发布", "计划中自动化"],
        ],
        col_widths=[pw * 0.32, pw * 0.30, pw * 0.38],
    ))

    story.append(h2("10.2 改进方向"))
    story.append(bullet("<b>X 采集升级</b>：订阅 X API，替代 Playwright 爬虫方案，彻底消除 Cookie/反爬问题"))
    story.append(bullet("<b>来源自动化管理</b>：自动发现、添加、评分、淘汰，形成闭环"))
    story.append(bullet("<b>云端部署</b>：消除本地依赖，7×24 运行"))
    story.append(bullet("<b>周报 Redoc 发布自动化</b>：打通从生成到发布的完整流程"))

    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("— 文档生成日期：2026-03-02 —", S_FOOTER))

    return story


# ── Build PDF ──────────────────────────────────────────────────

def main():
    w, h = A4
    margin = 20 * mm

    frame_cover = Frame(margin, margin, w - 2 * margin, h - 2 * margin,
                        id="cover")
    frame_normal = Frame(margin, 22 * mm, w - 2 * margin, h - 40 * mm,
                         id="normal")

    doc = BaseDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        title="AI Frontier Insight Bot — 产品技术文档",
        author="AI Frontier Insight",
    )
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame_cover],
                     onPage=_cover_footer),
        PageTemplate(id="normal", frames=[frame_normal],
                     onPage=_header_footer),
    ])

    story = build_content()
    doc.build(story)
    print(f"PDF generated: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
