#!/usr/bin/env python3
"""检查调研报告的引用完整性与结构。

用法：
  python3 check_report.py report.md [--sources sources.json]

检查项（E = 错误，退出码 1；W = 警告）：
  E1 正文引用的 [n] 不在来源表 / sources.json
  E2 「核心结论」每条缺【高/中/低】标签或缺 [n]
  E3 缺「存疑 / 待查」一节，或该节为空
  E4 「对比矩阵」有空格子
  E5 「结论速览」缺一句话结论或观察条目
  W1 核心结论 / 矩阵 / 结论速览里出现估算词（约、大约、估计、大概、据说、或许）
  W2 流量 / 收入类数字标了【高】（封顶规则）
  W3 来源表里有编号从未被正文引用
"""
import json
import re
import sys
from pathlib import Path

CITE_RE = re.compile(r"\[(\d{1,3})\]")
CONF_RE = re.compile(r"【(高|中|低)】")
EST_WORDS = ("约", "大约", "估计", "大概", "据说", "或许")
CAP_WORDS = ("流量", "访问量", "下载量", "月活", "日活", "收入", "营收", "付费率", "ARPU")
SECTION_RE = re.compile(r"^#{1,3}\s+(.*)$")


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "_head"
    sections[current] = []
    for line in text.splitlines():
        m = SECTION_RE.match(line)
        if m:
            current = m.group(1).strip()
            sections[current] = []
        else:
            sections[current].append(line)
    return sections


def find_section(sections: dict[str, list[str]], *keys: str) -> list[str] | None:
    for name, body in sections.items():
        if any(k in name for k in keys):
            return body
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    report = Path(sys.argv[1])
    text = report.read_text(encoding="utf-8")
    sections = split_sections(text)
    errors: list[str] = []
    warns: list[str] = []

    source_ids: set[int] = set()
    if "--sources" in sys.argv:
        sp = Path(sys.argv[sys.argv.index("--sources") + 1])
        source_ids |= {int(s["n"]) for s in json.loads(sp.read_text(encoding="utf-8"))}
    table = find_section(sections, "来源表")
    if table:
        for line in table:
            m = re.match(r"^\|\s*(\d{1,3})\s*\|", line)
            if m:
                source_ids.add(int(m.group(1)))
    if not source_ids:
        errors.append("E1 找不到来源表（## 来源表）也没有 --sources")

    body_wo_appendix = "\n".join(
        "\n".join(body) for name, body in sections.items() if "来源表" not in name
    )
    cited = {int(n) for n in CITE_RE.findall(body_wo_appendix)}
    missing = sorted(cited - source_ids) if source_ids else []
    if missing:
        errors.append(f"E1 正文引用了来源表里没有的编号: {missing}")
    unused = sorted(source_ids - cited)
    if unused:
        warns.append(f"W3 来源表编号从未被正文引用: {unused}")

    core = find_section(sections, "核心结论")
    if core is None:
        errors.append("E2 缺「核心结论」一节")
    else:
        for line in core:
            s = line.strip()
            if re.match(r"^(\d+\.|-|\*)\s+", s):
                if not CONF_RE.search(s):
                    errors.append(f"E2 核心结论缺置信度: {s[:60]}")
                if not CITE_RE.search(s):
                    errors.append(f"E2 核心结论缺来源编号: {s[:60]}")

    doubts = find_section(sections, "存疑")
    if doubts is None:
        errors.append("E3 缺「存疑 / 待查」一节")
    elif not any(l.strip() and not l.strip().startswith("|---") and l.strip() not in ("| 想查什么 | 查了哪些渠道 | 为什么没有 | 接什么能补 |",) for l in doubts):
        errors.append("E3 「存疑 / 待查」为空（无缺口要写'本次无'并说明理由）")

    matrix = find_section(sections, "对比矩阵", "维度事实表")
    if matrix:
        for line in matrix:
            if line.startswith("|") and not re.match(r"^\|\s*-", line):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) > 1 and any(c == "" for c in cells[1:]):
                    errors.append(f"E4 矩阵有空格子: {line.strip()[:80]}")

    summary = find_section(sections, "结论速览")
    if summary is None:
        errors.append("E5 缺「结论速览」一节")
    else:
        joined = "\n".join(summary)
        if "一句话结论" not in joined:
            errors.append("E5 结论速览缺「一句话结论」")
        if not any(re.match(r"^\s*-\s+", l) for l in summary):
            errors.append("E5 结论速览缺观察条目")

    for name in ("结论速览", "核心结论", "对比矩阵", "维度事实表"):
        body = find_section(sections, name)
        if not body:
            continue
        for line in body:
            s = line.strip()
            if not s or s.startswith("|---"):
                continue
            if any(w in s for w in EST_WORDS) and not CITE_RE.search(s):
                warns.append(f"W1 {name} 含估算词且无来源: {s[:60]}")
            if "【高】" in s and any(w in s for w in CAP_WORDS):
                warns.append(f"W2 {name} 流量/收入类数字标了【高】（封顶中，除非一方披露）: {s[:60]}")

    for e in errors:
        print("E", e)
    for w in warns:
        print("W", w)
    print(f"— 错误 {len(errors)}，警告 {len(warns)}，引用编号 {len(cited)}，来源 {len(source_ids)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
