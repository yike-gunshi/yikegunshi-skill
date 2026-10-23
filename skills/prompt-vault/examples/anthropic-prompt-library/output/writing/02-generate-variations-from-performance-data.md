---
title: 按效果数据重写广告标题
summary: 让 Claude Code 读投放效果数据，找出表现差的标题，按字数上限批量生成替换版本
category: writing
tags: [广告文案, 标题, 数据驱动, 营销, Claude Code]
model: Claude Code
source_name: Anthropic · Claude Code 文档 · 提示词库
source_url: https://code.claude.com/docs/zh-CN/prompt-library
collected: 2026-10-22
media: 0
---

# 按效果数据重写广告标题

> 先看数据再改文案：Claude Code 读取效果表，挑出该换的标题，一次生成一批不超字数的新版本。把数据文件拖进输入框或换成你自己的 `@文件`，`{items}` 也可以换成广告正文、按钮文字等其他内容，`{n}` 和 `{limit}` 填你要的数量和字数上限。

## Prompt 原文

**官方中文版**

```text
读取 {file}，找出表现不佳的{items}，并生成 {n} 个不超过 {limit} 个字符的新变体
```

**英文原版**

```text
read {file}, find the underperforming {items}, and generate {n} new variations that stay under {limit} characters
```

**填好的示例（官方页面的默认填法）**

```text
读取 @ads-performance.csv，找出表现不佳的标题，并生成 20 个不超过 90 个字符的新变体
```

## 来源

- 出处：[Anthropic · Claude Code 文档 · 提示词库](https://code.claude.com/docs/zh-CN/prompt-library)（[英文原页](https://code.claude.com/docs/en/prompt-library)），卡片「根据效果数据生成变体 / Generate variations from performance data」
- 卡片标注的原始出处：[How Anthropic teams use Claude Code](https://claude.com/resources/articles/how-anthropic-teams-use-claude-code)
- 官方说明「为什么这样做有效」：在一开始就说明约束，让生成内容不超出限制。Claude 会读取指标，挑选需要替换的内容，并生成符合要求的替代方案。
- 版权：原文版权归 Anthropic，此处原样摘录并注明出处
- 收录：2026-10-22
