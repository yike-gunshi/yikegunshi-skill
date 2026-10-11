#!/usr/bin/env python3
"""检查调研报告的结构、引用、可读性与图表。

用法：
  python3 check_report.py report.md [--sources sources.json]

错误（E，退出码 1）：
  E1 正文引用的 [n] 不在「口径与来源」节或 sources.json
  E2 正文出现【高】【中】【低】置信度标签
  E3 缺固定小节或顺序不对（一分钟看懂 / 一 … 八 / 附录 / 口径与来源）
  E4 表格有空格子
  E5 「一分钟看懂」不合规：要点不是 5—7 条，或有要点超 45 字、含 2 个以上数字、带引用编号
  E6 图片文件不存在
警告（W）：
  W1 正文含估算词（约 / 大约 / 估计 / 大概 / 据说）却没有来源编号
  W2 一句话里超过 2 个来源编号
  W3 正文字数（不含来源）偏离 6000—14000
  W4 「来源」节列了正文没引用的编号
  W5 过渡废话（值得注意的是 / 综上所述 / 不难看出 / 由此可见）
  W6 段落超过 120 字
  W7 连续 600 字以上没有表、图、列表或引语
  W8 截图下一行没有带来源编号的图注；数据图缺 charts/data/<同名>.json
"""
import json
import re
import sys
from pathlib import Path

CITE_RE = re.compile(r"\[(\d{1,3})\]")
TAG_RE = re.compile(r"【(高|中|低)】")
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
EST_WORDS = ("约", "大约", "估计", "大概", "据说")
FILLERS = ("值得注意的是", "综上所述", "不难看出", "由此可见")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
REQUIRED = [
    ("一分钟看懂", r"一分钟看懂"),
    ("一", r"^一[、.]"),
    ("二", r"^二[、.]"),
    ("三", r"^三[、.]"),
    ("四", r"^四[、.]"),
    ("五", r"^五[、.]"),
    ("六", r"^六[、.]"),
    ("七", r"^七[、.]"),
    ("八", r"^八[、.]"),
    ("附录", r"^附录"),
    ("口径与来源", r"来源"),
]


def zh_len(s: str) -> int:
    s = CITE_RE.sub("", s)
    return len(re.findall(r"[一-鿿]", s)) + len(re.findall(r"[A-Za-z0-9]+", s))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rp = Path(sys.argv[1])
    text = rp.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []
    warns: list[str] = []

    h2 = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith("## ")]
    pos = []
    for name, pat in REQUIRED:
        hit = next((k for k, (_, t) in enumerate(h2) if re.search(pat, t)), None)
        if hit is None:
            errors.append(f"E3 缺小节：{name}")
        pos.append(hit)
    found = [p for p in pos if p is not None]
    if found != sorted(found):
        errors.append("E3 小节顺序不对，应为 一分钟看懂 / 一 … 八 / 附录 / 口径与来源")

    src_idx = next((i for i, t in reversed(h2) if "来源" in t), len(lines))
    body = lines[:src_idx]
    body_text = "\n".join(body)

    # —— 来源 ——
    listed: set[int] = set()
    for l in lines[src_idx:]:
        m = re.match(r"^\s*(?:\[(\d{1,3})\]|(\d{1,3})[.、])\s*", l)
        if m:
            listed.add(int(m.group(1) or m.group(2)))
    known = listed
    if "--sources" in sys.argv:
        sp = Path(sys.argv[sys.argv.index("--sources") + 1])
        known = {int(s["n"]) for s in json.loads(sp.read_text(encoding="utf-8"))}
    cited = {int(n) for n in CITE_RE.findall(body_text)}
    if not listed:
        errors.append("E1 「口径与来源」节没有列出任何编号")
    if listed and (cited - listed):
        errors.append(f"E1 正文引用了来源节没列的编号: {sorted(cited - listed)}")
    if cited - known:
        errors.append(f"E1 正文编号不在 sources.json: {sorted(cited - known)}")
    if listed - cited:
        warns.append(f"W4 来源节列了正文没引用的编号: {sorted(listed - cited)}")

    for i, l in enumerate(body, 1):
        if TAG_RE.search(l):
            errors.append(f"E2 第 {i} 行有置信度标签: {l.strip()[:40]}")
        s = l.strip()
        if s.startswith("|") and not re.match(r"^\|\s*:?-", s):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if any(c == "" for c in cells[1:]):
                errors.append(f"E4 第 {i} 行表格有空格子")

    # —— 一分钟看懂 ——
    if pos[0] is not None:
        a = h2[pos[0]][0]
        b = h2[pos[0] + 1][0] if pos[0] + 1 < len(h2) else len(lines)
        items = [l.strip() for l in lines[a:b] if re.match(r"^\s*(\d+[.、]|[-*])\s+", l)]
        if not 5 <= len(items) <= 7:
            errors.append(f"E5 「一分钟看懂」要点应为 5—7 条，现为 {len(items)} 条")
        for it in items:
            t = re.sub(r"^\s*(\d+[.、]|[-*])\s+", "", it).replace("**", "")
            if CITE_RE.search(t):
                errors.append(f"E5 一分钟看懂的要点不带引用编号: {t[:30]}")
            if zh_len(t) > 45:
                errors.append(f"E5 要点超 45 字（{zh_len(t)}）: {t[:30]}")
            if len(NUM_RE.findall(t)) > 2:
                errors.append(f"E5 要点数字过多: {t[:30]}")

    # —— 句子级 ——
    for i, l in enumerate(body, 1):
        s = l.strip()
        if not s or s.startswith(("#", ">", "|", "!")):
            continue
        for sent in re.split(r"(?<=[。！？])", s):
            if any(w in sent for w in EST_WORDS) and NUM_RE.search(sent) and not CITE_RE.search(sent):
                warns.append(f"W1 第 {i} 行估算数字无来源: {sent[:40]}")
            if len(CITE_RE.findall(sent)) > 2:
                warns.append(f"W2 第 {i} 行一句超过 2 个编号: {sent[:40]}")
        for f in FILLERS:
            if f in s:
                warns.append(f"W5 第 {i} 行过渡废话「{f}」")

    # —— 段落长度与图文节奏 ——
    blocks, cur, start = [], [], 0
    for i, l in enumerate(body):
        if l.strip() == "":
            if cur:
                blocks.append((start, cur))
            cur = []
        else:
            if not cur:
                start = i
            cur.append(l)
    if cur:
        blocks.append((start, cur))
    run = 0
    for start, bl in blocks:
        first = bl[0].strip()
        nontext = first.startswith(("|", "!", ">", "-", "*", "```")) or re.match(r"^\d+[.、]\s", first)
        if first.startswith("#"):
            continue
        if nontext:
            run = 0
            continue
        n = zh_len(" ".join(bl))
        if n > 120:
            warns.append(f"W6 第 {start + 1} 行段落 {n} 字，超过 120")
        run += n
        if run > 600:
            warns.append(f"W7 第 {start + 1} 行前后连续 {run} 字没有表、图、列表或引语")
            run = 0

    # —— 图片 ——
    n_img = 0
    for i, l in enumerate(body):
        for src in IMG_RE.findall(l):
            n_img += 1
            p = (rp.parent / src).resolve()
            if not p.exists():
                errors.append(f"E6 图片不存在: {src}")
                continue
            stem = Path(src).stem
            if stem.startswith("shot-"):
                nxt = next((x for x in body[i + 1:i + 3] if x.strip()), "")
                if not CITE_RE.search(nxt):
                    warns.append(f"W8 截图 {src} 下一行缺带编号的图注")
            elif not (p.parent / "data" / f"{stem}.json").exists() and not (p.parent / f"{stem}.mmd").exists():
                warns.append(f"W8 图 {src} 没有对应的 data/{stem}.json 或 {stem}.mmd")

    n_tab = sum(1 for k, l in enumerate(body) if l.strip().startswith("|") and (k == 0 or not body[k - 1].strip().startswith("|")))
    chars = zh_len(body_text)
    if chars < 6000 or chars > 14000:
        warns.append(f"W3 正文约 {chars} 字，目标 8000—12000")

    for e in errors:
        print(e)
    for w in warns:
        print(w)
    print(f"— 错误 {len(errors)}，警告 {len(warns)}，正文 {chars} 字，图 {n_img} 张，表 {n_tab} 张，引用编号 {len(cited)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
