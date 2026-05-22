"""AI backend client — supports DeepSeek and Anthropic.

Backend selection:
  - DEEPSEEK_API_KEY set → use DeepSeek (OpenAI-compatible)
  - ANTHROPIC_API_KEY set → use Anthropic Claude
  - Both set → prefer DeepSeek (cheaper), auto-fallback to Anthropic on failure/timeout

Timeout:
  - 单次 API 调用默认 300s (5 min) 超时，可由 AI_API_TIMEOUT env 覆盖
  - 超时后立即抛错，由调用者（signal_extractor 等）的重试逻辑接管

DeepSeek models: deepseek-chat (V3)
Anthropic models: Sonnet (primary) + Haiku (fallback)
"""

import os
import time
from typing import Optional

from ..utils.config import load_settings


# 单次 API 调用超时秒数（防止 DeepSeek 偶发响应几小时把 pipeline 卡住）
API_TIMEOUT_SECONDS = float(os.environ.get("AI_API_TIMEOUT", "300"))


def _get_backend() -> str:
    """Determine which AI backend to use."""
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "none"


def _has_anthropic_fallback() -> bool:
    """Anthropic key 存在时，DeepSeek 失败可跨后端 fallback。"""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


# ─── DeepSeek (OpenAI-compatible) ────────────────────────────

def _call_deepseek(prompt: str, label: str, max_tokens: int = 4096) -> Optional[str]:
    """Call DeepSeek API (OpenAI-compatible)."""
    try:
        from openai import OpenAI
    except ImportError:
        print("  Warning: openai package not installed, run: pip3 install openai")
        return None

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    # timeout: 防止 DeepSeek 偶发慢响应把 pipeline 卡死
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=API_TIMEOUT_SECONDS,
        max_retries=0,  # 关闭 SDK 内置重试，由上层 call_ai/signal_extractor 控制
    )

    try:
        start = time.time()
        resp = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.time() - start
        finish = resp.choices[0].finish_reason
        print(f"  - DeepSeek ({label}) {elapsed:.1f}s, stop={finish}")
        if finish == "length":
            print(f"  - WARNING: Response truncated (hit max_tokens={max_tokens})")
        return resp.choices[0].message.content
    except Exception as e:
        print(f"  - DeepSeek ({label}) error: {e} (timeout={API_TIMEOUT_SECONDS}s)")
        return None


# ─── Anthropic ───────────────────────────────────────────────

def _call_anthropic(prompt: str, label: str, model: str = None,
                    max_tokens: int = 4096) -> Optional[str]:
    """Call Anthropic Claude API."""
    try:
        import anthropic
    except ImportError:
        print("  Warning: anthropic package not installed")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    if not model:
        settings = load_settings()
        model = settings.get("analysis", {}).get("model_primary", "claude-sonnet-4-20250514")

    client = anthropic.Anthropic(
        api_key=api_key,
        timeout=API_TIMEOUT_SECONDS,
        max_retries=0,
    )

    try:
        start = time.time()
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.time() - start
        print(f"  - Claude ({label}) {elapsed:.1f}s, stop={resp.stop_reason}")
        if resp.stop_reason == "max_tokens":
            print(f"  - WARNING: Response truncated (hit max_tokens={max_tokens})")
        return resp.content[0].text
    except Exception as e:
        print(f"  - Claude ({label}) error: {e} (timeout={API_TIMEOUT_SECONDS}s)")
        return None


# ─── Public API ──────────────────────────────────────────────

def _anthropic_with_model(prompt: str, label: str, kind: str, max_tokens: int) -> Optional[str]:
    """Call Anthropic with model picked by kind ('primary' or 'fallback')."""
    settings = load_settings()
    key = "model_primary" if kind == "primary" else "model_fallback"
    default = "claude-sonnet-4-20250514" if kind == "primary" else "claude-haiku-4-5-20251001"
    model = settings.get("analysis", {}).get(key, default)
    return _call_anthropic(prompt, label, model, max_tokens)


def call_sonnet(prompt: str, label: str, max_tokens: int = 4096) -> Optional[str]:
    """Call primary model (DeepSeek → Anthropic 跨后端 fallback)."""
    backend = _get_backend()
    if backend == "deepseek":
        result = _call_deepseek(prompt, label, max_tokens)
        if result is None and _has_anthropic_fallback():
            print(f"  - DeepSeek 失败/超时，切 Anthropic Sonnet 重试 ({label})")
            return _anthropic_with_model(prompt, label, "primary", max_tokens)
        return result
    elif backend == "anthropic":
        return _anthropic_with_model(prompt, label, "primary", max_tokens)
    print("  Warning: No AI API key set (DEEPSEEK_API_KEY or ANTHROPIC_API_KEY)")
    return None


def call_haiku(prompt: str, label: str, max_tokens: int = 4096) -> Optional[str]:
    """Call lightweight model (DeepSeek → Anthropic Haiku 跨后端 fallback)."""
    backend = _get_backend()
    if backend == "deepseek":
        # DeepSeek 只有一个 model，跟 call_sonnet 相同
        result = _call_deepseek(prompt, label, max_tokens)
        if result is None and _has_anthropic_fallback():
            print(f"  - DeepSeek 失败/超时，切 Anthropic Haiku 重试 ({label})")
            return _anthropic_with_model(prompt, label, "fallback", max_tokens)
        return result
    elif backend == "anthropic":
        return _anthropic_with_model(prompt, label, "fallback", max_tokens)
    print("  Warning: No AI API key set (DEEPSEEK_API_KEY or ANTHROPIC_API_KEY)")
    return None


def call_ai(prompt: str, label: str, use_sonnet: bool = False,
            max_tokens: int = 4096) -> Optional[str]:
    """Call AI with automatic fallback.

    Args:
        prompt: The prompt text
        label: Label for logging
        use_sonnet: If True, try primary model first
        max_tokens: Maximum tokens in response

    Returns response text or None if all backends fail.
    """
    if use_sonnet:
        result = call_sonnet(prompt, label, max_tokens)
        if result:
            return result
        print(f"  - Primary failed for {label}, trying fallback...")
        return call_haiku(prompt, label, max_tokens)
    else:
        result = call_haiku(prompt, label, max_tokens)
        if result:
            return result
        print(f"  - Fallback failed for {label}, trying primary...")
        return call_sonnet(prompt, label, max_tokens)
