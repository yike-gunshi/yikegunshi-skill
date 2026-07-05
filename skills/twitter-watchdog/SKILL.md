---
name: twitter-watchdog
description: |
  Twitter AI 新闻监控与报告工具。三层架构：抓取 → AI 分析 → 报告生成，各层独立执行。
  触发方式：
  - "抓取最新AI推文" / "抓取最近N小时的AI新闻"
  - "生成AI周报" / "生成本周AI报告"
  - "生成AI月报" / "生成N月AI月报"
  - "看看最近有什么AI新闻"
  - "twitter watchdog" / "AI日报"
---

# Twitter Watchdog — AI 新闻日报/周报/月报

## 基本信息

- **脚本路径**: `<SKILL_DIR>/scripts/twitter_watchdog.py`
- **配置文件**: `<SKILL_DIR>/config/config.yaml`
- **Python 环境**: `<SKILL_DIR>/venv/bin/python3`
- **数据目录**: `<SKILL_DIR>/output/`（所有数据累积存放于此）

## 三层架构

```
Layer 1: scrape          Layer 2: analyze          Layer 3: report
(数据采集)               (AI 分析)                  (报告生成)

raw/*.json        →    analysis/*.json      →    reports/*.{html,md}
```

- **Layer 1 (scrape)**: 抓取关注列表全量推文 + 热门搜索，不做任何过滤，保存原始数据
- **Layer 2 (analyze)**: 读取 raw 数据，Codex AI 判断 AI 相关性 + 生成总结
- **Layer 3 (report)**: 读取 analysis 数据，下载配图，生成 HTML + Markdown 报告

## 命令速查

所有命令都使用 skill 自带的 venv 运行：

```bash
PYTHON=<SKILL_DIR>/venv/bin/python3
SCRIPT=<SKILL_DIR>/scripts/twitter_watchdog.py
CONFIG=<SKILL_DIR>/config/config.yaml
```

**注意**：全局参数（如 `--hours-ago`、`--config`）必须放在子命令前面。

### 流水线模式（最简单，三步串行）

```bash
# 抓取 + 分析 + 生成报告（向后兼容）
$PYTHON $SCRIPT --config $CONFIG --hours-ago 8
```

### Layer 1: 抓取原始数据

```bash
# 抓取最近 N 小时的推文（不做 AI 过滤，保存全量）
$PYTHON $SCRIPT --config $CONFIG --hours-ago 8 scrape

# 禁用热门搜索（只看关注列表）
$PYTHON $SCRIPT --config $CONFIG --hours-ago 4 --no-trending scrape
```

### Layer 2: AI 分析

```bash
# 分析最新的 raw 文件
$PYTHON $SCRIPT --config $CONFIG --hours-ago 8 analyze

# 指定 raw 文件
$PYTHON $SCRIPT --config $CONFIG analyze --source output/raw/20260212_140000.json

# 指定时间范围
$PYTHON $SCRIPT --config $CONFIG analyze --from "2026-02-12 08:00" --to "2026-02-12 14:00"
```

### Layer 3: 生成报告

```bash
# 从最新 analysis 文件生成报告
$PYTHON $SCRIPT --config $CONFIG report

# 指定 analysis 文件
$PYTHON $SCRIPT --config $CONFIG report --source output/analysis/20260212_143000.json

# 日报（聚合当天所有 analysis）
$PYTHON $SCRIPT --config $CONFIG report --daily 2026-02-12

# 周报（从指定日期起 7 天）
$PYTHON $SCRIPT --config $CONFIG report --weekly 2026-02-10

# 月报
$PYTHON $SCRIPT --config $CONFIG report --monthly 2026-02
```

## 输出文件

```
output/
├── raw/                    # Layer 1: 原始抓取数据（全量推文）
│   └── YYYYMMDD_HHMMSS.json
├── analysis/               # Layer 2: AI 分析结果
│   └── YYYYMMDD_HHMMSS.json
└── reports/                # Layer 3: 最终报告
    ├── YYYYMMDD_HHMMSS.html    # 单次报告
    ├── YYYYMMDD_HHMMSS.md
    ├── daily_YYYYMMDD.html     # 日报
    ├── weekly_YYYYMMDD.html    # 周报
    ├── monthly_YYYYMM.html     # 月报
    ├── latest.html             # 最新报告
    └── images/                 # 推文配图
```

## CLI 完整参数

### 全局参数（放在子命令前面）

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config PATH` | 配置文件路径 | `config/config.yaml` |
| `--output-dir PATH` | 输出目录 | 见配置文件 |
| `--hours-ago N` | 时间窗口（小时） | 不限 |
| `--max-followings N` | 关注列表抓取范围（0=全部） | 0 |
| `--tweets-per-user N` | 每个用户最多推文数 | 20 |
| `--trending-count N` | 热门推文最多条数 | 20 |
| `--min-faves N` | 热门推文最低浏览量 | 2000 |
| `--language LANG` | 语言过滤（all/en/zh/ja...） | all |
| `--exclude-users "a,b"` | 排除的用户名 | 无 |
| `--reset-state` | 重置去重状态 | - |
| `--no-trending` | 禁用热门搜索 | - |
| `--no-summary` | 禁用 AI 总结 | - |

### analyze 子命令参数

| 参数 | 说明 |
|------|------|
| `--source PATH` | 指定 raw JSON 文件路径（默认取最新） |
| `--from "YYYY-MM-DD HH:MM"` | 起始时间 |
| `--to "YYYY-MM-DD HH:MM"` | 结束时间 |

### report 子命令参数

| 参数 | 说明 |
|------|------|
| `--source PATH` | 指定 analysis JSON 文件路径（默认取最新） |
| `--daily YYYY-MM-DD` | 生成日报（聚合当天所有 analysis） |
| `--weekly YYYY-MM-DD` | 生成周报（从指定日期起 7 天） |
| `--monthly YYYY-MM` | 生成月报 |

### Layer 4: 推送到 Telegram

```bash
# 推送最新分析摘要到 Telegram
$PYTHON $SCRIPT --config $CONFIG push

# 指定 analysis 文件推送
$PYTHON $SCRIPT --config $CONFIG push --source output/analysis/20260212_143000.json

# 测试推送配置（发送测试消息）
$PYTHON $SCRIPT --config $CONFIG push --test
```

## MVP 个性化配置

### 源头个性化 — custom_accounts

在 `twitter.custom_accounts` 中添加额外关注的账号（不在关注列表中也能抓取）：

```yaml
twitter:
  custom_accounts:
    - "AnthropicAI"
    - "OpenAI"
    - "GoogleDeepMind"
```

### 处理个性化 — style + custom_prompt

```yaml
ai_summary:
  style: "standard"       # concise(一句话) / standard(默认) / advanced(含分析)
  custom_prompt: ""        # 追加到 AI prompt 末尾，如"重点关注 Agent 和 MCP 方向"
```

- **concise**: 每条推文一句话摘要（≤30字），只保留核心事实
- **standard**: 当前默认风格（1-2 句说明）
- **advanced**: standard + 每条增加"为什么重要"分析

### 紧急度分级

AI 自动将推文分为：
- 🔴 **突发** (urgent)：重大产品发布、安全事件、行业巨变 → 即时推送到 Telegram
- 🟡/🟢 **常规**：日常新闻，随日报推送

### Telegram 推送

```yaml
push:
  enabled: true
  telegram:
    bot_token: "your_bot_token"    # 从 @BotFather 获取
    chat_id: "your_chat_id"       # 从 @userinfobot 获取
```

### push 子命令参数

| 参数 | 说明 |
|------|------|
| `--source PATH` | 指定 analysis JSON 文件路径（默认取最新） |
| `--test` | 测试推送配置（发送测试消息） |

## 使用提示

- 日报/周报/月报基于 `output/analysis/` 中的历史数据，确保有足够的历史分析结果
- 建议配合 cron/launchd 定时运行 scrape（每天 3-4 次），保证数据完整
- 如果用户只说"看看AI新闻"，默认用 `--hours-ago 8` 运行流水线
- 如果用户说"生成月报"但没指定月份，用当前月份
- 如果用户说"生成周报"但没指定日期，用上周一的日期
- 运行完成后，读取生成的报告文件展示给用户
- analyze 和 report 子命令不需要 Twitter API 凭证，只需要 Codex API 和历史数据
