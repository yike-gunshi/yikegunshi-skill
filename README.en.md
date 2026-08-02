<div align="center">

# yikegunshi-skill

**A curated collection of Agent Skills for Claude Code / Codex.**

Practical, production-tested skills for content workflows, product analysis, and knowledge management — built and maintained by [@yike-gunshi](https://github.com/yike-gunshi).

![Skills](https://img.shields.io/badge/skills-10-blue)
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
| **[prompt-craft](./skills/prompt-craft/)** | Write, revise, and review any LLM prompt: clarify requirements → draft against a 9-module architecture → adversarial review. Produces production-grade prompts that are verifiable, regression-testable, and injection-resistant (distilled from a survey of 14 external frameworks). | `写prompt`, `优化prompt`, `评审prompt` |
| **[book-to-mindmap](./skills/book-to-mindmap/)** | Turn books and long notes into high-density mind maps: claim-bearing branches, short on-canvas judgments, long explanations in notes, collapsed by default. Outputs `.xmind` and nested bullets. | `做成思维导图`, `转导图`, `生成xmind` |
| **[xhs-note](./skills/xhs-note/)** | Write a Xiaohongshu (RED) note: gather the author's own material → draft from published exemplars → de-AI review gate → generate a cover image with Codex → archive. Exemplar-first; never fabricates experiences the author didn't have. | `写小红书`, `发小红书`, `/xhs-note` |
| **[skill-build](./skills/skill-build/)** | The skill that builds skills: qualify → interview → design doc → completeness gate → write SKILL.md → eval with a with/without baseline → attribute and iterate. Ships a package linter and a rubric-discrimination auditor. | `做个skill`, `建个skill`, `skill不触发` |

## Installation

Clone the repo and install via `install.sh`, which symlinks skills into your agent's skills directory (avoid manual `cp` — copies drift as the repo updates):

```bash
git clone https://github.com/yike-gunshi/yikegunshi-skill.git
cd yikegunshi-skill

# Install all skills into ~/.claude/skills
./install.sh

# Install selected skills only
./install.sh --only lark-export --only prompt-craft

# Check status (detects broken links) / uninstall
./install.sh --status
./install.sh --uninstall
```

Codex users: add `--target codex` (installs into `~/.agents/skills`), or `--target both`.

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
│   ├── prompt-craft/
│   ├── skill-build/
│   ├── twitter-watchdog/
│   ├── wechat-publisher/
│   ├── work-logger/
│   └── xhs-note/
├── LICENSE
└── README.md
```

## Contributing

These skills are shared as-is for reference and reuse. Issues and PRs that improve portability or fix bugs are welcome.

## License

[MIT](./LICENSE) © 2026 yike-gunshi
