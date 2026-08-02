#!/usr/bin/env python3
"""考点分数聚合 + 基线对照区分度审计。

用法:
    python3 score_rubric.py --with with.json [--without without.json]
                            [--no-signal 0.5] [--high-var 2.0] [--json]

输入 JSON 是一个数组，每个元素是一次 run 的打分:

    [
      {"query_id": "q1", "run": 1, "scores": {"考点1": 10, "考点2": 7}},
      {"query_id": "q1", "run": 2, "scores": {"考点1": 10, "考点2": 8}},
      {"query_id": "q2", "run": 1, "scores": {"考点1": 6,  "考点2": 9}}
    ]

也接受 {"runs": [...]} 包一层，以及 scores 里用 {"分数": 8} 的对象形态。

输出每条考点的 with/without 均值、分差、标准差，并打标：
  NO-SIGNAL   分差在阈值内 —— 考点无区分度，或该约束本就是模型默认行为，
              对应的 SKILL.md 章节是候选删减对象
  REGRESSION  with 显著低于 without —— skill 在这条上帮倒忙，优先修
  HIGH-VAR    同条考点跨 run 波动大 —— 指令在那里可能有歧义
"""

import argparse
import json
import statistics
import sys
from pathlib import Path


def load_runs(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("runs") or data.get("results") or []
    if not isinstance(data, list):
        raise ValueError(f"{path}: 顶层应为数组，或含 runs/results 字段的对象")

    out = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: 第 {i} 项不是对象")
        scores = item.get("scores") or item.get("考点得分") or {}
        norm = {}
        for k, v in scores.items():
            if isinstance(v, dict):
                v = v.get("分数", v.get("score"))
            try:
                norm[str(k)] = float(v)
            except (TypeError, ValueError):
                raise ValueError(f"{path}: 考点 '{k}' 的分数不是数字: {v!r}")
        out.append({
            "query_id": str(item.get("query_id", item.get("id", f"#{i}"))),
            "run": item.get("run", 1),
            "scores": norm,
        })
    if not out:
        raise ValueError(f"{path}: 没有任何 run")
    return out


def by_criterion(runs):
    agg = {}
    for r in runs:
        for k, v in r["scores"].items():
            agg.setdefault(k, []).append(v)
    return agg


def stats(vals):
    return {
        "n": len(vals),
        "mean": statistics.fmean(vals),
        "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
        "min": min(vals),
        "max": max(vals),
    }


def query_totals(runs):
    per_query = {}
    for r in runs:
        per_query.setdefault(r["query_id"], []).append(sum(r["scores"].values()))
    return {q: statistics.fmean(v) for q, v in per_query.items()}


def main():
    ap = argparse.ArgumentParser(description="考点聚合 + 区分度审计")
    ap.add_argument("--with", dest="with_path", required=True, help="with-skill 的打分结果")
    ap.add_argument("--without", dest="without_path", help="baseline 的打分结果（不给则只做聚合）")
    ap.add_argument("--no-signal", type=float, default=0.5, help="分差阈值，低于它判无区分度（默认 0.5）")
    ap.add_argument("--high-var", type=float, default=2.0, help="标准差阈值，高于它判高方差（默认 2.0）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    try:
        with_runs = load_runs(args.with_path)
        without_runs = load_runs(args.without_path) if args.without_path else None
    except (ValueError, json.JSONDecodeError, OSError) as e:
        print(f"输入有问题: {e}", file=sys.stderr)
        return 2

    w_agg = by_criterion(with_runs)
    n_agg = by_criterion(without_runs) if without_runs else {}

    rows = []
    for crit in sorted(w_agg, key=lambda c: (len(c), c)):
        w = stats(w_agg[crit])
        row = {"criterion": crit, "with": w, "without": None, "delta": None, "flags": []}
        if w["std"] > args.high_var:
            row["flags"].append("HIGH-VAR")
        if crit in n_agg:
            nb = stats(n_agg[crit])
            delta = w["mean"] - nb["mean"]
            row["without"] = nb
            row["delta"] = delta
            if delta < -args.no_signal:
                row["flags"].append("REGRESSION")
            elif abs(delta) <= args.no_signal:
                row["flags"].append("NO-SIGNAL")
        elif without_runs:
            row["flags"].append("BASELINE-MISSING")
        rows.append(row)

    w_tot = query_totals(with_runs)
    n_tot = query_totals(without_runs) if without_runs else {}
    summary = {
        "with_total_mean": statistics.fmean(w_tot.values()),
        "without_total_mean": statistics.fmean(n_tot.values()) if n_tot else None,
        "with_runs": len(with_runs),
        "without_runs": len(without_runs) if without_runs else 0,
        "queries": len(w_tot),
    }
    if summary["without_total_mean"] is not None:
        summary["total_delta"] = summary["with_total_mean"] - summary["without_total_mean"]

    if args.json:
        print(json.dumps({"summary": summary, "criteria": rows, "per_query_total": w_tot},
                         ensure_ascii=False, indent=2))
        return 0

    has_base = without_runs is not None
    print(f"query {summary['queries']} 条 · with {summary['with_runs']} run"
          + (f" · without {summary['without_runs']} run" if has_base else " · 无基线对照"))
    print()

    head = f"{'考点':<14}{'with':>8}{'±std':>8}"
    if has_base:
        head += f"{'without':>10}{'分差':>8}"
    head += "  标记"
    print(head)
    print("-" * (len(head) + 12))

    for r in rows:
        line = f"{r['criterion']:<14}{r['with']['mean']:>8.2f}{r['with']['std']:>8.2f}"
        if has_base:
            if r["without"]:
                line += f"{r['without']['mean']:>10.2f}{r['delta']:>+8.2f}"
            else:
                line += f"{'-':>10}{'-':>8}"
        line += "  " + " ".join(r["flags"])
        print(line)

    print()
    line = f"总分均值  with {summary['with_total_mean']:.2f}"
    if has_base:
        line += f" · without {summary['without_total_mean']:.2f} · 分差 {summary['total_delta']:+.2f}"
    print(line)

    ns = [r["criterion"] for r in rows if "NO-SIGNAL" in r["flags"]]
    rg = [r["criterion"] for r in rows if "REGRESSION" in r["flags"]]
    hv = [r["criterion"] for r in rows if "HIGH-VAR" in r["flags"]]
    print()
    if rg:
        print(f"REGRESSION {', '.join(rg)}")
        print("  skill 在这几条上帮倒忙，优先修——通常是某条约束和场景冲突")
    if ns:
        print(f"NO-SIGNAL  {', '.join(ns)}")
        print("  有没有 skill 都一样。淘汰这些考点；对应的 SKILL.md 章节列为候选删减对象")
    if hv:
        print(f"HIGH-VAR   {', '.join(hv)}")
        print("  跨 run 波动大，指令在那里可能有歧义，S5 重点排查")
    if not (rg or ns or hv):
        print("没有 NO-SIGNAL / REGRESSION / HIGH-VAR 考点")
    if not has_base:
        print()
        print("没跑基线对照，无法回答「不用这个 skill 会差多少」。完整档补上 --without")
    return 0


if __name__ == "__main__":
    sys.exit(main())
