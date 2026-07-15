# AGENTS.md

## Project

This repo is the AI frontier insight automation. It produces personal and department AI daily reports from collected raw sources.

## Entry Points

- Current production wrapper: `scripts/frontier_daily.sh`
- Current headless prompt: `prompts/auto/daily_run.md`
- Current launchd job: `/Users/amber/Library/LaunchAgents/com.frontier.daily.v2.plist`
- Logs: `logs/auto-{DATE}.log`, `logs/launchd-auto.out`, and `logs/launchd-auto.err`
- X/Twitter source service: `/Users/amber/x-monitor`

## Safety Gates

- Department and large-group pushes are high risk. If anything is uncertain, do not push to a group; write an issue note and send/report it to Amber personally.
- Large-group DingTalk webhook messages cannot reliably be recalled after sending.
- X/Twitter health must be judged from `data/raw_cache/{DATE}.json` by counting actual `source_type=="twitter"` rows. Treat `N >= 20` as healthy even if an x-monitor health snapshot says softblock.
- If `N < 20`, send a personal alert, continue with available data, and make the source gap explicit.
- Never commit `.env`, credentials, raw caches, department prompts, department memory, or department daily outputs.

## Gitignored Sensitive Paths

These paths are intentionally local or sensitive:

- `.env`
- `.env.bak.*`
- `prompts/dept/`
- `prompts/auto/`
- `memory_dept/`
- `data/dept_daily/`
- `data/raw_cache/`
- `scripts/frontier_daily.sh`
- `scripts/frontier_cutover.sh`

## Migration To Codex

- Do not edit the production wrapper first.
- Create a Codex-specific wrapper such as `scripts/frontier_daily_codex.sh`.
- Keep the Python collection stage unchanged.
- Replace only the headless-agent invocation after confirming the correct non-interactive Codex CLI command and permission flags on this machine.
- First Codex runs must be generate-only / no group push.
- Switch launchd only after clean dry runs.

## Operating Rules

- Before production changes, inspect current git status and treat existing runtime output as user/system-owned.
- Before making API calls or installing packages, verify parameter names, machine SSL/network compatibility, and whether the external tool is actually executable.
- For content changes, make only the requested edits. Do not reformat surrounding reports, prompts, tables, or generated artifacts unless asked.
- If the current task is about live output, verify against current repo files, logs, raw data, and launchd state rather than relying only on memory.
