<div align="center">

# yikegunshi-skill

**A curated collection of Agent Skills for Claude Code / Codex.**

Practical, production-tested skills for content workflows, product analysis, and knowledge management — built and maintained by [@yike-gunshi](https://github.com/yike-gunshi).

![Skills](https://img.shields.io/badge/skills-6-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/Claude%20Code-compatible-8A2BE2)

[简体中文](./README.md) · **English**

</div>

---

## What is this?

An **Agent Skill** is a folder with a `SKILL.md` that teaches an AI coding agent (Claude Code, Codex) a repeatable workflow — when to trigger it, which steps to run, and which scripts to call. Drop a skill into your agent's skills directory and it becomes available on the matching trigger words.

This repository is where I keep my own reusable skills under version control, so I can restore a complete environment on any machine and share the ones that are generally useful.

## Skills

| Skill | What it does | Trigger |
|-------|--------------|---------|
| **[lark-export](./skills/lark-export/)** | Mirror a Feishu/Lark wiki or single doc to local Markdown, with images and attachments downloaded locally. Re-run to sync/update. | `同步飞书`, `导出飞书知识库` |
| **[prd-analyzer](./skills/prd-analyzer/)** | Analyze PRD documents (PDF) and product UI screenshots, then output a structured review that surfaces gaps and risks. | `分析PRD`, `/prd` |
| **[project-learner](./skills/project-learner/)** | Systematically learn any codebase — architecture, data model, core flows — and produce persistent knowledge docs + AI development guidance. | `学习项目`, `/learn-project` |
| **[work-logger](./skills/work-logger/)** | Summarize the current session's work into a dated Markdown work log. | `记录工作`, `/work-log` |
| **[twitter-watchdog](./skills/twitter-watchdog/)** | Monitor Twitter/X for AI news via a three-layer scrape → analyze → report pipeline; generates daily/weekly/monthly digests. | `抓取AI推文`, `AI日报` |
| **[wechat-publisher](./skills/wechat-publisher/)** | Publish a Markdown article to a WeChat Official Account draft: image compression → OSS upload → theming → draft box. | `发布微信`, `/wechat` |

## Installation

Clone the repo and link the skills you want into your agent's skills directory (`~/.claude/skills/` for Claude Code):

```bash
git clone https://github.com/yike-gunshi/yikegunshi-skill.git
cd yikegunshi-skill

# Link a single skill
ln -s "$PWD/skills/lark-export" ~/.claude/skills/lark-export

# …or link them all
for s in skills/*/; do ln -s "$PWD/$s" ~/.claude/skills/"$(basename "$s")"; done
```

Restart your agent (or start a new session) and the skills activate on their trigger words.

## Configuration & secrets

Some skills call third-party APIs and need credentials. **No secrets are committed to this repo** — provide them yourself:

| Skill | What to set | How |
|-------|-------------|-----|
| lark-export | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_EXPORT_HOME` | Environment variables (see the skill's `SKILL.md`) |
| twitter-watchdog | X API keys, twitterapi.io key, Anthropic key, Telegram token | Copy `config/config.example.yaml` → `config/config.yaml` and fill in |
| wechat-publisher | `WECHAT_APP_ID`, `WECHAT_APP_SECRET`, `OSS_ACCESS_KEY_ID`, `OSS_ACCESS_KEY_SECRET`, `OSS_BUCKET` | Environment variables |

`config/config.yaml`, `.env`, and other local secret files are git-ignored.

## Repository structure

```
yikegunshi-skill/
├── skills/
│   ├── lark-export/
│   ├── prd-analyzer/
│   ├── project-learner/
│   ├── twitter-watchdog/
│   ├── wechat-publisher/
│   └── work-logger/
├── LICENSE
└── README.md
```

## Contributing

These skills are shared as-is for reference and reuse. Issues and PRs that improve portability or fix bugs are welcome.

## License

[MIT](./LICENSE) © 2026 yike-gunshi
