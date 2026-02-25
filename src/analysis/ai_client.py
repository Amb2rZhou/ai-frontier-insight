"""AI backend client for Claude API calls.

Primary: Claude Sonnet (deep analysis)
Fallback: Claude Haiku (high-volume filtering, cost-efficient)
"""

import os
import time
from typing import Optional

import anthropic

from ..utils.config import load_settings


def _get_client() -> Optional[anthropic.Anthropic]:
    """Create Anthropic client if API key is available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  Warning: ANTHROPIC_API_KEY not set")
        return None
    return anthropic.Anthropic(api_key=api_key)


def call_sonnet(prompt: str, label: str, max_tokens: int = 4096) -> Optional[str]:
    """Call Claude Sonnet (primary model for deep analysis).

    Returns response text or None on failure.
    """
    client = _get_client()
    if not client:
        return None

    settings = load_settings()
    model = settings.get("analysis", {}).get("model_primary", "claude-sonnet-4-20250514")

    try:
        start = time.time()
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.time() - start
        print(f"  - Sonnet ({label}) {elapsed:.1f}s, stop={resp.stop_reason}")
        if resp.stop_reason == "max_tokens":
            print(f"  - WARNING: Response truncated (hit max_tokens={max_tokens})")
        return resp.content[0].text
    except Exception as e:
        print(f"  - Sonnet ({label}) error: {e}")
        return None


def call_haiku(prompt: str, label: str, max_tokens: int = 4096) -> Optional[str]:
    """Call Claude Haiku (fallback model, cost-efficient for filtering).

    Returns response text or None on failure.
    """
    client = _get_client()
    if not client:
        return None

    settings = load_settings()
    model = settings.get("analysis", {}).get("model_fallback", "claude-haiku-4-5-20251001")

    try:
        start = time.time()
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.time() - start
        print(f"  - Haiku ({label}) {elapsed:.1f}s, stop={resp.stop_reason}")
        if resp.stop_reason == "max_tokens":
            print(f"  - WARNING: Response truncated (hit max_tokens={max_tokens})")
        return resp.content[0].text
    except Exception as e:
        print(f"  - Haiku ({label}) error: {e}")
        return None


def call_ai(prompt: str, label: str, use_sonnet: bool = False,
            max_tokens: int = 4096) -> Optional[str]:
    """Call AI with automatic fallback.

    Args:
        prompt: The prompt text
        label: Label for logging
        use_sonnet: If True, use Sonnet primary; otherwise Haiku
        max_tokens: Maximum tokens in response

    Returns response text or None if all backends fail.
    """
    if use_sonnet:
        result = call_sonnet(prompt, label, max_tokens)
        if result:
            return result
        print(f"  - Sonnet failed for {label}, falling back to Haiku...")
        return call_haiku(prompt, label, max_tokens)
    else:
        result = call_haiku(prompt, label, max_tokens)
        if result:
            return result
        print(f"  - Haiku failed for {label}, falling back to Sonnet...")
        return call_sonnet(prompt, label, max_tokens)
