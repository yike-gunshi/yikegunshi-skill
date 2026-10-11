#!/usr/bin/env python3
"""覆盖率门禁：对照信息需求清单，统计研究笔记是否「够了」。

用法：
  python3 coverage_report.py <research_notes/课题目录>

输入：
  02-needs.json  信息需求清单，S2 由协调者写：
    [{"id": "N1", "module": "用户", "need": "中国用户画像", "market": "中国",
      "min_sources": 2, "min_families": 2, "note": "样本 ≥500 的调查"}]
    可选 min_findings：按条目数计的门槛。用户原声这类需求用它（一个评论页可有多条原话，按网页数会低估）。
  1*.md          研究员笔记。Cited Findings 每条行首用 {N1} 或 {N1,N4-中国} 标注它服务哪个需求（编号可带市场后缀）。

输出：
  25-coverage.md 每个需求的来源数、独立证据族数、最新日期、是否达标，以及未达标清单。
  退出码：全部达标 0；有未达标 1（协调者据此派定向补研）。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_source_table import URL_RE, DATE_RE, normalize, family_of  # noqa: E402
from urllib.parse import urlsplit  # noqa: E402

# 只有搜索摘要、没读原文的条目不算证据（研究员规程：摘要只用来找原文）
WEAK_MARKS = ("仅见搜索摘要", "仅搜索摘要", "未读原文", "搜索摘要")
TAG_RE = re.compile(r"\{(N\d+(?:-[^,}\s]+)?(?:\s*,\s*N\d+(?:-[^,}\s]+)?)*)\}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    d = Path(sys.argv[1])
    needs_path = d / "02-needs.json"
    if not needs_path.exists():
        print(f"缺少 {needs_path}，先在 S2 写信息需求清单")
        return 2
    needs = json.loads(needs_path.read_text(encoding="utf-8"))
    stats = {n["id"]: {"urls": set(), "families": set(), "dates": [], "lines": 0} for n in needs}
    untagged = 0
    weak = 0
    for md in sorted(d.glob("1*.md")):
        in_findings = False
        for line in md.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("## "):
                in_findings = line.strip().lower().startswith("## cited findings")
                continue
            if not in_findings or not line.lstrip().startswith("-"):
                continue
            m = TAG_RE.search(line)
            if not m:
                untagged += 1
                continue
            if any(w in line for w in WEAK_MARKS):
                weak += 1
                continue
            ids = [x.strip() for x in m.group(1).split(",")]
            urls = [normalize(u) for u in URL_RE.findall(line)]
            dm = DATE_RE.findall(line)
            for nid in ids:
                if nid not in stats:
                    continue
                st = stats[nid]
                st["lines"] += 1
                for u in urls:
                    st["urls"].add(u)
                    st["families"].add(family_of(urlsplit(u).netloc))
                st["dates"] += dm

    rows = ["| 需求 | 模块 | 市场 | 条目 | 来源 | 证据族 | 最新日期 | 门槛 | 达标 |", "|---|---|---|---|---|---|---|---|---|"]
    unmet = []
    for n in needs:
        st = stats[n["id"]]
        ok = (len(st["urls"]) >= n.get("min_sources", 1) and len(st["families"]) >= n.get("min_families", 1)
              and st["lines"] >= n.get("min_findings", 0))
        latest = max((x.replace("/", "-").replace(".", "-") for x in st["dates"]), default="—")
        rows.append(
            f"| {n['id']} {n['need']} | {n.get('module', '')} | {n.get('market', '—')} | {st['lines']} | "
            f"{len(st['urls'])} | {len(st['families'])} | {latest} | "
            f"≥{n.get('min_sources', 1)} 源 / ≥{n.get('min_families', 1)} 族"
            + (f" / ≥{n['min_findings']} 条" if n.get("min_findings") else "") + f" | {'✓' if ok else '✗'} |"
        )
        if not ok:
            unmet.append(n)
    out = ["# 覆盖率报表", "",
           f"未打需求标签的 finding：{untagged} 条；只有搜索摘要的 finding：{weak} 条。两者都不计入统计。", "",
           "脚本只数数量。协调者还要抽查每个「✓」背后的条目是否满足 note 里的质量要求（样本量、时效、一手），不满足的改判为 ✗。", ""] + rows
    if unmet:
        out += ["", "## 未达标，需定向补研", ""]
        for n in unmet:
            out.append(f"- {n['id']} {n['need']}（{n.get('market', '—')}）：{n.get('note', '')}")
    (d / "25-coverage.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"需求 {len(needs)} 项，数量达标 {len(needs) - len(unmet)}，未达标 {len(unmet)}；未打标签 {untagged} 条、仅摘要 {weak} 条不计 → 25-coverage.md")
    for n in unmet:
        print(f"  ✗ {n['id']} {n['need']}")
    return 1 if unmet else 0


if __name__ == "__main__":
    sys.exit(main())
