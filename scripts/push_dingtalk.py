#!/usr/bin/env python3
"""把当天的 AI 前沿日报推送到钉钉机器人（加签）。

精简成聊天友好版：每条只保留 标题(链接) + 💡洞察 + →建议，去掉长摘要；
末尾附趋势总结和网站完整版链接。

环境变量：DINGTALK_WEBHOOK, DINGTALK_SECRET（从 .env 加载）。
用法：python scripts/push_dingtalk.py [YYYY-MM-DD] [--dept]
  --dept  推部门版（读 data/dept_daily/，标题标「部门版试运行」，不带个人网站链接）
"""
import os
import re
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


def build_message(md_path: Path, dept: bool = False) -> str:
    if dept:
        return _build_dept_message(md_path)

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


def _build_dept_message(md_path: Path) -> str:
    """部门版：每条 signal 排成 中文标题 / 📌事件 / 💡洞察 / 👉对我们 / 原文链接，
    让人扫一眼就看清『发生了什么』。"""
    lines = md_path.read_text(encoding="utf-8").splitlines()
    out = ["## 🏢 AI 日报 · 部门版（试运行）"]
    in_trend = False
    cur_url = ""
    for ln in lines:
        s = ln.strip()
        if s.startswith("### Signal"):
            body = s[len("### Signal"):].lstrip()
            num, _, rest = body.partition(":")
            rest = rest.strip()
            m = re.match(r"\[(.+?)\]\((.+?)\)$", rest)
            if m:
                title, cur_url = m.group(1), m.group(2)
            else:
                title, cur_url = rest, ""
            out.append("")
            out.append(f"**{num.strip()}. {title}**")
        elif s.startswith("*Source:"):
            continue  # 推送里不展示来源行，溯源走末尾「原文 →」链接
        elif s.startswith("> 💡"):
            out.append(f"💡 {s[len('> 💡'):].strip()}")
        elif s.startswith("> →"):
            out.append(f"👉 {s[len('> →'):].strip()}")
            if cur_url:
                out.append(f"[原文 →]({cur_url})")
                cur_url = ""
        elif s.startswith("## Frontier Trend Summary"):
            in_trend = True
            out.append("")
            out.append("---")
            out.append("**📈 趋势总结**")
        elif in_trend:
            if s and not s.startswith("#") and not s.startswith("---") and not s.startswith("*AI"):
                out.append(s)
        elif s and not s.startswith("#") and not s.startswith("---") and not s.startswith("*"):
            # signal 标题与 💡 之间的中文事实段 = 发生了什么
            out.append(f"📌 {s}")
    out.append("")
    out.append("*部门版试运行中，视角/选题反馈请直接找衹月*")
    text = "\n\n".join(out)
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN] + "\n\n…（内容过长已截断）"
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

    args = sys.argv[1:]
    dept = "--dept" in args

    # --text-file <path>：直接推送指定文件里的 markdown 原文（用于头条+语雀链接这类已生成好的消息）
    text_file = None
    if "--text-file" in args:
        i = args.index("--text-file")
        text_file = args[i + 1] if i + 1 < len(args) else None

    if text_file:
        tf = Path(text_file)
        if not tf.exists():
            print(f"::error:: 文本文件不存在: {tf}")
            sys.exit(1)
        text = tf.read_text(encoding="utf-8")
        if len(text) > MAX_LEN:
            text = text[:MAX_LEN] + "\n\n…（内容过长已截断）"
    else:
        dates = [a for a in args if not a.startswith("--")]
        day = dates[0] if dates else date.today().isoformat()
        subdir = "dept_daily" if dept else "daily"
        md_path = REPO / "data" / subdir / day / f"{day}_daily.md"
        if not md_path.exists():
            print(f"::error:: 当天日报不存在: {md_path}")
            sys.exit(1)
        text = build_message(md_path, dept=dept)
    title = "AI 日报·部门版" if dept else "AI 前沿日报"  # 含 "AI" 满足关键词
    body = json.dumps({
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
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
