#!/usr/bin/env python3
"""思维导图 bullet 真源的结构检查

真源格式：`- ` 行是导图上看得见的节点，紧跟其后的 `> ` 行是该节点的 notes（不检查）。

硬检查（不通过就退出码 1）：
  节点文字长度 5-18（中文字符记 1、英文单词记 1；根节点豁免）、句末标点

提示（只打印，不影响退出码）：
  层深超过 4、同级子节点超过 7——这两项是经验值不是规矩，内容本身要求更宽更深时
  就该更宽更深，看到提示确认一下是内容需要还是自己没分好组即可。

用法: python3 mindmap-lint.py file.md
"""
import re
import sys

DEPTH_HINT = 4
CHILDREN_HINT = 7
LEN_RANGE = (5, 18)
END_PUNCT = "。；，！？.;,!?"


def effective_len(text):
    ascii_words = len(re.findall(r"[A-Za-z0-9_/^|.+-]+", text))
    cjk_chars = len(re.findall(r"[^\x00-\x7f]", text))
    return ascii_words + cjk_chars


nodes = []
for line in open(sys.argv[1], encoding="utf-8"):
    m = re.match(r"^(\s*)-\s+(.*\S)\s*$", line)
    if m:
        nodes.append((len(m.group(1)) // 2, m.group(2)))

problems, hints = [], []
for i, (depth, text) in enumerate(nodes):
    children = 0
    for d, _ in nodes[i + 1:]:
        if d <= depth:
            break
        if d == depth + 1:
            children += 1
    label = text[:24]
    if text[-1] in END_PUNCT:
        problems.append(f"句末标点: {label}")
    if depth >= 1:
        n = effective_len(text)
        if n < LEN_RANGE[0] or n > LEN_RANGE[1]:
            problems.append(f"长度 {n} 超出 {LEN_RANGE}: {label}")
    if depth > DEPTH_HINT:
        hints.append(f"第 {depth} 层，比常见的 {DEPTH_HINT} 层深: {label}")
    if children > CHILDREN_HINT:
        hints.append(f"{children} 个子节点，比常见的 {CHILDREN_HINT} 个多: {label}")

print(f"节点数 {len(nodes)}")
for h in hints:
    print("  提示:", h)
if problems:
    print(f"未通过 {len(problems)} 项:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("检查通过")
