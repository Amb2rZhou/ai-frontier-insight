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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from .analysis.insight_generator import (
    generate_insights,
    generate_trend_summary,
    update_trends,
)
from .analysis.signal_extractor import extract_signals
from .collectors.rss import RSSCollector
from .delivery.webhook import send_webhook
from .formatters.daily_markdown import format_daily_brief, export_daily_markdown
from .memory.manager import save_daily_signals
from .utils.config import get_timezone, load_settings
from .utils.draft import load_draft, save_draft, update_draft_status


def _parse_backfill_date() -> Optional[str]:
    """Parse --date YYYY-MM-DD from sys.argv (backfill mode). Returns None if absent."""
    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


def _parse_anchor() -> Optional[datetime]:
    """Parse --anchor 'YYYY-MM-DD HH:MM' from sys.argv. Interpreted in config TZ.
    Used to lock the 24h window to a specific point in time."""
    if "--anchor" not in sys.argv:
        return None
    idx = sys.argv.index("--anchor")
    if idx + 1 >= len(sys.argv):
        return None
    raw = sys.argv[idx + 1]
    tz = ZoneInfo(get_timezone())
    return datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=tz)


def _get_today() -> str:
    """Get today's date string in configured timezone (or backfill date if --date given)."""
    backfill = _parse_backfill_date()
    if backfill:
        return backfill
    tz = ZoneInfo(get_timezone())
    return datetime.now(tz).strftime("%Y-%m-%d")


def _collect_all(target_date: Optional[str] = None) -> list:
    """Run all enabled collectors and return combined RawItem list.

    If target_date is set (backfill mode), only run date-aware collectors:
    Arxiv (HF Daily Papers ?date=) and GitHub Releases (filtered by published_at).
    Skips RSS / Twitter / GitHub Trending / HF Trending / Benchmarks because they
    only return current state and would pollute past-date archives.
    """
    backfill = target_date is not None
    all_items = []

    if backfill:
        print(f"\n[Backfill mode for {target_date}] "
              f"Skipping RSS / GH Trending / HF Trending / Benchmarks "
              f"(real-time-only sources); Twitter included from archived x-monitor data")

        # Twitter (回填模式：读 target_date 对应的 x-monitor 归档)
        print("\n[Backfill] Collecting Twitter from archived data...")
        try:
            from .collectors.twitter import TwitterCollector
            twitter = TwitterCollector(target_date=target_date)
            all_items.extend(twitter.collect())
        except ImportError:
            print("  Twitter collector not available, skipping")
        except Exception as e:
            print(f"  Twitter collector error: {e}")
    else:
        # 计算 24h 时间窗口（默认 now，可被 --anchor 覆盖）
        anchor_dt = _parse_anchor()
        if anchor_dt:
            print(f"\n[Anchored mode] 24h window ends at {anchor_dt.isoformat()}")
            # 转 UTC 给 Twitter（其 timestamp 是 UTC）
            cutoff_utc = (anchor_dt - timedelta(hours=24)).astimezone(timezone.utc)
            # RSS feed item 用 naive datetime（本地时区），传 naive
            cutoff_naive = anchor_dt.replace(tzinfo=None) - timedelta(hours=24)
        else:
            cutoff_utc = None
            cutoff_naive = datetime.now() - timedelta(hours=24)

        # RSS
        print("\n[1/5] Collecting RSS feeds...")
        rss = RSSCollector(
            cutoff=cutoff_naive,
            max_per_source=5,
        )
        all_items.extend(rss.collect())

        # Twitter (import dynamically — user is writing this separately)
        print("\n[2/5] Collecting Twitter...")
        try:
            from .collectors.twitter import TwitterCollector
            twitter = TwitterCollector(cutoff_override=cutoff_utc)
            all_items.extend(twitter.collect())
        except ImportError:
            print("  Twitter collector not available yet, skipping")
        except Exception as e:
            print(f"  Twitter collector error: {e}")

    # GitHub (Releases is date-aware via published_at; Trending is skipped in backfill)
    print("\n[3/5] Collecting GitHub...")
    try:
        from .collectors.github_trending import GitHubTrendingCollector
        gh = GitHubTrendingCollector(target_date=target_date)
        all_items.extend(gh.collect())
    except Exception as e:
        print(f"  GitHub collector error: {e}")

    # Arxiv (HF Daily Papers supports ?date=YYYY-MM-DD)
    print("\n[4/5] Collecting Arxiv...")
    try:
        from .collectors.arxiv import ArxivCollector
        arxiv = ArxivCollector(target_date=target_date)
        all_items.extend(arxiv.collect())
    except Exception as e:
        print(f"  Arxiv collector error: {e}")

    if not backfill:
        # HuggingFace
        print("\n[5/5] Collecting HuggingFace...")
        try:
            from .collectors.huggingface import HuggingFaceCollector
            hf = HuggingFaceCollector()
            all_items.extend(hf.collect())
        except Exception as e:
            print(f"  HuggingFace collector error: {e}")

        # Benchmarks (5 leaderboards)
        try:
            from .collectors.benchmarks import BenchmarkCollector
            bench = BenchmarkCollector()
            all_items.extend(bench.collect())
        except Exception as e:
            print(f"  Benchmark collector error: {e}")

    print(f"\n=== Total collected: {len(all_items)} items ===")
    return all_items


def cmd_daily():
    """Full daily pipeline: collect → extract signals → generate insights → save."""
    today = _get_today()
    backfill_date = _parse_backfill_date()
    if backfill_date:
        print(f"=== Daily Brief Pipeline (BACKFILL): {today} ===")
    else:
        print(f"=== Daily Brief Pipeline: {today} ===")

    # Check if already generated
    existing = load_draft(today, "daily")
    if existing and existing.get("status") in ("sent", "approved"):
        print(f"Draft already {existing['status']} for {today}, skipping")
        return

    # Step 1: Collect
    raw_items = _collect_all(target_date=backfill_date)
    if not raw_items:
        print("No items collected, aborting")
        sys.exit(1)

    # Step 1.5: Cache full raw items for parallel pipelines (dept brief 复用采集)
    from .utils.archive import save_raw_cache
    cache_path = save_raw_cache(today, raw_items)
    print(f"  - Raw cache saved: {cache_path}")

    # Step 2: Extract signals
    print("\n[Analysis] Extracting signals...")
    signals = extract_signals(raw_items)
    if not signals:
        print("No signals extracted, aborting")
        sys.exit(1)

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

    # Step 8: Archive structured data for weekly reports
    print("\n[Archive] Saving daily archive...")
    from .utils.archive import archive_daily, cleanup_old_data
    archive_daily(today, raw_items, insights, trend_summary)

    # Step 9: Export markdown for Redoc / OpenClaw
    daily_dir = str(Path(__file__).resolve().parents[1] / "data" / "daily" / today)
    md_content = export_daily_markdown(today, insights, trend_summary, output_dir=daily_dir)
    print(f"  - Markdown exported: {daily_dir}/{today}_daily.md")

    # Step 10: Update wiki knowledge base
    print("\n[Wiki] Updating knowledge base...")
    try:
        from .wiki.updater import update_wiki
        wiki_stats = update_wiki(today, insights)
        print(f"  - {wiki_stats['pages_updated']} pages updated, "
              f"{wiki_stats['entries_added']} entries added, "
              f"{wiki_stats['pages_created']} new pages")
    except Exception as e:
        print(f"  - Wiki update failed (non-fatal): {e}")

    # Step 11: Publish to Jekyll site
    print("\n[Publish] Creating Jekyll post...")
    site_posts = Path(__file__).resolve().parents[1] / "docs" / "_posts"
    site_posts.mkdir(parents=True, exist_ok=True)
    md_source = Path(daily_dir) / f"{today}_daily.md"
    if md_source.exists():
        content = md_source.read_text(encoding="utf-8")
        first_line = content.split("\n")[0].strip("# ").strip()
        post_content = f'---\nlayout: post\ntitle: "{first_line} ({today})"\ndate: {today}\n---\n\n{content}\n'
        post_path = site_posts / f"{today}-daily.md"
        post_path.write_text(post_content, encoding="utf-8")
        print(f"  - Jekyll post: {post_path}")

    # Step 12: Clean up expired data
    cleanup_old_data()

    print(f"\n=== Daily pipeline complete: {len(insights)} insights saved ===")
    print(f"Draft: {draft_path}")


def cmd_collect():
    """采集-only：跑所有采集器，存 raw_cache，不做任何分析。

    供 headless Claude 分析链路用（采集走 Python，筛选/洞察走 Claude）。
    复用 cmd_daily 的步骤 1 / 1.5，支持 --date 回填、--anchor 锚点。
    """
    today = _get_today()
    backfill_date = _parse_backfill_date()
    print(f"=== Collect-only: {today} ===")

    raw_items = _collect_all(target_date=backfill_date)
    if not raw_items:
        print("No items collected, aborting")
        sys.exit(1)

    from .utils.archive import save_raw_cache
    cache_path = save_raw_cache(today, raw_items)
    print(f"\n=== Collect complete: {len(raw_items)} items → {cache_path} ===")


def cmd_publish_daily():
    """个人版机械发布：吃 headless Claude 产出的分析 JSON，做无 LLM 的发布步骤。

    用法：python -m src.main publish-daily --from-json <path>
    JSON 结构：{"date": "YYYY-MM-DD"(可选), "insights": [...], "trend_summary": "..."}
      - insights：最终 10 条，每条 dict 含 title/signal_text/insight/implication/sources/tags/signal_strength
    做的事（全部本地、不调 LLM）：存草稿 → 周累积 → 归档 → 导出 md → Jekyll post。
    不做：趋势记忆更新（由 Claude 直接读写 trends.json）、git push、推钉钉（由外层 shell/Claude 负责）。
    """
    if "--from-json" not in sys.argv:
        print("::error:: 缺少 --from-json <path>")
        sys.exit(1)
    idx = sys.argv.index("--from-json")
    if idx + 1 >= len(sys.argv):
        print("::error:: --from-json 后缺少路径")
        sys.exit(1)
    json_path = Path(sys.argv[idx + 1])
    if not json_path.exists():
        print(f"::error:: 分析 JSON 不存在: {json_path}")
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    today = data.get("date") or _get_today()
    insights = data.get("insights", [])
    trend_summary = data.get("trend_summary", "")
    if not insights:
        print("::error:: JSON 里没有 insights")
        sys.exit(1)

    print(f"=== Publish-daily（个人版机械发布）: {today}，{len(insights)} 条 ===")

    # 1. 存草稿（send 链路兼容）
    draft_data = {
        "date": today,
        "insights": insights,
        "trend_summary": trend_summary,
        "signal_count": len(insights),
    }
    draft_path = save_draft(draft_data, "daily")
    print(f"  - 草稿: {draft_path}")

    # 2. 周累积（供周报/去重）
    save_daily_signals(today, insights)

    # 3. 归档（需 raw_items）
    from .utils.archive import archive_daily, load_raw_cache
    raw_items = load_raw_cache(today) or []
    archive_daily(today, raw_items, insights, trend_summary)
    print(f"  - 归档完成（raw {len(raw_items)} 条）")

    # 4. 导出 markdown
    daily_dir = str(Path(__file__).resolve().parents[1] / "data" / "daily" / today)
    export_daily_markdown(today, insights, trend_summary, output_dir=daily_dir)
    print(f"  - Markdown: {daily_dir}/{today}_daily.md")

    # 5. Jekyll post
    site_posts = Path(__file__).resolve().parents[1] / "docs" / "_posts"
    site_posts.mkdir(parents=True, exist_ok=True)
    md_source = Path(daily_dir) / f"{today}_daily.md"
    if md_source.exists():
        content = md_source.read_text(encoding="utf-8")
        first_line = content.split("\n")[0].strip("# ").strip()
        post_content = (
            f'---\nlayout: post\ntitle: "{first_line} ({today})"\n'
            f'date: {today}\n---\n\n{content}\n'
        )
        post_path = site_posts / f"{today}-daily.md"
        post_path.write_text(post_content, encoding="utf-8")
        print(f"  - Jekyll post: {post_path}")

    print(f"\n=== Publish-daily 完成 ===")


def cmd_send_daily():
    """Send today's daily brief via webhook (two messages).

    Options:
        --alert-only    Only send to alert/test channels
    """
    alert_only = "--alert-only" in sys.argv
    today = _get_today()

    if alert_only:
        print(f"=== Sending Daily Brief (TEST ONLY): {today} ===")
    else:
        print(f"=== Sending Daily Brief: {today} ===")

    draft = load_draft(today, "daily")
    if not draft:
        print(f"No draft found for {today}")
        sys.exit(1)

    if draft.get("status") == "sent" and not alert_only:
        print(f"Already sent for {today}")
        return

    # Format as multiple messages
    messages = format_daily_brief(
        date=today,
        insights=draft.get("insights", []),
        trend_summary=draft.get("trend_summary", ""),
    )

    # Send all messages with brief pauses; only @all on the last message
    import time
    for i, msg in enumerate(messages, 1):
        is_last = (i == len(messages))
        print(f"Message {i}/{len(messages)}: {len(msg)} chars, {len(msg.encode('utf-8'))} bytes")
        success = send_webhook(msg, mention_all=(is_last and not alert_only), alert_only=alert_only)
        if not success:
            print(f"Failed to send message {i}")
            sys.exit(1)
        if not is_last:
            time.sleep(1)

    if not alert_only:
        update_draft_status(today, "sent", "daily")
    print("Daily brief sent successfully!")


def cmd_weekly():
    """Generate weekly deep insight report (placeholder for Phase 3)."""
    print("=== Weekly Insight Pipeline ===")
    print("Not yet implemented (Phase 3)")
    # TODO: weekly_synthesizer.py + weekly_markdown.py


def cmd_send_weekly():
    """Send weekly insight via webhook (placeholder for Phase 3)."""
    print("=== Sending Weekly Insight ===")
    print("Not yet implemented (Phase 3)")


def cmd_dept_daily():
    """部门版日报（与个人版并行、状态完全隔离）。

    必须经 scripts/dept_brief.sh 触发（设置 PIPELINE_PROFILE=dept），从而：
    - prompt 走 prompts/dept/（团队视角），缺失的模板回落共用版
    - 趋势/去重记忆走 memory_dept/，与个人版互不污染
    采集复用：优先读个人版 11:00 跑完缓存的 data/raw_cache/{date}.json，
    缺失时（个人版失败/未跑）兜底自行采集。
    产物只写 data/dept_daily/{date}/，不推钉钉、不进 wiki、不发个人网站。
    """
    from .utils.config import PIPELINE_PROFILE
    if PIPELINE_PROFILE != "dept":
        print("dept-daily 必须在 PIPELINE_PROFILE=dept 下运行（请用 scripts/dept_brief.sh），"
              "否则会污染个人版的趋势/去重记忆。终止。")
        sys.exit(1)

    today = _get_today()
    print(f"=== Dept Brief Pipeline: {today} ===")

    # Step 1: Reuse cached raw items; fallback to fresh collection
    from .utils.archive import load_raw_cache
    raw_items = load_raw_cache(today)
    if raw_items:
        print(f"[Collect] Reusing raw cache: {len(raw_items)} items")
    else:
        print("[Collect] No raw cache found, collecting fresh...")
        raw_items = _collect_all()
    if not raw_items:
        print("No items available, aborting")
        sys.exit(1)

    # Step 2: Extract signals (dept prompt + dept memory)
    print("\n[Analysis] Extracting signals (dept perspective)...")
    signals = extract_signals(raw_items)
    if not signals:
        print("No signals extracted, aborting")
        sys.exit(1)

    # Step 3: Generate insights
    print("\n[Analysis] Generating insights (dept perspective)...")
    insights = generate_insights(signals)
    if not insights:
        print("Insight generation failed, using raw signals")
        insights = signals

    # Step 4: Trend summary + trend memory (dept-isolated)
    print("\n[Analysis] Generating trend summary...")
    trend_summary = generate_trend_summary(signals)
    print("\n[Memory] Updating dept trends...")
    update_trends(signals)
    save_daily_signals(today, [s for s in signals])

    # Step 5: Export markdown to data/dept_daily/{date}/ (gitignored)
    dept_dir = str(Path(__file__).resolve().parents[1] / "data" / "dept_daily" / today)
    export_daily_markdown(today, insights, trend_summary, output_dir=dept_dir)
    print(f"\n=== Dept brief complete: {len(insights)} insights ===")
    print(f"Output: {dept_dir}/{today}_daily.md")


def cmd_cleanup():
    """Clean up old drafts and archived data."""
    print("=== Cleanup ===")
    from .utils.draft import cleanup_old_drafts
    from .utils.archive import cleanup_old_data
    cleanup_old_drafts(days=30)
    cleanup_old_data()
    print("Cleanup complete")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    commands = {
        "daily": cmd_daily,
        "collect": cmd_collect,
        "publish-daily": cmd_publish_daily,
        "dept-daily": cmd_dept_daily,
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
