"""Daily Brief markdown formatter for RedCity webhook."""

from typing import Dict, List


def format_daily_brief(date: str, insights: List[Dict],
                       trend_summary: str = "") -> str:
    """Format daily brief data into RedCity-compatible markdown.

    Args:
        date: Date string (YYYY-MM-DD)
        insights: List of enriched signal dicts with insight/implication
        trend_summary: Cross-source trend paragraph

    Returns:
        Markdown string for webhook
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
            signal_text = item.get("signal_text", "")
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

            if signal_text:
                lines.append(f"> {signal_text}")

            if insight:
                lines.append(f'> <font color="info">💡 {insight}</font>')

            if implication:
                lines.append(f'> <font color="warning">→ {implication}</font>')

            # Source links
            sources = item.get("sources", [])
            if sources:
                source_links = " · ".join(
                    f"[{s.get('name', 'link')}]({s.get('url', '')})"
                    for s in sources[:3] if s.get("url")
                )
                if source_links:
                    lines.append(source_links)

            lines.append("")  # blank line between items

    # Trend summary at the bottom
    if trend_summary:
        lines.append("───────────────")
        lines.append("## 📊 Trend Observation")
        lines.append(trend_summary)
        lines.append("")

    lines.append(f"---\n共 {len(insights)} 条前沿信号")

    return "\n".join(lines)
