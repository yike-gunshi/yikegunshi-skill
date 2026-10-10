#!/usr/bin/env python3
"""合并研究笔记中的来源：去重、编号、按域名初分 evidence family。

用法：
  python3 build_source_table.py <research_notes/课题目录> [--existing sources.json]

输出到同一目录：sources.json 与 sources.md。
--existing 保留旧编号（续查时不打乱正文引用），新来源接着编号。
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s<>()\[\]\"'`）】」，、；：]+")
MD_LINK_RE = re.compile(r"\[([^\]]{1,200})\]\((https?://[^)\s]+)\)")
# 研究员常用格式：标题（URL ，日期）或 标题 (URL, date)，括号全角半角都认
PAREN_CITE_RE = re.compile(
    r"([^（(\[\]—；;、]{2,160}?)\s*[（(]\s*(https?://[^\s）),，]+)\s*(?:[，,]\s*([^）)]{0,40}))?\s*[）)]"
)
DATE_RE = re.compile(r"(20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2})?日?)")
MULTI_LABEL_TLDS = {"com.cn", "net.cn", "org.cn", "gov.cn", "co.uk", "co.jp", "com.au", "com.hk", "com.tw", "co.kr"}
FIRST_PARTY_HINTS = ("github.com", "apps.apple.com", "play.google.com", "producthunt.com")
COMMUNITY_HINTS = ("reddit.com", "x.com", "twitter.com", "xiaohongshu.com", "weibo.com", "v2ex.com", "news.ycombinator.com", "zhihu.com")
REPORT_HINTS = ("iresearch", "analysys", "qianzhan", "questmobile", "statista", "gartner", "forrester", "mckinsey", "a16z", "sensortower", "similarweb", "ibisworld")


def normalize(url: str) -> str:
    url = url.rstrip(".,;:。，；：")
    parts = urlsplit(url)
    query = "&".join(q for q in parts.query.split("&") if q and not q.lower().startswith(("utm_", "ref=", "spm=", "from=")))
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/"), query, ""))


def family_of(host: str) -> str:
    labels = host.split(":")[0].split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_LABEL_TLDS:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def guess_type(host: str) -> str:
    if any(h in host for h in COMMUNITY_HINTS):
        return "社区原帖"
    if any(h in host for h in REPORT_HINTS):
        return "研报"
    if any(h in host for h in FIRST_PARTY_HINTS):
        return "一方"
    return "待定（一方/媒体）"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    notes_dir = Path(sys.argv[1])
    existing_path = None
    if "--existing" in sys.argv:
        existing_path = Path(sys.argv[sys.argv.index("--existing") + 1])
    if not notes_dir.is_dir():
        print(f"目录不存在: {notes_dir}")
        return 2

    sources: dict[str, dict] = {}
    if existing_path and existing_path.exists():
        for item in json.loads(existing_path.read_text(encoding="utf-8")):
            sources[item["url"]] = item

    next_n = max([s["n"] for s in sources.values()], default=0) + 1
    for md in sorted(notes_dir.glob("*.md")):
        if md.name in ("report.md", "sources.md"):
            continue
        for line in md.read_text(encoding="utf-8", errors="replace").splitlines():
            titles = {normalize(u): t.strip() for t, u in MD_LINK_RE.findall(line)}
            dates: dict[str, str] = {}
            for t, u, d in PAREN_CITE_RE.findall(line):
                key = normalize(u)
                t = re.sub(r"^.*[—]\s*", "", t).strip(" -—:：")
                titles.setdefault(key, t)
                if d:
                    dm = DATE_RE.search(d)
                    dates[key] = dm.group(1) if dm else d.strip()
            date_m = DATE_RE.search(line)
            for m in URL_RE.finditer(line):
                raw = m.group(0)
                url = normalize(raw)
                if url not in titles:
                    # 兜底：取 URL 前最后一个“—”之后、到 URL 为止的文字作标题
                    before = line[: m.start()]
                    seg = before.rsplit("—", 1)[-1] if "—" in before else before.rsplit("-", 1)[-1]
                    seg = re.sub(r"[（(]\s*$", "", seg)
                    seg = re.sub(r"[（(][^（()）]*[）)]", lambda mm: mm.group(0), seg)
                    seg = seg.strip(" 　:：,，;；、\t")
                    if 2 <= len(seg) <= 160 and not seg.startswith(("http", "- ")):
                        titles[url] = seg
                if url not in dates:
                    after = line[m.end(): m.end() + 60]
                    dm = DATE_RE.search(after.split("）")[0].split(")")[0])
                    if dm:
                        dates[url] = dm.group(1)
                if url in sources:
                    sources[url]["cited_in"].append(md.name)
                    if not sources[url]["title"] and titles.get(url):
                        sources[url]["title"] = titles[url]
                    if not sources[url]["date"] and dates.get(url):
                        sources[url]["date"] = dates[url]
                    continue
                host = urlsplit(url).netloc
                sources[url] = {
                    "n": next_n,
                    "title": titles.get(url, ""),
                    "url": url,
                    "date": dates.get(url) or (date_m.group(1) if date_m else ""),
                    "type": guess_type(host),
                    "family": family_of(host),
                    "cited_in": [md.name],
                }
                next_n += 1

    items = sorted(sources.values(), key=lambda s: s["n"])
    for s in items:
        s["cited_in"] = sorted(set(s["cited_in"]))
        # 标题清理：去掉夹带的 URL 与残缺括号
        t = re.sub(r"[（(]?\s*https?://\S+", "", s["title"])
        t = t.strip(" 　（()）:：,，;；、")
        s["title"] = t
    (notes_dir / "sources.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["| 编号 | 标题 | URL | 日期 | 类型 | family |", "|---|---|---|---|---|---|"]
    for s in items:
        lines.append(f"| {s['n']} | {s['title'] or '（待填）'} | {s['url']} | {s['date'] or '（待填）'} | {s['type']} | {s['family']} |")
    (notes_dir / "sources.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    families = {}
    for s in items:
        families.setdefault(s["family"], []).append(s["n"])
    multi = {f: ns for f, ns in families.items() if len(ns) > 1}
    print(f"来源 {len(items)} 条，family {len(families)} 个，写入 {notes_dir / 'sources.json'} 与 sources.md")
    if multi:
        print("同 family 多来源（验证者按内容确认是否转引同源）：")
        for f, ns in multi.items():
            print(f"  {f}: {ns}")
    blank = [s["n"] for s in items if not s["title"] or not s["date"]]
    if blank:
        print(f"标题或日期待填的编号: {blank}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
