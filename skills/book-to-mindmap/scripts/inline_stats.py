#!/usr/bin/env python3
"""统计节点内灰字（notes 第一段）的长度分布

和 md2xmind 用同一套切分逻辑，所以这里报的数字就是导图里实际显示的文字。
自己凭印象数或者只数第一行，都会得出偏小的结果——首段可能跨多行。

用法: python3 inline_stats.py 真源.md [更多文件...]
"""
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md2xmind import parse_bullets, split_notes, plain  # noqa: E402

LIMIT = 75   # 超过这个长度节点会明显变高


def walk(node, out):
    if node.get("notes"):
        inline, _ = split_notes(node["notes"])
        if inline:
            out.append((plain(node["title"]), len(plain(inline))))
    for c in node["children"]:
        walk(c, out)


def stats(path):
    tree = parse_bullets(open(path, encoding="utf-8").read())
    items = []
    walk(tree, items)
    if not items:
        return None
    lens = [n for _, n in items]
    over = [(t, n) for t, n in items if n > LIMIT]
    return {"条数": len(lens), "中位": statistics.median(lens),
            "最长": max(lens), "超标": over}


if __name__ == "__main__":
    for path in sys.argv[1:]:
        s = stats(path)
        name = os.path.basename(path)
        if not s:
            print(f"{name}: 没有带解释的节点")
            continue
        flag = "" if not s["超标"] else f"  ← 有 {len(s['超标'])} 条要拆"
        print(f"{name}")
        print(f"  {s['条数']} 条解释，中位 {s['中位']:.0f} 字，最长 {s['最长']} 字{flag}")
        for t, n in sorted(s["超标"], key=lambda x: -x[1])[:5]:
            print(f"    {n:4} 字  {t[:30]}")
        if len(s["超标"]) > 5:
            print(f"    …… 另有 {len(s['超标']) - 5} 条")
