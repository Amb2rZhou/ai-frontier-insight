"""Daily Brief markdown formatter for RedCity webhook.

RedCity webhook 消息大小限制约 8KB，需要控制输出长度。
"""

from typing import Dict, List

# RedCity webhook 安全上限（bytes），留余量
MAX_CONTENT_BYTES = 7500


def format_daily_brief(date: str, insights: List[Dict],
                       trend_summary: str = "") -> str:
    """Format daily brief data into RedCity-compatible markdown.

    Args:
        date: Date string (YYYY-MM-DD)
        insights: List of enriched signal dicts with insight/implication
        trend_summary: Cross-source trend paragraph

    Returns:
        Markdown string for webhook (within size limit)
    """
    lines = [f"# AI Frontier Brief {date}"]

    if not insights:
        lines.append("\n> No significant signals detected today.")
        return "\n".join(lines)

    # Category grouping
    categories = {}
    category_icons = {
        "model_release": "🚀",
        "research_breakthrough": "🔬",
        "strategic_move": "♟️",
        "ecosystem_shift": "🌐",
        "infrastructure": "⚙️",
        "open_source": "📦",
    }

    for item in insights:
        cat = item.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)

    # Render each category
    for cat, items in categories.items():
        icon = category_icons.get(cat, "📌")
        cat_name = cat.replace("_", " ").title()
        lines.append("───────────────")
        lines.append(f"## {icon} {cat_name}")

        for item in items:
            title = item.get("title", "Untitled")
            strength = item.get("signal_strength", 0)
            insight = item.get("insight", "")
            implication = item.get("implication", "")

            # Strength indicator
            if strength >= 0.8:
                strength_bar = "🔴"
            elif strength >= 0.6:
                strength_bar = "🟡"
            else:
                strength_bar = "🟢"

            lines.append(f"**{strength_bar} {title}**")

            # Compact: insight + implication only (skip signal_text to save space)
            if insight:
                lines.append(f"> 💡 {insight}")

            if implication:
                lines.append(f"> → {implication}")

            # Source links (compact, max 2)
            sources = item.get("sources", [])
            if sources:
                source_links = " · ".join(
                    f"[{s.get('name', 'link')}]({s.get('url', '')})"
                    for s in sources[:2] if s.get("url")
                )
                if source_links:
                    lines.append(source_links)

            lines.append("")

            # Check size limit — stop adding items if approaching limit
            current = "\n".join(lines).encode("utf-8")
            if len(current) > MAX_CONTENT_BYTES:
                remaining = len(insights) - sum(len(v) for v in categories.values())
                if remaining > 0:
                    lines.append(f"*...及其他 {remaining} 条信号*")
                break

    # Trend summary at the bottom (truncate if needed)
    if trend_summary:
        lines.append("───────────────")
        lines.append("## 📊 Trend Observation")
        # Truncate trend summary if total would exceed limit
        current_size = len("\n".join(lines).encode("utf-8"))
        trend_bytes = len(trend_summary.encode("utf-8"))
        if current_size + trend_bytes + 100 > MAX_CONTENT_BYTES:
            # Truncate trend summary to fit
            available = MAX_CONTENT_BYTES - current_size - 100
            if available > 200:
                truncated = trend_summary.encode("utf-8")[:available].decode("utf-8", errors="ignore")
                last_period = max(truncated.rfind("。"), truncated.rfind("。"), truncated.rfind(". "))
                if last_period > len(truncated) * 0.5:
                    truncated = truncated[:last_period + 1]
                lines.append(truncated)
            # else skip trend summary entirely
        else:
            lines.append(trend_summary)
        lines.append("")

    lines.append(f"---\n共 {len(insights)} 条前沿信号")

    return "\n".join(lines)
