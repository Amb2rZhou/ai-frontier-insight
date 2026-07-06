"""Robust HTTP GET (requests-only, no curl subprocess).

历史上这里在 requests 遇到 SSL 错误时会回退到 `/usr/bin/curl` 子进程，绕开
Python 3.9 + LibreSSL 的间歇性 SSL 失败。该回退已移除：
- curl 被星点（Starpoint 终端安全）当「风险程序」拦截，导致采集卡死；
- urllib3 钉到兼容 LibreSSL 的版本后，requests 直连各源已稳定（实测 arxiv/
  github/huggingface 均 200），不再需要 curl。
现在改为 requests + 重试。
"""

import time

import requests

DEFAULT_UA = "AI-Frontier-Insight-Bot/1.0"


def robust_get(url: str, headers: dict = None, params: dict = None,
               timeout: int = 30, retries: int = 3) -> requests.Response:
    """HTTP GET，遇 SSL/连接/超时错误自动重试（纯 requests，不再 spawn curl）。

    Args:
        url: 目标 URL
        headers: 可选请求头
        params: 可选查询参数
        timeout: 单次请求超时（秒）
        retries: 最多尝试次数

    Returns:
        requests.Response

    Raises:
        最后一次的 requests 异常（重试用尽仍失败时）。
    """
    # 拆成 (connect, read) 元组：连接阶段最多 10s、读阶段用 timeout，
    # 避免卡在 TLS 握手/首字节等待上（单一标量 timeout 对 SSL 握手不总生效）。
    to = (min(10, timeout), timeout)
    last_exc = None
    for attempt in range(retries):
        try:
            return requests.get(url, headers=headers, params=params, timeout=to)
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise last_exc
