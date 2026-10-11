#!/usr/bin/env python3
"""把竞品档案 CSV 渲染成 md 表格，供报告正文直接使用。

用法：
  python3 render_table.py <40-dossier/价格.csv> [--cols 列1,列2,...] [--rows 产品A,产品B]

CSV 约定（字段定义见 assets/dossier-fields.md）：
- 第一行是表头，必须有「来源」列，填编号，多个用分号：171;2
- 查不到的格写「未查到（试过：X、Y）」，不留空
- 渲染时「来源」列变成 [171,2]（合并写，避免两个方括号相邻被当成 Markdown 链接）；「日期」列保留

校验：空格子、缺来源的行会报错并退出 1——表里的每个数字和正文一样要可追溯。
"""
import csv
import sys
from pathlib import Path


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    p = Path(a[0])
    rows = list(csv.DictReader(p.open(encoding="utf-8-sig")))
    if not rows:
        print(f"空表：{p}")
        return 1
    header = list(rows[0].keys())
    if "来源" not in header:
        print("缺少「来源」列")
        return 1
    cols = a[a.index("--cols") + 1].split(",") if "--cols" in a else header
    keep = set(a[a.index("--rows") + 1].split(",")) if "--rows" in a else None
    errs = []
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for i, r in enumerate(rows, 2):
        if keep and r[header[0]] not in keep:
            continue
        cells = []
        for c in cols:
            v = (r.get(c) or "").strip()
            if not v:
                errs.append(f"第 {i} 行「{c}」为空")
            if c == "来源":
                nums = [x.strip() for x in v.replace("，", ";").replace(",", ";").split(";") if x.strip()]
                if not nums or not all(x.isdigit() for x in nums):
                    errs.append(f"第 {i} 行来源不是编号：{v!r}")
                v = "[" + ",".join(nums) + "]"
            cells.append(v.replace("|", "｜"))
        out.append("| " + " | ".join(cells) + " |")
    if errs:
        for e in errs:
            print("错误：" + e)
        return 1
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
