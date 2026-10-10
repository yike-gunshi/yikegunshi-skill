#!/usr/bin/env python3
"""检查调研报告的结构、引用与可读性。

用法：
  python3 check_report.py report.md [--sources sources.json]

错误（E，退出码 1）：
  E1 正文引用的 [n] 不在「来源」节或 sources.json
  E2 正文出现【高】【中】【低】置信度标签
  E3 缺固定小节或顺序不对（导语 / 一 … 八 / 口径与来源）
  E4 表格有空格子
  E5 「导语」没有 2—4 个编号问题
警告（W）：
  W1 正文含估算词（约 / 大约 / 估计 / 大概 / 据说）却没有来源编号
  W2 一句话里超过 2 个来源编号
  W3 正文字数（不含来源）偏离 8000—12000 字太多（<6000 或 >14000）
  W4 「来源」节列了正文没引用的编号
  W5 正文出现过渡废话（值得注意的是 / 综上所述 / 不难看出 / 由此可见）
"""
import json
import re
import sys
from pathlib import Path

CITE_RE = re.compile(r"\[(\d{1,3})\]")
TAG_RE = re.compile(r"【(高|中|低)】")
EST_WORDS = ("约", "大约", "估计", "大概", "据说")
FILLERS = ("值得注意的是", "综上所述", "不难看出", "由此可见")
REQUIRED = [
    ("导语", r"^导语"),
    ("一", r"^一[、.]"),
    ("二", r"^二[、.]"),
    ("三", r"^三[、.]"),
    ("四", r"^四[、.]"),
    ("五", r"^五[、.]"),
    ("六", r"^六[、.]"),
    ("七", r"^七[、.]"),
    ("八", r"^八[、.]"),
    ("口径与来源", r"来源"),
]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []
    warns: list[str] = []

    # 切分二级标题
    h2 = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith("## ")]
    pos = []
    for name, pat in REQUIRED:
        hit = next((i for i, (_, t) in enumerate(h2) if re.search(pat, t)), None)
        if hit is None:
            errors.append(f"E3 缺小节：{name}")
        pos.append(hit)
    found = [p for p in pos if p is not None]
    if found != sorted(found):
        errors.append("E3 小节顺序不对，应为 导语 / 一 … 八 / 口径与来源")

    src_idx = next((i for i, t in h2 if "来源" in t), len(lines))
    body = lines[:src_idx]
    src_lines = lines[src_idx:]
    body_text = "\n".join(body)

    # 来源编号
    listed: set[int] = set()
    for l in src_lines:
        m = re.match(r"^\s*(?:\[(\d{1,3})\]|(\d{1,3})[.、])\s*", l)
        if m:
            listed.add(int(m.group(1) or m.group(2)))
    if "--sources" in sys.argv:
        sp = Path(sys.argv[sys.argv.index("--sources") + 1])
        known = {int(s["n"]) for s in json.loads(sp.read_text(encoding="utf-8"))}
    else:
        known = listed
    cited = {int(n) for n in CITE_RE.findall(body_text)}
    if not listed:
        errors.append("E1 「来源」节没有列出任何编号")
    missing = sorted(cited - listed) if listed else []
    if missing:
        errors.append(f"E1 正文引用了「来源」节没列的编号: {missing}")
    unknown = sorted(cited - known)
    if unknown:
        errors.append(f"E1 正文编号不在 sources.json: {unknown}")
    extra = sorted(listed - cited)
    if extra:
        warns.append(f"W4 「来源」节列了正文没引用的编号: {extra}")

    for i, l in enumerate(body, 1):
        if TAG_RE.search(l):
            errors.append(f"E2 第 {i} 行有置信度标签: {l.strip()[:50]}")

    for i, l in enumerate(body, 1):
        s = l.strip()
        if s.startswith("|") and not re.match(r"^\|\s*:?-", s) and not re.match(r"^\|\s*\|", s):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if any(c == "" for c in cells[1:]):
                errors.append(f"E4 第 {i} 行表格有空格子")

    # 导语问题数
    if pos[0] is not None:
        start = h2[pos[0]][0]
        end = h2[pos[0] + 1][0] if pos[0] + 1 < len(h2) else len(lines)
        items = [l for l in lines[start:end] if re.match(r"^\s*\d+[.、]\s+", l)]
        if not 2 <= len(items) <= 4:
            errors.append(f"E5 「导语」应列 2—4 个问题，现为 {len(items)} 个")

    for i, l in enumerate(body, 1):
        s = l.strip()
        if not s or s.startswith(("#", ">", "|")):
            continue
        for sent in re.split(r"(?<=[。！？])", s):
            if any(w in sent for w in EST_WORDS) and not CITE_RE.search(sent):
                if re.search(r"\d", sent):
                    warns.append(f"W1 第 {i} 行估算数字无来源: {sent[:50]}")
            if len(CITE_RE.findall(sent)) > 2:
                warns.append(f"W2 第 {i} 行一句超过 2 个编号: {sent[:50]}")
        for f in FILLERS:
            if f in s:
                warns.append(f"W5 第 {i} 行过渡废话「{f}」")

    chars = len(re.findall(r"[一-鿿]", body_text)) + len(re.findall(r"[A-Za-z0-9]+", body_text))
    if chars < 6000 or chars > 14000:
        warns.append(f"W3 正文约 {chars} 字，目标 8000—12000")

    for e in errors:
        print(e)
    for w in warns:
        print(w)
    print(f"— 错误 {len(errors)}，警告 {len(warns)}，正文 {chars} 字，引用编号 {len(cited)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
