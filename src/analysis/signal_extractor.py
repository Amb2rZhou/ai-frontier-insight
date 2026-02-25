"""Signal Extractor: Raw items → ranked, deduplicated signals.

Uses Haiku for cost-efficient high-volume filtering.
"""

import json
from typing import Dict, List, Optional

from ..collectors.base import RawItem
from ..memory.manager import load_trends
from ..utils.config import load_prompt, load_settings
from ..utils.json_repair import parse_json_response
from .ai_client import call_ai


def extract_signals(raw_items: List[RawItem]) -> Optional[List[Dict]]:
    """Extract top signals from raw items using AI.

    Args:
        raw_items: List of RawItem from all collectors

    Returns:
        List of signal dicts, or None on failure.
        Each signal: {title, signal_text, signal_strength, sources, tags}
    """
    if not raw_items:
        print("  No raw items to extract signals from")
        return []

    settings = load_settings()
    max_signals = settings.get("analysis", {}).get("daily_max_signals", 15)

    # Load current trends for novelty assessment
    trends_data = load_trends()
    trends = trends_data.get("trends", [])
    if trends:
        trends_context = json.dumps(
            [{"name": t["name"], "trajectory": t.get("trajectory", "stable"),
              "signal_count": t.get("signal_count", 0)}
             for t in trends[:20]],
            ensure_ascii=False, indent=2
        )
    else:
        trends_context = "No trends tracked yet (first run)."

    # Build compact raw items text for prompt
    raw_items_text = "\n".join(
        f"[{i}] {item.to_compact()}" for i, item in enumerate(raw_items)
    )

    # Build prompt
    prompt = load_prompt(
        "signal_extraction",
        n=len(raw_items),
        max_signals=max_signals,
        trends_context=trends_context,
        raw_items=raw_items_text,
    )

    print(f"  Signal extraction: {len(raw_items)} items → max {max_signals} signals")
    print(f"  Prompt size: {len(prompt)} chars")

    # Use Haiku for cost efficiency (high volume filtering)
    response = call_ai(prompt, "signal_extraction", use_sonnet=False, max_tokens=4096)
    if not response:
        print("  Signal extraction failed: no AI response")
        return None

    # Parse JSON response
    parsed = parse_json_response(response)
    if not parsed:
        print("  Signal extraction failed: could not parse JSON response")
        return None

    signals = parsed.get("signals", [])
    print(f"  Extracted {len(signals)} signals")

    # Sort by signal_strength descending
    signals.sort(key=lambda s: s.get("signal_strength", 0), reverse=True)

    # Trim to max
    if len(signals) > max_signals:
        signals = signals[:max_signals]

    # Attach source URLs from raw items
    for signal in signals:
        indices = signal.get("raw_item_indices", [])
        if not signal.get("sources"):
            signal["sources"] = []
            for idx in indices:
                if 0 <= idx < len(raw_items):
                    item = raw_items[idx]
                    signal["sources"].append({
                        "name": item.source_name,
                        "url": item.url,
                    })

    return signals
