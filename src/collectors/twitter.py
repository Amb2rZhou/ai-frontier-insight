"""Twitter/X collector — reads from x-monitor pipeline JSON.

x-monitor runs locally via launchd, scrapes an X List page with Playwright,
and writes structured JSON to data/x-monitor/{date}.json in this repo.
Quality/engagement/relevance filtering is done upstream in x-monitor.
This collector only applies a time window filter (24h).
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List

from .base import BaseCollector, RawItem

# x-monitor 推送数据到本仓库的位置
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "x-monitor"


class TwitterCollector(BaseCollector):
    """Collects tweets from x-monitor's local pipeline output."""

    source_type = "twitter"

    def __init__(self, hours: int = 24, target_date: str = None,
                 cutoff_override: datetime = None):
        """
        Args:
            hours: Only include tweets published within this many hours.
            target_date: If set (YYYY-MM-DD), backfill mode — read that date's
                file (and the day before) and use end-of-target-date as the
                time anchor instead of now().
            cutoff_override: Explicit cutoff datetime (UTC). Highest priority.
                If set, only tweets with timestamp >= cutoff_override are kept,
                and date file selection is based on its date.
        """
        self.hours = hours
        self.target_date = target_date
        self.cutoff_override = cutoff_override

    def _load_file(self, filepath: Path) -> list:
        """Load tweets from a single pipeline JSON file."""
        if not filepath.exists():
            return []
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return data.get("tweets", [])
        except (json.JSONDecodeError, OSError):
            return []

    def collect(self) -> List[RawItem]:
        """Read target + previous day's x-monitor JSON, filter to last N hours."""
        if self.cutoff_override:
            # 明确锚点：以 cutoff 那天和后一天作为读取范围（覆盖 24h 窗口）
            cutoff_end = self.cutoff_override + timedelta(hours=self.hours)
            anchor = cutoff_end.date()
        elif self.target_date:
            anchor = date.fromisoformat(self.target_date)
        else:
            anchor = date.today()
        previous = anchor - timedelta(days=1)

        # 读取目标日和前一天的文件，合并去重
        all_tweets = {}
        for d in [previous, anchor]:
            for t in self._load_file(DATA_DIR / f"{d.isoformat()}.json"):
                tid = t.get("id", "")
                if tid and tid not in all_tweets:
                    all_tweets[tid] = t

        if not all_tweets:
            print(f"  Twitter: no data files for {previous} ~ {anchor}")
            return []

        # 仅时间过滤（质量/互动/语义过滤已在 x-monitor 上游完成）
        if self.cutoff_override:
            cutoff = self.cutoff_override
        elif self.target_date:
            # 回填模式：以目标日 23:59 UTC 为锚点
            anchor_dt = datetime.combine(
                anchor, datetime.max.time(), tzinfo=timezone.utc
            )
            cutoff = anchor_dt - timedelta(hours=self.hours)
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.hours)
        items = []
        skipped_old = 0
        for t in all_tweets.values():
            username = t.get("username", "unknown")
            text = t.get("text", "")
            if not text:
                continue

            # 时间过滤：丢弃超过 N 小时的推文
            ts = t.get("timestamp", "")
            if ts:
                try:
                    pub_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if pub_dt < cutoff:
                        skipped_old += 1
                        continue
                except (ValueError, TypeError):
                    pass

            items.append(RawItem(
                title=f"@{username}",
                content=text,
                source_type="twitter",
                source_name=f"@{username}",
                url=t.get("url", ""),
                published=ts,
                metadata={
                    "tweet_id": t.get("id", ""),
                    "images": t.get("images", []),
                    "likes": t.get("likes", 0),
                    "retweets": t.get("retweets", 0),
                    "views": t.get("views", 0),
                    "user_bio": t.get("user_bio", ""),
                },
            ))

        accounts = len(set(item.source_name for item in items))
        print(f"  Twitter: {len(items)} tweets from {accounts} accounts "
              f"(filtered {skipped_old} older than {self.hours}h)")
        return items
