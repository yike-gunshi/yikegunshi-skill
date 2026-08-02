#!/usr/bin/env python3
"""思维导图 bullet 真源的结构检查

真源格式：`- ` 行是导图上看得见的节点，紧跟其后的 `> ` 行是该节点的 notes（不检查）。

硬检查（不通过就退出码 1）：
  节点文字长度 5-18（中文字符记 1、英文单词记 1；根节点豁免）、句末标点

提示（只打印，不影响退出码）：
  层深、同级子节点数——经验值不是规矩，内容要求更宽更深时就该更宽更深
  过度分析——大量只带一个子节点的父节点，说明为了让层级"看起来完整"硬加了中间层，
    该合并。判据来自芝加哥格式手册的索引编辑清单
  模板腔——同一层兄弟节点句式雷同。规则被执行成模板是模型通病，读起来像机器生成

用法: python3 mindmap-lint.py file.md
"""
import re
import sys
from collections import Counter, defaultdict

DEPTH_HINT = 4
CHILDREN_HINT = 7
LEN_RANGE = (5, 18)
END_PUNCT = "。；，！？.;,!?"
LONELY_RATIO = 0.2   # 只带一个子节点的父节点占比超过此值即过度分析
SAME_STYLE_RATIO = 0.6   # 同层兄弟中句式雷同的占比超过此值即模板腔
# 这些前缀有语义职责（标记行动、标记顺序），重复出现是对的，不算模板腔
ROLE_PREFIX = ("做法：", "第")


def strip_attrs(text):
    """去掉行尾的 @标记 和 §标签、以及加粗记号——它们都不占节点标题的长度"""
    text = re.sub(r"(\s+[@§][^\s@§]+)+$", "", text)
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


def effective_len(text):
    text = strip_attrs(text)
    ascii_words = len(re.findall(r"[A-Za-z0-9_/^|.+-]+", text))
    cjk_chars = len(re.findall(r"[^\x00-\x7f]", text))
    return ascii_words + cjk_chars


def style_key(text):
    """把节点归纳成一个句式特征，用来找雷同"""
    if text.startswith(ROLE_PREFIX):
        return None
    m = re.match(r"^(.{1,6}?)[：:]", text)
    if m:
        return f"前{len(m.group(1))}字加冒号"
    return None


nodes = []
for line in open(sys.argv[1], encoding="utf-8"):
    m = re.match(r"^(\s*)-\s+(.*\S)\s*$", line)
    if m:
        nodes.append((len(m.group(1)) // 2, m.group(2)))

problems, hints = [], []
parents = 0
lonely = []
siblings = defaultdict(list)   # (父节点下标) -> [子节点文字]

for i, (depth, text) in enumerate(nodes):
    children = []
    for j in range(i + 1, len(nodes)):
        d, t = nodes[j]
        if d <= depth:
            break
        if d == depth + 1:
            children.append(t)
    label = text[:24]

    if text[-1] in END_PUNCT:
        problems.append(f"句末标点: {label}")
    if depth >= 1:
        n = effective_len(text)
        if n < LEN_RANGE[0] or n > LEN_RANGE[1]:
            problems.append(f"长度 {n} 超出 {LEN_RANGE}: {label}")
    if depth > DEPTH_HINT:
        hints.append(f"第 {depth} 层，比常见的 {DEPTH_HINT} 层深: {label}")
    if len(children) > CHILDREN_HINT:
        hints.append(f"{len(children)} 个子节点，比常见的 {CHILDREN_HINT} 个多: {label}")

    if children:
        parents += 1
        if len(children) == 1:
            lonely.append(label)
        siblings[i] = children

if parents:
    ratio = len(lonely) / parents
    if ratio > LONELY_RATIO:
        hints.append(
            f"过度分析：{len(lonely)}/{parents} 个父节点只带一个子节点（{ratio:.0%}），"
            f"这类中间层多半可以合并，例如「{lonely[0]}」")

for children in siblings.values():
    if len(children) < 3:
        continue
    keys = [k for k in (style_key(c) for c in children) if k]
    if not keys:
        continue
    key, n = Counter(keys).most_common(1)[0]
    if n / len(children) > SAME_STYLE_RATIO and n >= 3:
        hints.append(
            f"模板腔：{n}/{len(children)} 个兄弟节点都是「{key}」的写法，"
            f"改掉一半，例如「{children[0][:20]}」")

print(f"节点数 {len(nodes)}")
for h in hints:
    print("  提示:", h)
if problems:
    print(f"未通过 {len(problems)} 项:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("检查通过")
