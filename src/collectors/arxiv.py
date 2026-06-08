"""Paper collector — arXiv official API (export.arxiv.org).

改用 arXiv 官方 API（export.arxiv.org/api/query，返回 Atom XML），不依赖
huggingface.co（在部分网络环境下不可达）。按配置的分类拉取最新论文，按
提交时间倒序。信号筛选阶段会进一步按机构权威性过滤，这里只负责把近期论文取回来。

API: https://export.arxiv.org/api/query
"""

import subprocess
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo  # noqa: F401

import feedparser

from .base import BaseCollector, RawItem
from ..utils.config import load_sources, get_timezone  # noqa: F401

ARXIV_API = "https://export.arxiv.org/api/query"


def _curl_text(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch raw text via curl subprocess（避开 LibreSSL 在 requests 下的问题）。"""
    cmd = [
        "/usr/bin/curl", "-sS", "--max-time", str(timeout), "-L",
        "-H", "User-Agent: AI-Frontier-Insight-Bot/1.0",
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        if result.returncode != 0:
            print(f"  Papers: curl failed: {result.stderr.strip()}")
            return None
        return result.stdout
    except subprocess.TimeoutExpired as e:
        print(f"  Papers: fetch error: {e}")
        return None


def _parse_arxiv_id(entry_id: str) -> str:
    """从 http://arxiv.org/abs/2506.12345v1 提取 2506.12345。"""
    tail = entry_id.rstrip("/").split("/abs/")[-1]
    return tail.split("v")[0] if tail else tail


def _fetch_arxiv(categories: List[str], max_results: int, sort_by: str) -> List[dict]:
    """拉取并解析 arXiv API。"""
    search = "+OR+".join(f"cat:{c}" for c in categories) or "cat:cs.AI"
    url = (
        f"{ARXIV_API}?search_query={search}"
        f"&sortBy={sort_by}&sortOrder=descending"
        f"&start=0&max_results={max_results}"
    )
    xml = _curl_text(url)
    if not xml:
        return []

    feed = feedparser.parse(xml)
    papers = []
    for e in feed.entries:
        arxiv_id = _parse_arxiv_id(e.get("id", ""))
        authors = [a.get("name", "") for a in e.get("authors", []) if a.get("name")]
        cats = [t.get("term", "") for t in e.get("tags", []) if t.get("term")]
        if e.get("arxiv_primary_category"):
            primary = e.get("arxiv_primary_category", {}).get("term", "")
        else:
            primary = cats[0] if cats else ""
        papers.append({
            "arxiv_id": arxiv_id,
            "title": " ".join(e.get("title", "").split()),
            "summary": " ".join(e.get("summary", "").split()),
            "authors": authors,
            "categories": cats,
            "primary_category": primary,
            "published": e.get("published", ""),
            "url": e.get("link", f"https://arxiv.org/abs/{arxiv_id}"),
        })
    return papers


class ArxivCollector(BaseCollector):
    """Collects recent AI papers from the arXiv official API."""

    source_type = "arxiv"

    def __init__(self, target_date: Optional[str] = None):
        # If target_date set (backfill mode), keep only papers submitted around that date.
        self.target_date = target_date

    def collect(self) -> List[RawItem]:
        sources = load_sources()
        arxiv_config = sources.get("arxiv", {})

        if not arxiv_config.get("enabled", False):
            print("  Paper collector disabled")
            return []

        categories = arxiv_config.get("categories", ["cs.AI", "cs.CL", "cs.LG", "cs.CV"])
        max_results = arxiv_config.get("max_results", 25)
        sort_by = arxiv_config.get("sort_by", "submittedDate")

        print(f"  Papers: fetching arXiv API ({len(categories)} cats, max {max_results})...")
        papers = _fetch_arxiv(categories, max_results, sort_by)

        # Backfill 模式：只保留提交日期落在 [target_date-1, target_date] 的论文
        if self.target_date and papers:
            try:
                target = datetime.strptime(self.target_date, "%Y-%m-%d").date()
                lo = target - timedelta(days=1)
                kept = []
                for p in papers:
                    try:
                        d = datetime.strptime(p["published"][:10], "%Y-%m-%d").date()
                        if lo <= d <= target:
                            kept.append(p)
                    except ValueError:
                        continue
                papers = kept
            except ValueError:
                pass

        items = []
        for paper in papers:
            authors = paper["authors"]
            if len(authors) > 3:
                author_str = ", ".join(authors[:3]) + " et al."
            else:
                author_str = ", ".join(authors)

            parts = [f"Authors: {author_str}"]
            if paper["primary_category"]:
                parts.append(f"Category: {paper['primary_category']}")
            summary = paper["summary"]
            if len(summary) > 400:
                summary = summary[:400] + "..."
            parts.append(f"Summary: {summary}")

            items.append(RawItem(
                title=paper["title"],
                content=". ".join(parts),
                source_type="arxiv",
                source_name="arXiv",
                url=paper["url"],
                published=paper["published"],
                metadata={
                    "authors": authors,
                    "arxiv_id": paper["arxiv_id"],
                    "categories": paper["categories"],
                    "primary_category": paper["primary_category"],
                },
            ))

        print(f"  Papers: {len(items)} papers from arXiv")
        return items
