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

        # 注意：不在此早退——当天文件为空时，下面会走 48h 兜底逻辑

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
        items, skipped_old = self._window_items(all_tweets.values(), cutoff)

        # 兜底：当天窗口 0 条（x-monitor 软封/未跑/文件缺失），放宽到最近 48h
        # 捞回最后一批可用数据。signal 层有跨天去重，重复不影响。
        if not items:
            fb_cutoff = cutoff - timedelta(hours=self.hours)  # 窗口放宽到 2×hours
            fb_tweets = {}
            for d in [anchor - timedelta(days=2), previous, anchor]:
                for t in self._load_file(DATA_DIR / f"{d.isoformat()}.json"):
                    tid = t.get("id", "")
                    if tid and tid not in fb_tweets:
                        fb_tweets[tid] = t
            items, _ = self._window_items(fb_tweets.values(), fb_cutoff)
            if items:
                print(f"  Twitter: 当天窗口为空，回退最近 {self.hours * 2}h "
                      f"捞回 {len(items)} 条")

        accounts = len(set(item.source_name for item in items))
        print(f"  Twitter: {len(items)} tweets from {accounts} accounts "
              f"(filtered {skipped_old} older than {self.hours}h)")
        return items

    def _window_items(self, tweets, cutoff):
        """把推文 dict 列表转成 RawItem，按 cutoff 做时间窗过滤。"""
        items = []
        skipped_old = 0
        for t in tweets:
            text = t.get("text", "")
            if not text:
                continue
            ts = t.get("timestamp", "")
            if ts:
                try:
                    pub_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if pub_dt < cutoff:
                        skipped_old += 1
                        continue
                except (ValueError, TypeError):
                    pass
            items.append(self._to_item(t))
        return items, skipped_old

    def _to_item(self, t) -> RawItem:
        username = t.get("username", "unknown")
        return RawItem(
            title=f"@{username}",
            content=t.get("text", ""),
            source_type="twitter",
            source_name=f"@{username}",
            url=t.get("url", ""),
            published=t.get("timestamp", ""),
            metadata={
                "tweet_id": t.get("id", ""),
                "images": t.get("images", []),
                "likes": t.get("likes", 0),
                "retweets": t.get("retweets", 0),
                "views": t.get("views", 0),
                "user_bio": t.get("user_bio", ""),
            },
        )
