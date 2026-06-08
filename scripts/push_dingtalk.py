#!/usr/bin/env python3
"""把当天的 AI 前沿日报推送到钉钉机器人（加签）。

精简成聊天友好版：每条只保留 标题(链接) + 💡洞察 + →建议，去掉长摘要；
末尾附趋势总结和网站完整版链接。

环境变量：DINGTALK_WEBHOOK, DINGTALK_SECRET（从 .env 加载）。
用法：python scripts/push_dingtalk.py [YYYY-MM-DD]
"""
import os
import sys
import time
import hmac
import json
import base64
import hashlib
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

SITE_URL = "https://amb2rzhou.github.io/ai-frontier-insight/"
MAX_LEN = 18000  # 钉钉 markdown 上限约 20000 字符，留余量
REPO = Path(__file__).resolve().parents[1]


def build_message(md_path: Path) -> str:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    out, in_trend = [], False
    out.append("## 📡 AI 前沿日报")
    for ln in lines:
        s = ln.strip()
        if s.startswith("### Signal"):
            # "### Signal 1: [title](url)" -> "**1. [title](url)**"
            body = s[len("### Signal"):].lstrip()
            num, _, rest = body.partition(":")
            out.append("")
            out.append(f"**{num.strip()}. {rest.strip()}**")
        elif s.startswith("> 💡") or s.startswith("> →"):
            out.append(s[2:].strip())
        elif s.startswith("## Frontier Trend Summary"):
            in_trend = True
            out.append("")
            out.append("---")
            out.append("**📈 趋势总结**")
        elif in_trend and s and not s.startswith("#") and not s.startswith("---") and not s.startswith("*AI"):
            out.append(s)
    out.append("")
    out.append(f"[查看完整版 →]({SITE_URL})")
    text = "\n\n".join(out)
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN] + f"\n\n…（内容过长已截断）[完整版 →]({SITE_URL})"
    return text


def sign_url(webhook: str, secret: str) -> str:
    ts = str(round(time.time() * 1000))
    sign = urllib.parse.quote_plus(base64.b64encode(
        hmac.new(secret.encode(), f"{ts}\n{secret}".encode(), hashlib.sha256).digest()))
    return f"{webhook}&timestamp={ts}&sign={sign}"


def main():
    webhook = os.environ.get("DINGTALK_WEBHOOK", "").strip()
    secret = os.environ.get("DINGTALK_SECRET", "").strip()
    if not webhook or not secret:
        print("::error:: 缺少 DINGTALK_WEBHOOK 或 DINGTALK_SECRET")
        sys.exit(1)

    day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    md_path = REPO / "data" / "daily" / day / f"{day}_daily.md"
    if not md_path.exists():
        print(f"::error:: 当天日报不存在: {md_path}")
        sys.exit(1)

    text = build_message(md_path)
    body = json.dumps({
        "msgtype": "markdown",
        "markdown": {"title": "AI 前沿日报", "text": text},  # 含 "AI" 满足关键词
        "at": {"isAtAll": False},
    }).encode("utf-8")

    url = sign_url(webhook, secret)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    if resp.get("errcode") == 0:
        print(f"钉钉推送成功 ({len(text)} 字符)")
    else:
        print(f"::error:: 钉钉推送失败: {resp}")
        sys.exit(1)


if __name__ == "__main__":
    main()
