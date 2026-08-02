#!/usr/bin/env python3
"""思维导图 bullet 真源的结构 lint（v2）

真源格式：`- ` 行为图面节点，节点行后的 `> ` 行为 notes（不检查）。
检查项：图面节点有效长度 5-18（中文字符记 1、英文单词记 1；根节点豁免）、
分支数（浅层 <=8、深层 <=5）、层深 <=4、句末标点
用法: python3 mindmap-lint.py file.md
"""
import re
import sys

MAX_DEPTH = 4
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

problems = []
for i, (depth, text) in enumerate(nodes):
    children = 0
    for d, _ in nodes[i + 1:]:
        if d <= depth:
            break
        if d == depth + 1:
            children += 1
    label = text[:24]
    max_children = 8 if depth <= 1 else 5
    if depth > MAX_DEPTH:
        problems.append(f"层深 {depth} 超过 {MAX_DEPTH}: {label}")
    if text[-1] in END_PUNCT:
        problems.append(f"句末标点: {label}")
    if children > max_children:
        problems.append(f"分支数 {children} 超过 {max_children}: {label}")
    if depth >= 1:
        n = effective_len(text)
        if n < LEN_RANGE[0] or n > LEN_RANGE[1]:
            problems.append(f"有效长度 {n} 超出 {LEN_RANGE}: {label}")

print(f"图面节点数 {len(nodes)}")
if problems:
    print(f"未通过 {len(problems)} 项:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("全部通过")
