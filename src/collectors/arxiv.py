"""Arxiv paper collector.

Uses the Arxiv API to fetch recent papers by category.
Returns richer metadata than RSS (authors, categories, full abstract).

API docs: https://info.arxiv.org/help/api/user-manual.html
"""

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List

import requests

from .base import BaseCollector, RawItem
from ..utils.config import load_sources

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _fetch_arxiv(categories: List[str], max_results: int = 50,
                  sort_by: str = "submittedDate") -> List[dict]:
    """Fetch papers from Arxiv API.

    Args:
        categories: List of Arxiv categories (e.g. ["cs.AI", "cs.CL"])
        max_results: Maximum papers to return
        sort_by: "submittedDate" or "lastUpdatedDate" or "relevance"
    """
    # Build category query: cat:cs.AI OR cat:cs.CL OR ...
    cat_query = "+OR+".join(f"cat:{cat}" for cat in categories)

    # Add date filter for last 3 days (Arxiv has submission delays)
    three_days_ago = (datetime.utcnow() - timedelta(days=3)).strftime("%Y%m%d")
    today = datetime.utcnow().strftime("%Y%m%d")
    date_filter = f"+AND+submittedDate:[{three_days_ago}0000+TO+{today}2359]"

    params = {
        "search_query": cat_query + date_filter,
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": "descending",
    }

    resp = requests.get(ARXIV_API, params=params, timeout=30)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    papers = []

    for entry in root.findall("atom:entry", ARXIV_NS):
        paper_id_el = entry.find("atom:id", ARXIV_NS)
        title_el = entry.find("atom:title", ARXIV_NS)
        summary_el = entry.find("atom:summary", ARXIV_NS)
        published_el = entry.find("atom:published", ARXIV_NS)

        if paper_id_el is None or title_el is None:
            continue

        paper_id = paper_id_el.text.strip()
        title = title_el.text.strip().replace("\n", " ")
        summary = summary_el.text.strip() if summary_el is not None else ""
        published = published_el.text.strip() if published_el is not None else ""

        authors = [
            a.find("atom:name", ARXIV_NS).text
            for a in entry.findall("atom:author", ARXIV_NS)
            if a.find("atom:name", ARXIV_NS) is not None
        ]

        categories = [
            c.get("term") for c in entry.findall("atom:category", ARXIV_NS)
        ]

        # Get PDF link
        pdf_url = None
        for link in entry.findall("atom:link", ARXIV_NS):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break

        # Get abstract page link
        abs_url = paper_id  # The id IS the abstract URL

        papers.append({
            "id": paper_id,
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "published": published,
            "pdf_url": pdf_url,
            "abs_url": abs_url,
        })

    return papers


class ArxivCollector(BaseCollector):
    """Collects recent AI papers from Arxiv."""

    source_type = "arxiv"

    def collect(self) -> List[RawItem]:
        sources = load_sources()
        arxiv_config = sources.get("arxiv", {})

        if not arxiv_config.get("enabled", False):
            print("  Arxiv collector disabled")
            return []

        categories = arxiv_config.get("categories", ["cs.AI", "cs.CL", "cs.LG"])
        max_results = arxiv_config.get("max_results", 50)
        sort_by = arxiv_config.get("sort_by", "submittedDate")

        print(f"  Arxiv: fetching from {categories}, max {max_results}...")

        papers = []
        try:
            papers = _fetch_arxiv(categories, max_results, sort_by)
        except Exception as e:
            print(f"  Arxiv API error: {e}")

        # Fallback to RSS if API returns nothing
        if not papers:
            print("  Arxiv API returned 0 results, falling back to RSS...")
            papers = self._fetch_via_rss(categories)

        items = []
        for paper in papers:
            # Build author string (first 3 + "et al.")
            authors = paper.get("authors", [])
            if len(authors) > 3:
                author_str = ", ".join(authors[:3]) + " et al."
            else:
                author_str = ", ".join(authors)

            # Truncate abstract for token efficiency
            summary = paper.get("summary", "")
            if len(summary) > 400:
                summary = summary[:400] + "..."

            items.append(RawItem(
                title=paper["title"],
                content=f"Authors: {author_str}. Abstract: {summary}",
                source_type="arxiv",
                source_name="Arxiv",
                url=paper.get("abs_url", ""),
                published=paper.get("published", ""),
                metadata={
                    "authors": authors,
                    "categories": paper.get("categories", []),
                    "pdf_url": paper.get("pdf_url"),
                    "arxiv_id": paper.get("id", ""),
                },
            ))

        print(f"  Arxiv: {len(items)} papers fetched")
        return items

    @staticmethod
    def _fetch_via_rss(categories: List[str]) -> List[dict]:
        """Fallback: fetch papers via Arxiv RSS feed."""
        import feedparser

        combined = "+".join(categories)
        feed_url = f"https://rss.arxiv.org/rss/{combined}"

        try:
            resp = requests.get(feed_url, timeout=30, headers={
                "User-Agent": "AI-Frontier-Insight-Bot/1.0"
            })
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as e:
            print(f"  Arxiv RSS fallback also failed: {e}")
            return []

        papers = []
        for entry in feed.entries:
            papers.append({
                "id": entry.get("link", ""),
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", entry.get("description", "")).strip(),
                "authors": [],  # RSS doesn't reliably provide authors
                "categories": categories,
                "published": "",
                "pdf_url": None,
                "abs_url": entry.get("link", ""),
            })

        print(f"  Arxiv RSS fallback: {len(papers)} papers")
        return papers
