# 示范：把 Anthropic 官方提示词库里的 prompt 收进个人 prompt 库

日期：2026-10-22

给 prompt-vault 一个有 prompt 的网页，它把里面的 prompt 抽出来，整理成格式统一、分好类、带出处的 prompt 卡片，再生成一份总目录。这个目录是一次真实运行的完整记录。

## 给了什么

一个网页：Anthropic 官方 Claude Code 文档里的「提示词库」页面。

- 中文版：https://code.claude.com/docs/zh-CN/prompt-library
- 英文原页：https://code.claude.com/docs/en/prompt-library

从里面挑了三条不写代码的人也看得懂的 prompt：

- 将会议转化为工单（Turn a meeting into tickets）
- 根据以往示例起草文档（Draft a document from past examples）
- 根据效果数据生成变体（Generate variations from performance data）

页面链接和挑选说明见 [input/来源.md](input/来源.md)。

> 说明：Anthropic 早先在通用开发文档里的那版提示词库已经下线，旧地址会跳到「提示词最佳实践」页面。现在官方维护的提示词库在 Claude Code 文档下，所以这三条是写给 Claude Code 用的，里面的 `@文件名`、文件夹指的是你电脑上的文件。

## 用户会怎么说

> 这个页面里有几条 prompt 挺好用的，帮我把「将会议转化为工单」「根据以往示例起草文档」「根据效果数据生成变体」收进我的 prompt 库：https://code.claude.com/docs/zh-CN/prompt-library

## Skill 做了什么

1. **抓取网页**：页面正文只有说明文字，prompt 卡片藏在页面代码里，Skill 从页面代码中取出卡片原文，中文版和英文原版都拿到了。
2. **提炼**：每条拆出官方中文版、英文原版、官方页面给的填空示例、官方的「为什么这样做有效」说明，以及卡片标注的原始出处。
3. **确认卡**：每条把拟定标题、分类、标签、原文全文、来源列给用户确认。本示范由 AI 代为确认，见下一节。
4. **写成统一文档**：按 prompt 库的固定模板写，原文放进代码块，方便一键复制。
5. **归类并重建目录**：按分类放进对应文件夹，用 Skill 自带的脚本生成总目录。
6. **提交推送**：真实使用时这一步会提交并推送到 GitHub。本示范只在本地生成，没有写进真实的 prompt 库，也没有提交和推送。

## 代确认的门禁

真实使用时这些地方要用户拍板，本示范逐处选默认：

- 确认卡「会议记录转待办工单」：选「入库」—— 演示时由 AI 按默认确认
- 确认卡「照以往范文起草新文档」：选「入库」—— 演示时由 AI 按默认确认
- 确认卡「按效果数据重写广告标题」：选「入库」—— 演示时由 AI 按默认确认
- 分类「会议记录转待办工单」：候选「产品 · 原型」和「写作文案」，选「产品 · 原型」（官方给这条打的角色标签是「产品」）—— 演示时由 AI 按默认确认
- 分类「照以往范文起草新文档」：选「写作文案」—— 演示时由 AI 按默认确认
- 分类「按效果数据重写广告标题」：选「写作文案」—— 演示时由 AI 按默认确认
- 新增分类：不新增，沿用库里已有的分类 —— 演示时由 AI 按默认确认
- 命名：原文是英文，按库的规则文件名保留英文原名，卡片标题用中文 —— 演示时由 AI 按默认确认
- 中文版：直接用官方中文页面的译文，不另做翻译 —— 演示时由 AI 按默认确认
- 原文边界：三条都是完整的一句话，没有拿不准的段落，原样收录 —— 演示时由 AI 按默认确认

## 得到了什么

`output/` 是一个只装了这三条的小型 prompt 库，目录结构和真实的库一样：

| 文件 | 内容 |
|---|---|
| [output/README.md](output/README.md) | 总目录：按分类分节，每条一行，标题、说明、标签、适用工具一目了然 |
| [output/product/01-turn-a-meeting-into-tickets.md](output/product/01-turn-a-meeting-into-tickets.md) | 会议记录转待办工单 |
| [output/writing/01-draft-a-document-from-past-examples.md](output/writing/01-draft-a-document-from-past-examples.md) | 照以往范文起草新文档 |
| [output/writing/02-generate-variations-from-performance-data.md](output/writing/02-generate-variations-from-performance-data.md) | 按效果数据重写广告标题 |

每张卡片里有：一句话说明和怎么替换、可一键复制的 prompt（官方中文版、英文原版、填好的示例）、出处和版权说明。官方页面只给了 prompt，没有附效果截图，所以卡片里没有「效果案例」这一节。

## 版权与出处

三条 prompt 的原文和中文译文都来自 Anthropic 官方文档，版权归 Anthropic。每张卡片的「来源」一节都写明了页面链接、卡片名和卡片标注的原始出处。本示范只做摘录和整理，用于演示 prompt-vault 的效果。
