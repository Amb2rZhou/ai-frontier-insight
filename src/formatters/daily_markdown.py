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


def format_signals_messages(date: str, insights: List[Dict]) -> List[str]:
    """Format signals into multiple messages, each within size budget.

    First message includes full header; continuation messages have a short header.
    """
    if not insights:
        return [f"# AI Frontier Daily Brief\n**日期：{date}**\n\n> 今日无重大前沿信号。"]

    first_header = f"# AI Frontier Daily Brief\n**日期：{date}**\n\n## 一、Key Frontier Signals\n\n"
    footer = f'\n<font color="comment">AI Frontier Insight Bot</font>'

    messages = []
    current_blocks = []
    current_header = first_header
    used_bytes = 0

    for i, item in enumerate(insights, 1):
        block = _render_signal(i, item)
        block_bytes = len(block.encode("utf-8"))
        budget = MAX_CONTENT_BYTES - len(current_header.encode("utf-8")) - len(footer.encode("utf-8")) - OVERHEAD_BYTES

        if used_bytes + block_bytes > budget and current_blocks:
            # Flush current message
            messages.append(current_header + "\n".join(current_blocks) + footer)
            # Next message uses a short continuation header
            current_header = f"## 一、Key Frontier Signals（续）\n\n"
            current_blocks = []
            used_bytes = 0

        current_blocks.append(block)
        used_bytes += block_bytes

    if current_blocks:
        messages.append(current_header + "\n".join(current_blocks) + footer)

    return messages


def format_trend_message(date: str, trend_summary: str) -> str:
    """Format message 2: Frontier Trend Summary."""
    if not trend_summary:
        return ""

    # Strip echoed prompt data
    for marker in ["今日 top signals", "今日top signals", "趋势走向：",
                    "Today's top signals", "Trend trajectories"]:
        idx = trend_summary.find(marker)
        if idx > 0:
            trend_summary = trend_summary[:idx].rstrip()
            break

    if not trend_summary.strip():
        return ""

    lines = []
    lines.append(f"## 二、Frontier Trend Summary（{date}）")
    lines.append("")
    lines.append(trend_summary.strip())
    lines.append("")
    lines.append(f'<font color="comment">AI Frontier Insight Bot</font>')

    return "\n".join(lines)


def format_daily_brief(date: str, insights: List[Dict],
                       trend_summary: str = "") -> List[str]:
    """Format daily brief as multiple messages.

    Tries to merge trend summary into the last signal message if it fits.

    Returns:
        List of messages.
    """
    messages = format_signals_messages(date, insights)
    trend_msg = format_trend_message(date, trend_summary)
    if trend_msg:
        # Try appending trend to last message
        if messages:
            merged = messages[-1] + "\n\n" + trend_msg
            if len(merged.encode("utf-8")) <= MAX_CONTENT_BYTES:
                messages[-1] = merged
            else:
                messages.append(trend_msg)
        else:
            messages.append(trend_msg)
    return messages
