"""AI Frontier Insight Bot — Main entry point.

Commands:
    python src/main.py daily          # Full daily pipeline: collect → analyze → save draft
    python src/main.py send-daily     # Send today's daily brief via webhook
    python src/main.py weekly         # Generate weekly deep insight
    python src/main.py send-weekly    # Send weekly insight via webhook
    python src/main.py cleanup        # Clean up old data
"""

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .analysis.insight_generator import (
    generate_insights,
    generate_trend_summary,
    update_trends,
)
from .analysis.signal_extractor import extract_signals
from .collectors.rss import RSSCollector
from .delivery.webhook import send_webhook
from .formatters.daily_markdown import format_daily_brief
from .memory.manager import save_daily_signals
from .utils.config import get_timezone, load_settings
from .utils.draft import load_draft, save_draft, update_draft_status


def _get_today() -> str:
    """Get today's date string in configured timezone."""
    tz = ZoneInfo(get_timezone())
    return datetime.now(tz).strftime("%Y-%m-%d")


def _collect_all() -> list:
    """Run all enabled collectors and return combined RawItem list."""
    all_items = []

    # RSS
    print("\n[1/5] Collecting RSS feeds...")
    rss = RSSCollector(
        cutoff=datetime.now() - timedelta(hours=24),
        max_per_source=5,
    )
    all_items.extend(rss.collect())

    # Twitter (import dynamically — user is writing this separately)
    print("\n[2/5] Collecting Twitter...")
    try:
        from .collectors.twitter import TwitterCollector
        twitter = TwitterCollector()
        all_items.extend(twitter.collect())
    except ImportError:
        print("  Twitter collector not available yet, skipping")
    except Exception as e:
        print(f"  Twitter collector error: {e}")

    # GitHub Trending + Releases
    print("\n[3/5] Collecting GitHub...")
    try:
        from .collectors.github_trending import GitHubTrendingCollector
        gh = GitHubTrendingCollector()
        all_items.extend(gh.collect())
    except Exception as e:
        print(f"  GitHub collector error: {e}")

    # Arxiv
    print("\n[4/5] Collecting Arxiv...")
    try:
        from .collectors.arxiv import ArxivCollector
        arxiv = ArxivCollector()
        all_items.extend(arxiv.collect())
    except Exception as e:
        print(f"  Arxiv collector error: {e}")

    # HuggingFace
    print("\n[5/5] Collecting HuggingFace...")
    try:
        from .collectors.huggingface import HuggingFaceCollector
        hf = HuggingFaceCollector()
        all_items.extend(hf.collect())
    except Exception as e:
        print(f"  HuggingFace collector error: {e}")

    print(f"\n=== Total collected: {len(all_items)} items ===")
    return all_items


def cmd_daily():
    """Full daily pipeline: collect → extract signals → generate insights → save."""
    today = _get_today()
    print(f"=== Daily Brief Pipeline: {today} ===")

    # Check if already generated
    existing = load_draft(today, "daily")
    if existing and existing.get("status") in ("sent", "approved"):
        print(f"Draft already {existing['status']} for {today}, skipping")
        return

    # Step 1: Collect
    raw_items = _collect_all()
    if not raw_items:
        print("No items collected, aborting")
        return

    # Step 2: Extract signals
    print("\n[Analysis] Extracting signals...")
    signals = extract_signals(raw_items)
    if not signals:
        print("No signals extracted, aborting")
        return

    # Step 3: Generate insights
    print("\n[Analysis] Generating insights...")
    insights = generate_insights(signals)
    if not insights:
        print("Insight generation failed, using raw signals")
        insights = signals  # Fallback: use signals without insight/implication

    # Step 4: Generate trend summary
    print("\n[Analysis] Generating trend summary...")
    trend_summary = generate_trend_summary(signals)

    # Step 5: Update trends
    print("\n[Memory] Updating trends...")
    update_trends(signals)

    # Step 6: Save signals to weekly accumulator
    save_daily_signals(today, [s for s in signals])

    # Step 7: Save draft
    draft_data = {
        "date": today,
        "insights": [i if isinstance(i, dict) else i.to_dict() for i in insights],
        "trend_summary": trend_summary,
        "raw_item_count": len(raw_items),
        "signal_count": len(signals),
    }
    draft_path = save_draft(draft_data, "daily")

    print(f"\n=== Daily pipeline complete: {len(insights)} insights saved ===")
    print(f"Draft: {draft_path}")


def cmd_send_daily():
    """Send today's daily brief via webhook."""
    today = _get_today()
    print(f"=== Sending Daily Brief: {today} ===")

    draft = load_draft(today, "daily")
    if not draft:
        print(f"No draft found for {today}")
        return

    if draft.get("status") == "sent":
        print(f"Already sent for {today}")
        return

    # Format markdown
    content = format_daily_brief(
        date=today,
        insights=draft.get("insights", []),
        trend_summary=draft.get("trend_summary", ""),
    )

    print(f"Formatted message: {len(content)} chars")

    # Send
    success = send_webhook(content)
    if success:
        update_draft_status(today, "sent", "daily")
        print("Daily brief sent successfully!")
    else:
        print("Failed to send daily brief")


def cmd_weekly():
    """Generate weekly deep insight report (placeholder for Phase 3)."""
    print("=== Weekly Insight Pipeline ===")
    print("Not yet implemented (Phase 3)")
    # TODO: weekly_synthesizer.py + weekly_markdown.py


def cmd_send_weekly():
    """Send weekly insight via webhook (placeholder for Phase 3)."""
    print("=== Sending Weekly Insight ===")
    print("Not yet implemented (Phase 3)")


def cmd_cleanup():
    """Clean up old drafts and archived data."""
    print("=== Cleanup ===")
    from .utils.draft import cleanup_old_drafts
    cleanup_old_drafts(days=30)
    print("Cleanup complete")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    commands = {
        "daily": cmd_daily,
        "send-daily": cmd_send_daily,
        "weekly": cmd_weekly,
        "send-weekly": cmd_send_weekly,
        "cleanup": cmd_cleanup,
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[command]()


if __name__ == "__main__":
    main()
