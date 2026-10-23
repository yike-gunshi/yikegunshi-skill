---
title: 照以往范文起草新文档
summary: 给 Claude Code 指一个放着以往成品的文件夹，让它学会结构和语气，再照样起草一份新文档
category: writing
tags: [仿写, 文档起草, 写作风格, Claude Code]
model: Claude Code
source_name: Anthropic · Claude Code 文档 · 提示词库
source_url: https://code.claude.com/docs/zh-CN/prompt-library
collected: 2026-10-22
media: 0
---

# 照以往范文起草新文档

> 不用费劲描述自己的写作风格，直接让 Claude Code 读你以前写好的同类文档，初稿就像出自你手。`{folder}` 换成范文所在文件夹，`{examples}` 换成文档类型，`{topic}` 换成这次要写的主题。

## Prompt 原文

**官方中文版**

```text
阅读 {folder} 中的{examples}以学习其结构和语气，然后为{topic}起草一份新的
```

**英文原版**

```text
read the {examples} in {folder} to learn the structure and voice, then draft a new one for {topic}
```

**填好的示例（官方页面的默认填法）**

```text
阅读 legal/pia/ 中的隐私影响评估以学习其结构和语气，然后为新的分析集成起草一份新的
```

## 来源

- 出处：[Anthropic · Claude Code 文档 · 提示词库](https://code.claude.com/docs/zh-CN/prompt-library)（[英文原页](https://code.claude.com/docs/en/prompt-library)），卡片「根据以往示例起草文档 / Draft a document from past examples」
- 卡片标注的原始出处：[How Anthropic uses Claude in Legal](https://claude.com/resources/articles/how-anthropic-uses-claude-legal)
- 官方说明「为什么这样做有效」：指向存放已完成工作的文件夹，而不是描述您的风格。Claude 会从您已经发布的内容中学习结构和语气，因此初稿读起来就像出自您之手。
- 版权：原文版权归 Anthropic，此处原样摘录并注明出处
- 收录：2026-10-22
