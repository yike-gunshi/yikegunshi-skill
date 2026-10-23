#!/usr/bin/env python3
"""基线对照第三步：把评委的逐条判断按考点表公式算成分数。

- K1–K7、K9 由评委判断算出；每份纪要有多次评委采样，每条考点取中位数
- K8（骨架）由本脚本直接读纪要文本判断

输出:
  <out>/<arm>.json      score_rubric.py 能读的格式
  <out>/逐条明细.json    每份纪要在每个标准答案条目上的判断（多次采样取多数）

用法:
  python3 score.py --gen ../基线对照/生成 --judge ../基线对照/评委 \
      --key ../标准答案.json --out ../基线对照/分数
"""

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

SEC = {
    "concl": re.compile(r"结论|决定|决议|已定|定了什么"),
    "todo": re.compile(r"待办|行动项|action|todo|分工|任务", re.I),
    "open": re.compile(r"谈拢|未决|待决|未达成|遗留|待定|未定|分歧|开放问题|悬而未决|待讨论|待明确|待拍板"),  # 首版漏了"未谈拢"，把不用 Skill 组的正常标题误判成缺块
    "replay": re.compile(r"讨论过程|会议内容|讨论内容|议题详情|发言|会议过程|讨论记录"),
}
HEADER_LINE = re.compile(r"^\s*(#{1,6}\s+.+|[一二三四五六七八九十]+[、.．].+|【[^】]+】\s*$|\*\*[^*]+\*\*\s*[:：]?\s*$)")
DATE = re.compile(r"(2026[-/.年]\s*10|10\s*[月/-]\s*\d{1,2}|10/\d{1,2})")


def skeleton_score(text):
    lines = [l for l in text.splitlines()]
    headers = []
    for i, l in enumerate(lines):
        if HEADER_LINE.match(l):
            for k in ("concl", "todo", "open", "replay"):
                if SEC[k].search(l):
                    # "待定" 之类同时命中多个时，按出现在标题里的先后取第一个关键词
                    headers.append((i, k))
                    break
    order = [k for _, k in headers if k in ("concl", "todo", "open")]
    firsts = []
    for k in order:
        if k not in firsts:
            firsts.append(k)
    s = 0.0
    detail = {}
    detail["三块齐且顺序对"] = firsts[:3] == ["concl", "todo", "open"]
    s += 2 if detail["三块齐且顺序对"] else 0
    detail["第一块是结论或待办"] = bool(order) and order[0] in ("concl", "todo")
    s += 1 if detail["第一块是结论或待办"] else 0
    # 开头：第一个结论/待办区块之前的文字里有日期和参会人
    first_sec_line = headers[0][0] if headers else len(lines)
    head = "\n".join(lines[: max(first_sec_line, 1) + 1])
    detail["开头有日期和参会人"] = bool(DATE.search(head)) and bool(re.search(r"参会|参与|出席|与会", head))
    s += 1 if detail["开头有日期和参会人"] else 0
    detail["没有按顺序复述的段落"] = not any(k == "replay" for _, k in headers)
    s += 1 if detail["没有按顺序复述的段落"] else 0
    return s, detail


def scores_from_verdict(v, key, tid):
    sc = {}
    traps_bad = sum(1 for t in v.get("traps", []) if t.get("written_as_decided"))
    extra_bad = len(v.get("extra_false_conclusions") or [])
    sc["K1"] = max(0.0, 10 - 5 * (traps_bad + extra_bad))

    dec = v.get("decided", [])
    sc["K2"] = 10 * sum(1 for d in dec if d.get("in_conclusions")) / max(1, len(key["decided"]))

    todos = {t["id"]: t for t in v.get("todos", [])}
    found = [todos[a["id"]] for a in key["todos"] if todos.get(a["id"], {}).get("found")]
    sc["K3"] = 10 * len(found) / len(key["todos"])
    sc["K4"] = 10 * sum(1 for t in found if t.get("owner_verdict") == "correct") / len(found) if found else 0.0
    sc["K5"] = 5 * sum(1 for t in found if t.get("deadline_verdict") == "correct") / len(found) if found else 0.0

    if key["open"]:
        op = v.get("open", [])
        sc["K6"] = 10 * sum(1 for o in op if o.get("in_open_section")) / len(key["open"])

    sc["K7"] = max(0.0, 10 - 4 * len(v.get("fabrications") or []))

    if key["confirm"]:
        cf = v.get("confirm", [])
        sc["K9"] = 5 * sum(1 for c in cf if c.get("flagged")) / len(key["confirm"])
    return sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", required=True)
    ap.add_argument("--judge", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    keys = json.loads(Path(args.key).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    details = {}

    for arm_dir in sorted(Path(args.judge).iterdir()):
        if not arm_dir.is_dir():
            continue
        arm = arm_dir.name
        groups = defaultdict(list)
        for f in sorted(arm_dir.glob("T*-r*-j*.json")):
            if f.name.endswith(".raw.json"):
                continue
            stem = re.sub(r"-j\d+$", "", f.stem)
            groups[stem].append(json.loads(f.read_text(encoding="utf-8")))
        runs = []
        for stem, verdicts in sorted(groups.items()):
            tid, r = stem.split("-r")
            key = keys[tid]
            per = [scores_from_verdict(v, key, tid) for v in verdicts]
            med = {k: statistics.median(p[k] for p in per) for k in per[0]}
            text = (Path(args.gen) / arm / f"{stem}.md").read_text(encoding="utf-8")
            k8, k8d = skeleton_score(text)
            med["K8"] = k8
            runs.append({"query_id": tid, "run": int(r), "scores": med, "judge_samples": len(verdicts),
                         "judge_spread": {k: max(p[k] for p in per) - min(p[k] for p in per) for k in per[0]}})

            # 逐条明细：多次采样取多数
            def vote(items_key, idf, field):
                c = defaultdict(Counter)
                for v in verdicts:
                    for it in v.get(items_key, []):
                        c[it.get("id")][str(it.get(field))] += 1
                return {i: cnt.most_common(1)[0][0] for i, cnt in c.items()}
            details[f"{arm}/{stem}"] = {
                "traps_written_as_decided": vote("traps", "id", "written_as_decided"),
                "decided_in_conclusions": vote("decided", "id", "in_conclusions"),
                "open_in_section": vote("open", "id", "in_open_section"),
                "todo_found": vote("todos", "id", "found"),
                "todo_owner": vote("todos", "id", "owner_verdict"),
                "todo_deadline": vote("todos", "id", "deadline_verdict"),
                "confirm_flagged": vote("confirm", "id", "flagged"),
                "extra_false_conclusions": [v.get("extra_false_conclusions") for v in verdicts],
                "fabrications": [v.get("fabrications") for v in verdicts],
                "critique": [v.get("critique") for v in verdicts],
                "skeleton": k8d,
            }
        (out / f"{arm}.json").write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{arm}: {len(runs)} 份纪要")
    (out / "逐条明细.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
