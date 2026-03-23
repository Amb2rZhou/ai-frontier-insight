# Pipeline Health Report

**Last checked: 2026-03-23**

## Overall Status: Healthy

All critical components operational. 3 non-critical RSS feeds intermittently unreachable.

## Component Status

### Data Collection

| Component | Status | Details |
|-----------|--------|---------|
| X-Monitor (Twitter) | OK | launchd 定时运行，今日已采集 31 条推文，数据连续无间断 |
| RSS Feeds (20/23) | OK | 20 个源正常返回，覆盖主要科技媒体和 AI 博客 |
| GitHub API | OK | search + releases 端点均 200，无 token 时 rate limit 较紧 |
| HuggingFace API | OK | daily_papers / models / spaces 均 200，无需认证 |
| Benchmarks (5/5) | OK | Open LLM / SWE-bench / ARC-AGI-2 / OSWorld / Terminal-Bench 全部可达 |

### AI Analysis

| Component | Status | Details |
|-----------|--------|---------|
| DeepSeek API | OK | api.deepseek.com 可达 (401 without key = expected) |

### Delivery

| Component | Status | Details |
|-----------|--------|---------|
| RedCity Webhook | OK | redcity-open.xiaohongshu.com 可达 |
| GitHub Pages | OK | Jekyll 站点正常构建，推送后 30s-2min 生效 |

### Scheduling

| Component | Status | Details |
|-----------|--------|---------|
| Daily pipeline (launchd) | OK | 每天 09:30 触发，约 4 分钟完成 |
| X-Monitor (launchd) | OK | 每小时触发，随机 2-5h 间隔实际运行，09:00-09:25 强制运行 |

## Known Issues

### RSS Feeds (非阻断)

| Feed | HTTP Status | Cause | Impact |
|------|-------------|-------|--------|
| Wired | 000 (连接失败) | 屏蔽 bot 请求 | 低 — 非核心 AI 源 |
| Meta Engineering | 000 (连接失败) | engineering.fb.com 在国内网络不可达 | 低 — Meta 动态可通过 Twitter/HN 获取 |
| Reddit r/MachineLearning | 403 | Reddit 限制 RSS 访问 | 低 — ML 论文已通过 HuggingFace Papers 覆盖 |

代码已有容错：单个 RSS 失败不影响其他源采集，保留 enabled 以便网络恢复后自动生效。

### Benchmark 端点 (间歇性)

- **OSWorld**: xlsx 下载偶尔超时（文件较大），但今日测试通过 (0.66s)
- **Terminal-Bench**: Next.js SSR 页面偶尔响应慢（3s），已有 60s timeout

### Rate Limits

- **GitHub API (无 token)**: Search 10 req/min, Core 60 req/hr — 代码已加 2.5s sleep 控制
- **DeepSeek API**: 按 key 配额，当前使用量未触及限制

## Architecture Resilience

- 每个 collector 独立 try/except，单个源失败不影响整体
- Benchmark collectors 逐个隔离，单个 benchmark 超时/报错不阻断其他
- Signal extraction 提取 15 条 → 代码层去重 → 最终输出 10 条
- X-Monitor cookie 过期时自动发送 webhook 告警
