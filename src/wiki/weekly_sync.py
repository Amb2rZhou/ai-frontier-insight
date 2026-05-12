"""sync_wiki_from_weekly: data/weekly/2026-W*.md → wiki/weekly-summaries/W*.md

Usage:
  python -m src.wiki.weekly_sync 2026-W20
  python -m src.wiki.weekly_sync data/weekly/2026-W20.md
  python -m src.wiki.weekly_sync --all          # 全量回扫所有未生成的
  python -m src.wiki.weekly_sync --force 2026-W20  # 强制覆盖已有

每次同步会：
  1. 调 AI 把 data/weekly markdown 浓缩成 wiki page
  2. 跑 linker 兜底加 wiki-link
  3. 写到 wiki/weekly-summaries/W{n}.md
  4. 反向更新前一周的 linked_from（加 next 链）
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from ..analysis.ai_client import call_ai
from ..utils.config import load_prompt
from .linker import add_links_to_markdown, get_entity_map

REPO_ROOT = Path(__file__).resolve().parents[2]
WEEKLY_DATA_DIR = REPO_ROOT / "data" / "weekly"
WEEKLY_WIKI_DIR = REPO_ROOT / "wiki" / "weekly-summaries"

WEEK_ID_RE = re.compile(r"(\d{4})-W(\d{2})")


def _parse_week_id(arg: str) -> tuple[str, int, int]:
    """Accepts '2026-W20' or 'data/weekly/2026-W20.md', returns (week_id, year, num)."""
    m = WEEK_ID_RE.search(arg)
    if not m:
        raise ValueError(f"Cannot parse week id from: {arg}")
    return m.group(0), int(m.group(1)), int(m.group(2))


def _short_week(num: int) -> str:
    return f"W{num}"


def _read_weekly_data(week_id: str) -> str:
    p = WEEKLY_DATA_DIR / f"{week_id}.md"
    if not p.exists():
        raise FileNotFoundError(f"Missing source weekly: {p}")
    return p.read_text(encoding="utf-8")


def _extract_date_range(weekly_md: str) -> str:
    m = re.search(r"\*\*日期：\*\*\s*([^\n]+)", weekly_md)
    return m.group(1).strip() if m else ""


def generate_wiki_page(week_id: str, *, force: bool = False) -> Path:
    """主入口：根据 week_id (e.g. '2026-W20') 生成 wiki/weekly-summaries/W{n}.md.
    Returns: path to the written wiki page.
    """
    _, year, num = _parse_week_id(week_id)
    target = WEEKLY_WIKI_DIR / f"{_short_week(num)}.md"
    if target.exists() and not force:
        print(f"[weekly_sync] {target.name} exists; use --force to overwrite", file=sys.stderr)
        return target

    raw = _read_weekly_data(week_id)
    date_range = _extract_date_range(raw)
    today = date.today().isoformat()

    prev = _short_week(num - 1) if num > 1 else ""
    prev_prev = _short_week(num - 2) if num > 2 else ""
    next_w = _short_week(num + 1)

    prompt = load_prompt(
        "weekly_to_wiki",
        weekly_markdown=raw[:18000],
        week_num=num,
        week_id=week_id,
        date_range=date_range,
        today=today,
        prev=num - 1 if num > 1 else 1,
        prev_prev=num - 2 if num > 2 else 1,
        next_or_skip=prev if prev else "",
    )

    print(f"[weekly_sync] calling AI for {week_id}...", file=sys.stderr)
    out = call_ai(prompt, label=f"weekly_sync_{week_id}", use_sonnet=False, max_tokens=4096)
    if not out or not out.strip():
        raise RuntimeError(f"AI returned empty result for {week_id}")

    # Strip code-block fence if model wrapped the whole output
    out = out.strip()
    if out.startswith("```"):
        out = re.sub(r"^```[a-z]*\n", "", out)
        out = re.sub(r"\n```\s*$", "", out)

    # Final linker pass — catch any plain-text entities the AI missed
    em = get_entity_map()
    out = add_links_to_markdown(out, current_page=f"weekly-summaries/{_short_week(num)}",
                                entity_map=em)

    WEEKLY_WIKI_DIR.mkdir(parents=True, exist_ok=True)
    target.write_text(out + "\n", encoding="utf-8")
    print(f"[weekly_sync] wrote {target}", file=sys.stderr)

    _update_linked_from(num)
    return target


def _update_linked_from(num: int) -> None:
    """给前一周的 wiki page 补上 next 链（如果还没有）。"""
    prev_path = WEEKLY_WIKI_DIR / f"{_short_week(num - 1)}.md"
    if not prev_path.exists():
        return
    text = prev_path.read_text(encoding="utf-8")
    next_link = f"[[W{num}]]"
    if next_link in text:
        return
    # Insert into frontmatter linked_from list, if exists
    if re.search(r"^linked_from:", text, re.MULTILINE):
        text = re.sub(
            r"(linked_from:\s*\n(?:\s*-\s*\[\[[^\]]+\]\]\n)+)",
            lambda m: m.group(1) + f"  - {next_link}\n",
            text,
            count=1,
        )
        # Inline list form fallback
        text = re.sub(
            r"^(linked_from:\s*)(\[\[[^\n]+\]\])\s*$",
            lambda m: f"{m.group(1)}{m.group(2)}, {next_link}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
    prev_path.write_text(text, encoding="utf-8")
    print(f"[weekly_sync] back-linked {prev_path.name} → {next_link}", file=sys.stderr)


def list_missing() -> list[str]:
    """返回 data/weekly 里存在但 wiki/weekly-summaries 还没生成的 week_ids."""
    have = {p.stem for p in WEEKLY_WIKI_DIR.glob("W*.md")}
    missing = []
    for p in WEEKLY_DATA_DIR.glob("*-W*.md"):
        m = WEEK_ID_RE.search(p.stem)
        if not m:
            continue
        short = f"W{int(m.group(2))}"
        if short not in have:
            missing.append(p.stem)
    return sorted(missing)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    force = "--force" in argv
    args = [a for a in argv if not a.startswith("--")]
    if "--all" in argv:
        targets = list_missing()
        if not targets:
            print("[weekly_sync] nothing missing", file=sys.stderr)
            return 0
        print(f"[weekly_sync] missing: {targets}", file=sys.stderr)
        for wid in targets:
            try:
                generate_wiki_page(wid, force=force)
            except Exception as e:
                print(f"[weekly_sync] FAILED {wid}: {e}", file=sys.stderr)
        return 0
    if not args:
        print("usage: weekly_sync <week_id> | --all [--force]", file=sys.stderr)
        return 2
    for arg in args:
        week_id, _, _ = _parse_week_id(arg)
        generate_wiki_page(week_id, force=force)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
