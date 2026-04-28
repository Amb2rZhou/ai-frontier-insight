"""Wiki auto-maintenance — updates wiki pages after daily signal extraction."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

WIKI_ROOT = Path(__file__).resolve().parents[2] / "wiki"

# Maps keywords (lowercase) → wiki page relative path (without .md)
ENTITY_MAP = {
    # Companies
    "openai": "companies/openai",
    "open ai": "companies/openai",
    "sam altman": "companies/openai",
    "chatgpt": "companies/openai",
    "anthropic": "companies/anthropic",
    "dario amodei": "companies/anthropic",
    "google": "companies/google-deepmind",
    "deepmind": "companies/google-deepmind",
    "google deepmind": "companies/google-deepmind",
    "meta": "companies/meta",
    "meta ai": "companies/meta",
    "microsoft": "companies/microsoft",
    "nvidia": "companies/nvidia",
    "jensen huang": "companies/nvidia",
    "xai": "companies/xai",
    "x.ai": "companies/xai",
    "elon musk": "companies/xai",
    "alibaba": "companies/alibaba",
    "阿里": "companies/alibaba",
    "通义": "companies/alibaba",
    "tencent": "companies/tencent",
    "腾讯": "companies/tencent",
    "bytedance": "companies/bytedance",
    "字节": "companies/bytedance",
    "hugging face": "companies/hugging-face",
    "huggingface": "companies/hugging-face",
    "perplexity": "companies/perplexity",
    "salesforce": "companies/salesforce",
    "scale ai": "companies/scale-ai",
    "cursor": "companies/cursor-ai",
    "apple": "companies/apple",
    # Products
    "claude": "products/claude",
    "claude code": "products/claude",
    "opus": "products/claude",
    "sonnet": "products/claude",
    "haiku": "products/claude",
    "gpt-5": "products/gpt",
    "gpt-4": "products/gpt",
    "chatgpt": "products/gpt",
    "codex": "products/codex",
    "gemini": "products/gemini",
    "gemma": "products/gemma",
    "qwen": "products/qwen",
    "千问": "products/qwen",
    "grok": "products/grok",
    "copilot": "products/copilot",
    "sora": "products/sora",
    "muse spark": "products/muse-spark",
    "openclaw": "products/openclaw",
    "ollama": "products/ollama",
    # Technologies
    "mcp": "technologies/mcp-protocol",
    "model context protocol": "technologies/mcp-protocol",
    "agent framework": "technologies/agent-frameworks",
    "agent sdk": "technologies/agent-frameworks",
    "ai agent": "technologies/agent-frameworks",
    "agentic": "technologies/agent-frameworks",
    "computer use": "technologies/computer-use",
    "computer-use": "technologies/computer-use",
    "multi-agent": "technologies/multi-agent-systems",
    "multi agent": "technologies/multi-agent-systems",
    "swarm": "technologies/multi-agent-systems",
    "rag": "technologies/rag",
    "retrieval": "technologies/rag",
    # Trends
    "embodied ai": "trends/embodied-ai",
    "robot": "trends/embodied-ai",
    "humanoid": "trends/embodied-ai",
    "open source model": "trends/open-source-models",
    "open-source model": "trends/open-source-models",
    "ai safety": "trends/ai-safety",
    "ai security": "trends/ai-security",
}

# Tags from signal extraction → wiki pages
TAG_MAP = {
    "openai": "companies/openai",
    "anthropic": "companies/anthropic",
    "google": "companies/google-deepmind",
    "meta": "companies/meta",
    "microsoft": "companies/microsoft",
    "nvidia": "companies/nvidia",
    "头部公司战略动作": None,  # too generic
    "agent 与新交互范式": "technologies/agent-frameworks",
    "开源生态": "trends/open-source-models",
    "ai 辅助编程": "products/codex",
    "内容安全与治理": "trends/ai-safety",
    "企业应用": "trends/enterprise-agents",
    "多模态生成": "trends/creative-ai",
    "腾讯": "companies/tencent",
    "阿里巴巴": "companies/alibaba",
}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown. Returns (metadata, body)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip()
    return meta, "---" + parts[1] + "---" + parts[2]


def _update_frontmatter_date(content: str, date: str) -> str:
    """Update the 'updated:' field in frontmatter."""
    return re.sub(
        r"(updated:\s*)\d{4}-\d{2}-\d{2}",
        f"\\g<1>{date}",
        content,
        count=1,
    )


def _has_timeline_entry(content: str, date: str, title: str) -> bool:
    """Check if a similar timeline entry already exists."""
    short_title = title[:40].lower()
    for line in content.split("\n"):
        if date in line and short_title in line.lower():
            return True
    return False


def _add_wiki_links(title: str, current_page: str = "") -> str:
    """Add [[wiki-link]] to entity mentions in a timeline entry title."""
    linked_spans: list[tuple[int, int]] = []

    candidates: list[tuple[str, str, int, int]] = []
    title_lower = title.lower()
    for keyword, page in ENTITY_MAP.items():
        if page == current_page:
            continue
        kw_lower = keyword.lower()
        start = 0
        while True:
            idx = title_lower.find(kw_lower, start)
            if idx < 0:
                break
            end = idx + len(keyword)
            if idx > 0 and title_lower[idx - 1].isalnum():
                start = end
                continue
            if end < len(title_lower) and title_lower[end].isalnum():
                start = end
                continue
            candidates.append((keyword, page, idx, end))
            break

    candidates.sort(key=lambda c: (-len(c[0]), c[2]))

    linked_pages: set[str] = set()
    for keyword, page, idx, end in candidates:
        if page in linked_pages:
            continue
        if any(idx < se and end > ss for ss, se in linked_spans):
            continue
        linked_pages.add(page)
        linked_spans.append((idx, end))

    for idx, end in sorted(linked_spans, reverse=True):
        original = title[idx:end]
        page = None
        for kw, p, i, e in candidates:
            if i == idx and e == end:
                page = p
                break
        if page:
            page_name = page.split("/")[-1]
            title = f"{title[:idx]}[[{page_name}|{original}]]{title[end:]}"
    return title


def _insert_timeline_entry(content: str, date: str, title: str,
                           current_page: str = "") -> str:
    """Insert a timeline entry in reverse-chronological order under ## Timeline (newest first)."""
    title = _add_wiki_links(title, current_page)
    entry = f"- **{date}**: {title}"
    lines = content.split("\n")
    timeline_idx = -1

    for i, line in enumerate(lines):
        if line.strip() == "## Timeline":
            timeline_idx = i
            break

    if timeline_idx < 0:
        return content

    first_entry_idx = timeline_idx + 1
    while first_entry_idx < len(lines) and not lines[first_entry_idx].startswith("- **"):
        if lines[first_entry_idx].startswith("## "):
            break
        first_entry_idx += 1

    insert_idx = first_entry_idx
    for i in range(first_entry_idx, len(lines)):
        if not lines[i].startswith("- **"):
            break
        existing_date = lines[i][4:14] if len(lines[i]) > 14 else ""
        if existing_date <= date:
            insert_idx = i
            break
        insert_idx = i + 1

    lines.insert(insert_idx, entry)
    return "\n".join(lines)



def _match_insights_to_pages(insights: list[dict]) -> dict[str, list[dict]]:
    """Match each insight to relevant wiki pages. Returns {page_path: [insights]}."""
    matches: dict[str, list[dict]] = {}

    for insight in insights:
        title = insight.get("title", "")
        signal = insight.get("signal_text", "")
        tags = insight.get("tags", [])
        text_blob = f"{title} {signal}".lower()

        matched_pages = set()

        for keyword, page in ENTITY_MAP.items():
            if keyword.lower() in text_blob:
                matched_pages.add(page)

        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in TAG_MAP and TAG_MAP[tag_lower]:
                matched_pages.add(TAG_MAP[tag_lower])
            for keyword, page in ENTITY_MAP.items():
                if keyword in tag_lower:
                    matched_pages.add(page)

        for page in matched_pages:
            if page not in matches:
                matches[page] = []
            matches[page].append(insight)

    return matches


def update_wiki(date: str, insights: list[dict]) -> dict:
    """Update wiki pages based on today's insights.

    Returns stats dict with pages_updated, pages_created, entries_added.
    """
    stats = {"pages_updated": 0, "pages_created": 0, "entries_added": 0}

    if not WIKI_ROOT.exists():
        print("  - Wiki directory not found, skipping")
        return stats

    if not insights:
        return stats

    page_insights = _match_insights_to_pages(insights)

    for page_rel, page_insights_list in page_insights.items():
        page_path = WIKI_ROOT / f"{page_rel}.md"

        if not page_path.exists():
            continue

        content = page_path.read_text(encoding="utf-8")
        modified = False

        for insight in page_insights_list:
            title = insight.get("title", "")
            if not title:
                continue

            if _has_timeline_entry(content, date, title):
                continue

            content = _insert_timeline_entry(content, date, title, page_rel)
            stats["entries_added"] += 1
            modified = True

        if modified:
            content = _update_frontmatter_date(content, date)
            page_path.write_text(content, encoding="utf-8")
            stats["pages_updated"] += 1

    return stats
