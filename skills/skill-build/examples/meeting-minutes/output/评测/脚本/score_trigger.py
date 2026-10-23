#!/usr/bin/env python3
"""汇总触发评测：每条题的触发率，以及 train / test 上的召回、误触发。

一条题跑 N 次，触发次数过半记为"触发"。

用法: python3 score_trigger.py ../触发评测/结果-v1.jsonl
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


def main():
    path = Path(sys.argv[1])
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by = defaultdict(list)
    for r in recs:
        by[r["id"]].append(r)

    print(f"{'题号':<5}{'集合':<7}{'应触发':<7}{'触发次数':<9}去向（每次）")
    stats = defaultdict(lambda: {"TP": 0, "FN": 0, "FP": 0, "TN": 0})
    for qid in sorted(by, key=lambda x: (x[0], int(x[1:]))):
        rs = sorted(by[qid], key=lambda r: r["run"])
        pos = rs[0]["should_trigger"]
        hit = sum(r["triggered"] for r in rs)
        dest = [r["skill"] or ("自己动手:" + "/".join(dict.fromkeys(r["tools"])) if r["tools"] else "直接回答") for r in rs]
        print(f"{qid:<5}{rs[0]['split']:<7}{'是' if pos else '否':<8}{hit}/{len(rs):<8}{' | '.join(dest)}")
        maj = hit * 2 > len(rs)
        for sp in (rs[0]["split"], "全部"):
            s = stats[sp]
            if pos:
                s["TP" if maj else "FN"] += 1
            else:
                s["FP" if maj else "TN"] += 1
    print()
    for sp in ("train", "test", "全部"):
        s = stats[sp]
        npos, nneg = s["TP"] + s["FN"], s["FP"] + s["TN"]
        print(f"{sp:<6} 正例触发 {s['TP']}/{npos} · 负例误触发 {s['FP']}/{nneg}")
    runs_pos = [r for r in recs if r["should_trigger"]]
    runs_neg = [r for r in recs if not r["should_trigger"]]
    print(f"按单次运行算：正例 {sum(r['triggered'] for r in runs_pos)}/{len(runs_pos)} 次触发，"
          f"负例 {sum(r['triggered'] for r in runs_neg)}/{len(runs_neg)} 次误触发")


if __name__ == "__main__":
    main()
