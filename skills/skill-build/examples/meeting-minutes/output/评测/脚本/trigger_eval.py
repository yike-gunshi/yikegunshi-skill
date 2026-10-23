#!/usr/bin/env python3
"""触发评测：在真实使用环境里看 description 能不能让模型在该用时用、不该用时不用。

环境：
- 沙盒目录里放一个项目级 skill 链接 .claude/skills/meeting-minutes -> 待测 skill 目录
  （只在沙盒里，不装进 ~/.claude/skills）
- 其余照常加载本机的用户级配置和全部 skill，所以 podcast-summary、book-to-mindmap、
  skill-build 这些隔壁 skill 都在，路由竞争是真实的
- 开放只读工具 Read / Glob / Grep 加 Skill。只给 Skill 一个工具会抹掉"自己动手"这条路，
  触发率会虚高
- 题里提到的文件在沙盒里都真实存在

判定：流式读取输出，模型调用 Skill 且 skill 名为 meeting-minutes 即记为触发，随即结束该次运行；
最多 3 轮仍未调用即记为未触发。

用法:
  python3 trigger_eval.py --evalset ../触发评测集.json --skill-dir ../../meeting-minutes \
      --fixtures ../转写稿 --sandbox /tmp/xx --out ../触发评测/结果.jsonl --runs 3 --parallel 6
"""

import argparse
import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import CLAUDE_BIN, _env

PODCAST = "主持人 00:00:05\n欢迎收听《商业就是这样》第 88 期，今天我们聊聊连锁咖啡的定价……\n嘉宾 00:01:10\n其实定价的核心不是成本，是你想让顾客怎么比较……\n（虚构示例）\n"
COURSE = "老师 00:00:03\n同学们好，第三讲我们讲需求分析的三个层次：用户说的、用户做的、用户需要的……\n（虚构示例）\n"
INTERVIEW = "访谈员 00:00:02\n您平时怎么记账？\n受访者 00:00:09\n嗯，我一般月底才想起来，用的是手机自带的备忘录……\n（虚构示例）\n"
MINUTES = "# {name}纪要\n\n2026-10-{d} · 参会：林舟、陈默\n\n## 结论\n1. 示例结论\n\n## 待办\n1. **陈默**：示例待办（截止：周五）\n\n## 没谈拢的问题\n无\n"


def build_sandbox(sandbox, skill_dir, fixtures):
    sb = Path(sandbox)
    (sb / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
    link = sb / ".claude" / "skills" / "meeting-minutes"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(Path(skill_dir).resolve())
    tr = sb / "transcripts"
    tr.mkdir(exist_ok=True)
    src = {f.name[:2]: f.read_text(encoding="utf-8") for f in Path(fixtures).glob("T*.txt")}
    mapping = {"1021-产品评审会.txt": "T1", "周会1019.txt": "T1", "客户对齐会.txt": "T2",
               "Q3复盘会.txt": "T5", "standup-1021.txt": "T3", "供应商沟通会.txt": "T2",
               "双十一运营会.txt": "T5"}
    for name, t in mapping.items():
        (tr / name).write_text(src[t], encoding="utf-8")
    (tr / "播客-E88.txt").write_text(PODCAST, encoding="utf-8")
    (tr / "课程-第3讲.txt").write_text(COURSE, encoding="utf-8")
    iv = sb / "interviews"
    iv.mkdir(exist_ok=True)
    for i in range(1, 4):
        (iv / f"用户访谈{i}.txt").write_text(INTERVIEW, encoding="utf-8")
    mn = sb / "minutes"
    mn.mkdir(exist_ok=True)
    for i, n in enumerate(["周一站会", "产品评审会", "客户对齐会", "供应商沟通会", "周五复盘会"]):
        (mn / f"10{19 + i}-{n}纪要.md").write_text(MINUTES.format(name=n, d=19 + i), encoding="utf-8")
    (mn / "1021-客户对齐会纪要.md").write_text(MINUTES.format(name="客户对齐会", d=21), encoding="utf-8")


def one_run(query, sandbox, model, max_turns=3, timeout=300):
    cmd = [CLAUDE_BIN, "-p", query, "--output-format", "stream-json", "--verbose",
           "--no-session-persistence", "--exclude-dynamic-system-prompt-sections",
           "--tools", "Read,Glob,Grep,Skill", "--allowedTools", "Read Glob Grep Skill",
           "--model", model, "--max-turns", str(max_turns)]
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=sandbox, env=_env(), stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    timer = threading.Timer(timeout, p.kill)
    timer.start()
    tools, skill, cost = [], None, None
    try:
        for line in p.stdout:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "assistant":
                for c in ev.get("message", {}).get("content", []):
                    if c.get("type") == "tool_use":
                        tools.append(c.get("name"))
                        if c.get("name") == "Skill":
                            skill = (c.get("input") or {}).get("skill") or (c.get("input") or {}).get("command")
                            if skill:
                                break
                if skill:
                    p.kill()
                    break
            if ev.get("type") == "result":
                cost = ev.get("total_cost_usd")
    finally:
        timer.cancel()
        p.wait()
    return {"tools": tools, "skill": skill, "cost": cost, "wall_s": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evalset", required=True)
    ap.add_argument("--skill-dir", required=True)
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--sandbox", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--model", default="opus")
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    build_sandbox(args.sandbox, args.skill_dir, args.fixtures)
    es = json.loads(Path(args.evalset).read_text(encoding="utf-8"))
    items = [(q, True) for q in es["should_trigger"]] + [(q, False) for q in es["should_not_trigger"]]
    if args.only:
        items = [x for x in items if x[0]["id"] in args.only]
    jobs = [(q, pos, r) for q, pos in items for r in range(1, args.runs + 1)]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for l in out.read_text(encoding="utf-8").splitlines():
            d = json.loads(l)
            done.add((d["id"], d["run"]))
    lock = threading.Lock()

    def do(job):
        q, pos, r = job
        if (q["id"], r) in done:
            return f"skip {q['id']} r{r}"
        res = one_run(q["query"], args.sandbox, args.model)
        rec = {"id": q["id"], "run": r, "should_trigger": pos, "split": q["split"],
               "triggered": res["skill"] == "meeting-minutes", **res}
        with lock:
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return f"{q['id']} r{r} skill={res['skill']} tools={res['tools']}"

    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        for line in ex.map(do, jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
