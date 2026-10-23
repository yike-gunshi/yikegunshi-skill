---
title: 会议记录转待办工单
summary: 让 Claude Code 读会议记录、整理出行动项，并在你的任务工具里为每一项建一张带验收标准的工单
category: product
tags: [会议纪要, 行动项, 工单, Claude Code]
model: Claude Code
source_name: Anthropic · Claude Code 文档 · 提示词库
source_url: https://code.claude.com/docs/zh-CN/prompt-library
collected: 2026-10-22
media: 0
---

# 会议记录转待办工单

> 开完会不用再手动整理纪要：把会议记录交给 Claude Code，它挑出行动项，直接在任务工具里逐条建好工单，你只需审工单。`{input}` 换成你的会议记录文件，`{tracker}` 换成你用的任务工具（官方页面注明：需先把任务工具接入 Claude Code）。

## Prompt 原文

**官方中文版**

```text
阅读 {input} 并整理出行动项，然后在{tracker}中为每一项创建一个包含验收标准的工单
```

**英文原版**

```text
read {input} and write up the action items, then create a ticket in {tracker} for each one, with acceptance criteria
```

**填好的示例（官方页面的默认填法）**

```text
阅读 @meeting-notes.md 并整理出行动项，然后在我们的问题跟踪器中为每一项创建一个包含验收标准的工单
```

## 来源

- 出处：[Anthropic · Claude Code 文档 · 提示词库](https://code.claude.com/docs/zh-CN/prompt-library)（[英文原页](https://code.claude.com/docs/en/prompt-library)），卡片「将会议转化为工单 / Turn a meeting into tickets」
- 卡片标注的原始出处：[How Anthropic teams use Claude Code](https://claude.com/resources/articles/how-anthropic-teams-use-claude-code)
- 官方说明「为什么这样做有效」：省去整理文字稿这一步。Claude 会从非结构化输入中提取行动项，并通过 MCP 直接写入您的跟踪器，因此您审查的是工单，而不是文字稿。
- 版权：原文版权归 Anthropic，此处原样摘录并注明出处
- 收录：2026-10-22
