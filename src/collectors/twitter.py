"""Twitter/X collector — reads from x-monitor pipeline JSON.

x-monitor runs locally via launchd, scrapes an X List page with Playwright,
and writes structured JSON to data/x-monitor/{date}.json in this repo.
This collector reads that file and converts tweets to RawItem format.
"""

import json
from datetime import date
from pathlib import Path
from typing import List

from .base import BaseCollector, RawItem

# x-monitor 推送数据到本仓库的位置
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "x-monitor"


class TwitterCollector(BaseCollector):
    """Collects tweets from x-monitor's local pipeline output."""

    source_type = "twitter"

    def __init__(self, target_date: str = None):
        """
        Args:
            target_date: ISO date string (e.g. "2026-02-25").
                         Defaults to today.
        """
        self.target_date = target_date or date.today().isoformat()

    def collect(self) -> List[RawItem]:
        """Read x-monitor pipeline JSON and convert to RawItem list."""
        json_file = DATA_DIR / f"{self.target_date}.json"

        if not json_file.exists():
            print(f"  Twitter: no data file for {self.target_date} ({json_file})")
            return []

        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  Twitter: failed to read {json_file}: {e}")
            return []

        tweets = data.get("tweets", [])
        if not tweets:
            print(f"  Twitter: file exists but contains 0 tweets")
            return []

        items = []
        for t in tweets:
            username = t.get("username", "unknown")
            text = t.get("text", "")
            if not text:
                continue

            items.append(RawItem(
                title=f"@{username}",
                content=text,
                source_type="twitter",
                source_name=f"@{username}",
                url=t.get("url", ""),
                published=t.get("timestamp", ""),
                metadata={
                    "tweet_id": t.get("id", ""),
                    "images": t.get("images", []),
                },
            ))

        print(f"  Twitter: {len(items)} tweets from {len(set(t.get('username') for t in tweets))} accounts")
        return items
