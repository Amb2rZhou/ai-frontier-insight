"""RedCity webhook delivery.

Adapted from daily-news-digest send_webhook.py.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from ..utils.config import load_settings


def _get_webhook_key() -> Optional[str]:
    """Get webhook key from environment variable."""
    key = os.environ.get("WEBHOOK_KEY", "").strip()
    if key:
        return key

    # Fallback: try WEBHOOK_KEYS JSON with 'frontier' key
    keys_json = os.environ.get("WEBHOOK_KEYS", "").strip()
    if keys_json:
        try:
            keys_map = json.loads(keys_json)
            key = keys_map.get("frontier", keys_map.get("default", ""))
            if key:
                return key.strip()
        except (json.JSONDecodeError, AttributeError):
            pass

    print("  Warning: No webhook key found (set WEBHOOK_KEY env var)")
    return None


def _post_webhook(url: str, content: str, mention_all: bool = True) -> str:
    """Post a single markdown message to webhook.

    Returns:
        "ok"            - success
        "api_error"     - server rejected (safe to retry smaller)
        "network_error" - network issue (NOT safe to retry)
    """
    markdown_body = {"content": content}
    if mention_all:
        markdown_body["mentioned_list"] = ["@all"]
    payload = {
        "msgtype": "markdown",
        "markdown": markdown_body,
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"  Webhook response: {result}")
            errcode = result.get("errcode", 0)
            if errcode != 0:
                errmsg = result.get("errmsg", "unknown error")
                print(f"  Webhook API error: {errcode} - {errmsg}")
                return "api_error"
            return "ok"
    except urllib.error.HTTPError as e:
        print(f"  Webhook HTTP error: {e.code} {e.reason}")
        return "api_error"
    except Exception as e:
        print(f"  Webhook network error: {e}")
        return "network_error"


def send_webhook(content: str, mention_all: bool = True) -> bool:
    """Send markdown content to RedCity webhook.

    Args:
        content: Markdown string to send
        mention_all: Whether to @all in this message

    Returns:
        True on success
    """
    webhook_key = _get_webhook_key()
    if not webhook_key:
        return False

    settings = load_settings()
    url_base = settings.get("delivery", {}).get("webhook", {}).get(
        "url_base",
        "https://redcity-open.xiaohongshu.com/api/robot/webhook/send",
    )
    url = f"{url_base}?key={webhook_key}"

    content_bytes = len(content.encode("utf-8"))
    print(f"  Webhook message: {content_bytes} bytes")

    result = _post_webhook(url, content, mention_all=mention_all)
    if result == "ok":
        return True

    if result == "network_error":
        print("  Network error — skipping retry to avoid duplicate")
        return False

    # API error — try trimming content
    # Simple strategy: truncate at 80%, 60%, 40% of original
    for ratio in [0.8, 0.6, 0.4]:
        truncated = content[:int(len(content) * ratio)]
        # Try to cut at a clean line boundary
        last_newline = truncated.rfind("\n")
        if last_newline > len(truncated) * 0.5:
            truncated = truncated[:last_newline]
        truncated += "\n\n---\n(message truncated)"

        print(f"  Retrying at {int(ratio*100)}% ({len(truncated.encode('utf-8'))} bytes)")
        result = _post_webhook(url, truncated, mention_all=mention_all)
        if result == "ok":
            return True
        if result == "network_error":
            print("  Network error during retry — stopping")
            return False

    print("  All retry attempts failed")
    return False
