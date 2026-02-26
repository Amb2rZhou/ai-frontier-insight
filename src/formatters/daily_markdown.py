"""Daily Brief markdown formatter for RedCity webhook.

输出两条消息：
  消息1: Key Frontier Signals（尽可能多条）
  消息2: Frontier Trend Summary

颜色方案（RedCity 仅支持 3 种）：
  - 黑色（默认）→ Insight
  - info（绿色）→ Implication
  - comment（灰色）→ 辅助信息
"""

from typing import Dict, List, Tuple

MAX_CONTENT_BYTES = 8000
OVERHEAD_BYTES = 200


def _first_source_url(sources: list) -> str:
    """Get first valid source URL."""
    for s in sources:
        url = s.get("url", "")
        if url:
            return url
    return ""


def _format_source_tag(sources: list) -> str:
    """Format source attribution line.

    Rules:
      - Twitter/X sources → show @username
      - Other sources → show source name (e.g. TechCrunch, Arxiv)
      - Multiple sources → join with " | "
    """
    if not sources:
        return ""

    tags = []
    for s in sources:
        name = s.get("name", "")
        url = s.get("url", "")
        # Twitter sources: extract @handle from name like "Twitter (@tegmark)"
        if "twitter" in name.lower() or "x.com" in url:
            # Extract @handle
            if "(@" in name:
                handle = name.split("(@")[1].rstrip(")")
                tags.append(f"@{handle}")
            elif "@" in name:
                tags.append(name)
            else:
                tags.append(name)
        else:
            tags.append(name if name else "Link")
    # Deduplicate while preserving order
    seen = set()
    unique_tags = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)
    return " | ".join(unique_tags)


def _render_signal(i: int, item: Dict) -> str:
    """Render a single signal block with color coding, source link, and attribution."""
    parts = []
    title = item.get("title", "Untitled")
    signal_text = item.get("signal_text", "")
    insight = item.get("insight", "")
    implication = item.get("implication", "")
    sources = item.get("sources", [])

    # Title with optional source link
    source_url = _first_source_url(sources)
    if source_url:
        parts.append(f"**Signal {i}: [{title}]({source_url})**")
    else:
        parts.append(f"**Signal {i}: {title}**")

    # Source attribution (gray)
    source_tag = _format_source_tag(sources)
    if source_tag:
        parts.append(f'<font color="comment">Source: {source_tag}</font>')

    # Summary (plain)
    if signal_text:
        parts.append(f"> {signal_text}")

    # Insight (black)
    if insight:
        parts.append(f"> 💡 {insight}")

    # Implication (green)
    if implication:
        parts.append(f'> <font color="info">→ {implication}</font>')

    parts.append("")
    return "\n".join(parts)


def _clean_trend_summary(trend_summary: str) -> str:
    """Strip echoed prompt data from trend summary."""
    if not trend_summary:
        return ""
    for marker in ["今日 top signals", "今日top signals", "趋势走向：",
                    "Today's top signals", "Trend trajectories"]:
        idx = trend_summary.find(marker)
        if idx > 0:
            trend_summary = trend_summary[:idx].rstrip()
            break
    return trend_summary.strip()


def format_daily_brief(date: str, insights: List[Dict],
                       trend_summary: str = "") -> List[str]:
    """Format daily brief as exactly 2 messages.

    Message 1: header + as many signals as fit within 8KB budget.
    Message 2: remaining signals + Frontier Trend Summary.

    Returns:
        List of 1-2 messages.
    """
    if not insights:
        return [f"# AI Frontier Daily Brief\n**日期：{date}**\n\n> 今日无重大前沿信号。"]

    footer = f'\n<font color="comment">AI Frontier Insight Bot</font>'

    # Render all signal blocks
    rendered = []
    for i, item in enumerate(insights, 1):
        rendered.append(_render_signal(i, item))

    # --- Message 1: pack as many signals as possible ---
    msg1_header = f"# AI Frontier Daily Brief\n**日期：{date}**\n\n## 一、Key Frontier Signals\n\n"
    msg1_budget = MAX_CONTENT_BYTES - len(msg1_header.encode("utf-8")) - len(footer.encode("utf-8")) - OVERHEAD_BYTES

    msg1_blocks = []
    msg1_bytes = 0
    split_at = len(rendered)  # default: all fit in msg1

    for idx, block in enumerate(rendered):
        block_bytes = len(block.encode("utf-8"))
        if msg1_bytes + block_bytes > msg1_budget:
            split_at = idx
            break
        msg1_blocks.append(block)
        msg1_bytes += block_bytes

    msg1 = msg1_header + "\n".join(msg1_blocks) + footer

    # --- Message 2: remaining signals + trend summary ---
    remaining = rendered[split_at:]
    trend_text = _clean_trend_summary(trend_summary)

    msg2_parts = []
    if remaining:
        msg2_parts.append(f"## 一、Key Frontier Signals（续）\n")
        msg2_parts.append("\n".join(remaining))

    if trend_text:
        msg2_parts.append(f"## 二、Frontier Trend Summary（{date}）\n")
        msg2_parts.append(trend_text)

    if msg2_parts:
        msg2 = "\n".join(msg2_parts) + footer
        return [msg1, msg2]

    return [msg1]
