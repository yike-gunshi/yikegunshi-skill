<div align="center">

# yikegunshi-skill

**一套精选的 Claude Code / Codex Agent Skill 合集。**

面向内容工作流、产品分析与知识管理的实用 skill，由 [@yike-gunshi](https://github.com/yike-gunshi) 构建与维护。

![Skills](https://img.shields.io/badge/skills-6-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/Claude%20Code-compatible-8A2BE2)

[English](./README.md) · **简体中文**

</div>

---

## 这是什么？

**Agent Skill** 是一个带 `SKILL.md` 的文件夹，用来教 AI 编码代理（Claude Code、Codex）一套可复用的工作流——什么时候触发、执行哪些步骤、调用哪些脚本。把一个 skill 放进代理的 skills 目录，它就会在匹配的触发词上生效。

这个仓库用来对我自己可复用的 skill 做版本管理，方便在任何机器上快速恢复完整环境，并把其中通用的部分分享出来。

## Skill 一览

| Skill | 作用 | 触发词 |
|-------|------|--------|
| **[lark-export](./skills/lark-export/)** | 把飞书/Lark 知识库或单篇文档镜像成本地 Markdown，图片和附件一并下载到本地。重复运行即同步更新。 | `同步飞书`、`导出飞书知识库` |
| **[prd-analyzer](./skills/prd-analyzer/)** | 分析 PRD 文档（PDF）与产品界面截图，输出结构化评审，暴露缺口与风险。 | `分析PRD`、`/prd` |
| **[project-learner](./skills/project-learner/)** | 系统性学习任意代码库——架构、数据模型、核心流程——产出可持久化的知识文档 + AI 开发指导。 | `学习项目`、`/learn-project` |
| **[work-logger](./skills/work-logger/)** | 把当前会话完成的工作总结成一份按日期命名的 Markdown 工作日志。 | `记录工作`、`/work-log` |
| **[twitter-watchdog](./skills/twitter-watchdog/)** | 通过「抓取 → 分析 → 报告」三层流水线监控 Twitter/X 上的 AI 动态，生成日报/周报/月报。 | `抓取AI推文`、`AI日报` |
| **[wechat-publisher](./skills/wechat-publisher/)** | 把 Markdown 文章发布到微信公众号草稿箱：图片压缩 → OSS 上传 → 排版 → 草稿箱。 | `发布微信`、`/wechat` |

## 安装

克隆仓库，把想用的 skill 链接到代理的 skills 目录（Claude Code 为 `~/.claude/skills/`）：

```bash
git clone https://github.com/yike-gunshi/yikegunshi-skill.git
cd yikegunshi-skill

# 链接单个 skill
ln -s "$PWD/skills/lark-export" ~/.claude/skills/lark-export

# 或者全部链接
for s in skills/*/; do ln -s "$PWD/$s" ~/.claude/skills/"$(basename "$s")"; done
```

重启代理（或开新会话），skill 会在其触发词上激活。

## 配置与密钥

部分 skill 会调用第三方 API，需要凭证。**本仓库不包含任何密钥**——请自行提供：

| Skill | 需要设置 | 方式 |
|-------|----------|------|
| lark-export | `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_EXPORT_HOME` | 环境变量（见该 skill 的 `SKILL.md`） |
| twitter-watchdog | X API key、twitterapi.io key、Anthropic key、Telegram token | 复制 `config/config.example.yaml` → `config/config.yaml` 后填入 |
| wechat-publisher | `WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`、`OSS_BUCKET` | 环境变量 |

`config/config.yaml`、`.env` 等本地密钥文件已被 git 忽略。

## 仓库结构

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

## 贡献

这些 skill 以现状分享，供参考与复用。欢迎提交改善可移植性或修复 bug 的 issue 与 PR。

## 许可

[MIT](./LICENSE) © 2026 yike-gunshi
