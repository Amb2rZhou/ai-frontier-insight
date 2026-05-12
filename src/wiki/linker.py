"""Wiki-link auto-injector.

把 plain markdown 里的实体名（公司/产品/技术/趋势）自动包裹成 [[slug|原文]]。

复用 updater.py 里的 ENTITY_MAP，并动态扫 wiki/ 目录补全。

跳过区：
  - YAML frontmatter
  - Fenced code block (```)
  - 行内 code (`...`)
  - 已有的 [[wiki-link]]
  - markdown 链接 [text](url) 的 url 部分
  - 标题行（行首 #）— 也参与替换，但前缀 # 保留

每段（paragraph）内每个 entity 只链一次，避免文本过于密集。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, Optional

from .updater import ENTITY_MAP as STATIC_ENTITY_MAP

WIKI_ROOT = Path(__file__).resolve().parents[2] / "wiki"

# ─── Entity map: static + dynamic scan of wiki/ ──────────────────

def _scan_wiki_slugs() -> dict[str, str]:
    """扫 wiki/{companies,products,technologies,trends}/ 收集所有 slug。
    每个 slug 自动产生两个 key：slug 本身（小写）+ 把 dash 替换成空格后的字符串。
    """
    out: dict[str, str] = {}
    for category in ("companies", "products", "technologies", "trends"):
        cdir = WIKI_ROOT / category
        if not cdir.is_dir():
            continue
        for md in cdir.glob("*.md"):
            slug = md.stem  # e.g. "google-deepmind"
            page = f"{category}/{slug}"
            out[slug.lower()] = page
            # dash → space 后也作为 key（便于匹配 "google deepmind"）
            spaced = slug.replace("-", " ")
            if spaced != slug:
                out[spaced.lower()] = page
    return out


def get_entity_map() -> dict[str, str]:
    """返回合并后的 entity map：static (updater.py) + dynamic (wiki/ 目录)."""
    merged = dict(STATIC_ENTITY_MAP)
    for k, v in _scan_wiki_slugs().items():
        merged.setdefault(k, v)  # static 优先（含别名）
    return merged


# ─── Protected-region tokenization ───────────────────────────────

# Global-level protections (applied before paragraph splitting)
_GLOBAL_PROTECT_PATTERNS = [
    (re.compile(r"\A---\n.*?\n---\n", re.DOTALL), "FRONTMATTER"),
    (re.compile(r"```.*?```", re.DOTALL), "CODEBLOCK"),
]

# Paragraph-level protections (preserve, but expose pre-existing wiki-link slugs to linker)
#
# Order matters: protect INLINECODE/MDLINK/URL **before** WIKILINK so that wiki-links
# nested inside inline code (e.g. `` `[[boss-profile]]` ``) get absorbed by the
# outer pattern. Otherwise the WIKILINK pattern claims them first, replaces with a
# placeholder, and the INLINECODE pattern then swallows the placeholder — leaving
# unrecoverable `\x00P0\x00` debris after restore.
_PARA_PROTECT_PATTERNS = [
    (re.compile(r"`[^`\n]+`"), "INLINECODE"),
    (re.compile(r"\[[^\[\]]+\]\([^)]+\)"), "MDLINK"),
    (re.compile(r"https?://\S+"), "URL"),
    (re.compile(r"\[\[[^\[\]]+\]\]"), "WIKILINK"),
]

_WIKILINK_SLUG_RE = re.compile(r"\[\[([^\[\]|#]+)(?:[|#][^\[\]]*)?\]\]")


def _protect_global(text: str) -> tuple[str, list[str]]:
    bucket: list[str] = []

    def _make_placeholder(idx: int) -> str:
        return f"\x00G{idx}\x00"

    for pattern, _label in _GLOBAL_PROTECT_PATTERNS:
        def repl(m: re.Match) -> str:
            bucket.append(m.group(0))
            return _make_placeholder(len(bucket) - 1)
        text = pattern.sub(repl, text)
    return text, bucket


def _protect_paragraph(text: str) -> tuple[str, list[str], set[str]]:
    """Returns (text_with_placeholders, bucket, pre_existing_slugs).
    pre_existing_slugs: slug names from any [[slug|...]] already in this paragraph.
    """
    bucket: list[str] = []
    existing_slugs: set[str] = set()

    def _make_placeholder(idx: int) -> str:
        return f"\x00P{idx}\x00"

    for pattern, label in _PARA_PROTECT_PATTERNS:
        def repl(m: re.Match, _label=label) -> str:
            frag = m.group(0)
            if _label == "WIKILINK":
                sm = _WIKILINK_SLUG_RE.match(frag)
                if sm:
                    existing_slugs.add(sm.group(1).strip())
            bucket.append(frag)
            return _make_placeholder(len(bucket) - 1)
        text = pattern.sub(repl, text)
    return text, bucket, existing_slugs


def _restore(text: str, bucket: list[str], prefix: str = "P") -> str:
    for i, frag in enumerate(bucket):
        text = text.replace(f"\x00{prefix}{i}\x00", frag)
    return text


# ─── Core linking ────────────────────────────────────────────────

def _link_paragraph(para: str, entity_map: dict[str, str],
                    current_page: Optional[str] = None,
                    pre_linked_pages: Optional[set[str]] = None) -> str:
    """对单段文本做 [[ ]] 包裹。每个 page 在本段只链一次。
    pre_linked_pages: 段内已有 [[slug|...]] 的 page 集合（避免再次链同一 page）。
    """
    if not para.strip():
        return para

    para_lower = para.lower()
    candidates: list[tuple[str, str, int, int]] = []

    for keyword, page in entity_map.items():
        if current_page and page == current_page:
            continue
        kw_lower = keyword.lower()
        kw_len = len(kw_lower)
        start = 0
        while True:
            idx = para_lower.find(kw_lower, start)
            if idx < 0:
                break
            end = idx + kw_len
            # Word boundary: only adjacent ASCII alphanumeric blocks fail the boundary.
            # CJK / punctuation / whitespace count as boundaries.
            def _is_word_char(ch: str) -> bool:
                return ch.isascii() and (ch.isalnum() or ch == "-")
            if idx > 0 and _is_word_char(para_lower[idx - 1]):
                start = idx + 1
                continue
            if end < len(para_lower) and _is_word_char(para_lower[end]):
                start = idx + 1
                continue
            candidates.append((keyword, page, idx, end))
            start = end

    candidates.sort(key=lambda c: (-len(c[0]), c[2]))

    linked_spans: list[tuple[int, int]] = []
    # Seed linked_pages with slugs already wiki-linked in this paragraph
    linked_pages: set[str] = set()
    if pre_linked_pages:
        for slug in pre_linked_pages:
            # find any candidate page whose slug matches and pre-add it
            for _, p in entity_map.items():
                if p.split("/")[-1] == slug:
                    linked_pages.add(p)
                    break
            else:
                # Even if not in entity_map, treat as "already linked" if slug appears
                # We can't know its category, so just skip — use a sentinel
                linked_pages.add(f"_existing/{slug}")
    chosen: list[tuple[int, int, str, str]] = []

    for keyword, page, idx, end in candidates:
        if page in linked_pages:
            continue
        if any(idx < se and end > ss for ss, se in linked_spans):
            continue
        linked_pages.add(page)
        linked_spans.append((idx, end))
        chosen.append((idx, end, page, para[idx:end]))

    for idx, end, page, original in sorted(chosen, key=lambda c: -c[0]):
        slug = page.split("/")[-1]
        para = f"{para[:idx]}[[{slug}|{original}]]{para[end:]}"
    return para


def add_links_to_markdown(text: str,
                          current_page: Optional[str] = None,
                          entity_map: Optional[dict[str, str]] = None) -> str:
    """主入口：对整篇 markdown 加 wiki-link，保护 frontmatter/code/已有 link。"""
    if entity_map is None:
        entity_map = get_entity_map()
    # Layer 1: global protect (frontmatter, fenced code blocks)
    g_protected, g_bucket = _protect_global(text)
    # Split by blank lines into paragraphs
    paragraphs = re.split(r"(\n\s*\n)", g_protected)
    out: list[str] = []
    for p in paragraphs:
        if p.strip() == "" or re.fullmatch(r"\n\s*\n", p):
            out.append(p)
            continue
        # Markdown table rows: process each row independently so each row may
        # link the same entity (e.g. 10 signals each mentioning Anthropic).
        stripped = p.lstrip()
        if stripped.startswith("|"):
            lines = p.split("\n")
            linked_lines = []
            for line in lines:
                if not line.strip().startswith("|"):
                    linked_lines.append(line)
                    continue
                p_protected, p_bucket, existing_slugs = _protect_paragraph(line)
                linked = _link_paragraph(p_protected, entity_map,
                                         current_page=current_page,
                                         pre_linked_pages=existing_slugs)
                linked_lines.append(_restore(linked, p_bucket, prefix="P"))
            out.append("\n".join(linked_lines))
            continue
        # Layer 2: paragraph protect (existing wiki-links, inline code, md-links, URLs)
        p_protected, p_bucket, existing_slugs = _protect_paragraph(p)
        linked = _link_paragraph(p_protected, entity_map,
                                 current_page=current_page,
                                 pre_linked_pages=existing_slugs)
        out.append(_restore(linked, p_bucket, prefix="P"))
    return _restore("".join(out), g_bucket, prefix="G")


# ─── CLI ─────────────────────────────────────────────────────────

def _infer_current_page(path: Path) -> Optional[str]:
    """从文件路径推断 current_page（避免自链）。
    e.g. wiki/companies/openai.md → companies/openai
    """
    try:
        rel = path.resolve().relative_to(WIKI_ROOT)
    except ValueError:
        return None
    if rel.suffix != ".md":
        return None
    return str(rel.with_suffix(""))


def link_file(path: Path, in_place: bool = False,
              entity_map: Optional[dict[str, str]] = None) -> str:
    """读文件、加链、可选原地写回。返回 (是否改变, 新内容)."""
    original = path.read_text(encoding="utf-8")
    current = _infer_current_page(path)
    linked = add_links_to_markdown(original, current_page=current,
                                   entity_map=entity_map)
    if in_place and linked != original:
        path.write_text(linked, encoding="utf-8")
    return linked


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("Usage: python -m src.wiki.linker <file_or_dir> [--in-place] [--dry-run]")
        return 0
    in_place = "--in-place" in argv
    dry_run = "--dry-run" in argv
    targets = [Path(a) for a in argv if not a.startswith("--")]
    entity_map = get_entity_map()
    changed = 0
    scanned = 0
    for t in targets:
        files: Iterable[Path]
        if t.is_dir():
            files = t.rglob("*.md")
        else:
            files = [t]
        for f in files:
            scanned += 1
            original = f.read_text(encoding="utf-8")
            current = _infer_current_page(f)
            linked = add_links_to_markdown(original, current_page=current,
                                           entity_map=entity_map)
            if linked != original:
                changed += 1
                if dry_run:
                    print(f"would change: {f}")
                elif in_place:
                    f.write_text(linked, encoding="utf-8")
                    print(f"updated: {f}")
                else:
                    print(f"=== {f} ===")
                    print(linked)
    print(f"\nscanned {scanned}, changed {changed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
