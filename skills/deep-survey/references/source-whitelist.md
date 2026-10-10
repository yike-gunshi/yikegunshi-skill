# 来源白名单与可信度分级

S2 列计划时从这里挑，按对象类型组合。白名单是优先级不是围墙：主流媒体报道仍可用，但需标为二方。

## 可信度分级

| 级 | 类型 | 例子 |
|---|---|---|
| 一方 | 对象自己发布的 | 官网、定价页、财报、招股书、官方博客、GitHub 仓库与 README、应用商店页、官方公告 |
| 一方原声 | 用户或从业者的原始发言 | 应用商店评论、Reddit / X / 小红书 / 微博 / V2EX 原帖、Product Hunt 评论、GitHub issues |
| 二方研报 | 第三方研究机构 | 艾瑞咨询、易观、前瞻产业研究院、QuestMobile、Statista、Gartner、Forrester、IBISWorld、McKinsey Global Institute、a16z、Sensor Tower / SimilarWeb 公开榜单 |
| 二方媒体 | 新闻与分析 | 36 氪、晚点、虎嗅、机器之心、量子位、TechCrunch、The Information、The Verge、Reuters、Bloomberg |
| 聚合 / 转述 | 二次整理 | 发现报告、洞见研报、199IT、镝数聚、公众号综述、自媒体长文——**只用来找原始来源，不直接作为结论依据** |

## 按类型的起手来源

| 类型 | 先查 |
|---|---|
| product | 官网与定价页 → 应用商店页与评论 → Product Hunt → Reddit / 小红书原帖 → 融资稿 → 媒体报道 |
| industry | 研报摘要（多机构并列口径）→ 上市公司财报 → 政策原文 → 行业图谱文章 → 融资数据库转述 |
| company | 官网与公告 → 财报 / 招股书 → 融资新闻 → LinkedIn → 媒体报道 → 企查查 / 天眼查公开页（库内信息进存疑） |
| ai-tool | GitHub 仓库（README、issues、commits、releases）→ 作者主页与文章 → 文档站 → 社区讨论（HN、Reddit、X）→ 本机已有 skill 清单 |

## 行业报告入口（公开可查摘要）

国内机构：艾瑞咨询、易观分析、前瞻产业研究院、QuestMobile。大厂研究院：阿里研究院、腾讯研究院、巨量算数、36 氪研究院。聚合平台：发现报告、洞见研报、萝卜投研、镝数聚、199IT。国际：Statista、Gartner、McKinsey Global Institute、Forrester、IBISWorld。使用时记录来源、发布时间、口径与研究方法，不同机构数字并列呈现。

## 本机可用的原帖抓取（确认单勾选后启用）

- 小红书：`项目/小红书抓取/`（crawl.js）
- X：`~/.claude/skills/twitter-watchdog/`（twitter_watchdog.py）
- 两者都需要本机登录态；不可用时口碑维度只用公开网页，置信度降一级并在存疑里记录。
