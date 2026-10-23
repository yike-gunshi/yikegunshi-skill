#!/usr/bin/env python3
"""盲评：同一份转写稿、同一轮次的两份纪要，打乱顺序交给评委，不告诉它谁用了 Skill。

评委扮演群里的参会人，只看转写稿和两份纪要（不给标准答案），回答哪份更能直接拿来用。
这是和考点评分独立的另一个视角。

用法:
  python3 pairwise.py --gen ../基线对照/生成 --a with --b without \
      --transcripts ../转写稿 --out ../基线对照/盲评 --parallel 6
"""

import argparse
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import run_claude, write_json

SYSTEM = """你是这场会的一位参会人。会后群里收到两份候选纪要，你要判断哪一份更能直接拿来用。

判断依据，按重要性排：
1. 有没有把会上没定的事写成定了（会让人照着错的结论干活）
2. 有没有漏掉会上派的活，负责人和截止时间写得对不对、有没有替人认领
3. 有没有写转写稿里没有的内容
4. 能不能一眼看到结论和待办

以转写稿为准，自己核对。两份都没毛病、差别只在措辞时判"平"。

只输出一个 JSON 对象，放在 ```json 代码块里：
```json
{"winner": "甲" 或 "乙" 或 "平", "reason": "两三句话说清决定性的差别", "甲的问题": ["..."], "乙的问题": ["..."]}
```"""

PROMPT = """## 转写稿

{transcript}

## 纪要甲

{a}

## 纪要乙

{b}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--transcripts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="opus")
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--seed", type=int, default=20261022)
    ap.add_argument("--cwd", default="/tmp")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    tfiles = {f.name[:2]: f for f in Path(args.transcripts).glob("T*.txt")}
    gen = Path(args.gen)
    jobs = []
    for fa in sorted((gen / args.a).glob("T*-r*.md")):
        fb = gen / args.b / fa.name
        if fb.exists():
            jobs.append((fa, fb, rng.random() < 0.5))

    out = Path(args.out)

    def do(job):
        fa, fb, swap = job
        dest = out / f"{args.a}-vs-{args.b}" / f"{fa.stem}.json"
        if dest.exists():
            return f"skip {dest.name}"
        first, second = (fb, fa) if swap else (fa, fb)
        prompt = PROMPT.format(transcript=tfiles[fa.name[:2]].read_text(encoding="utf-8"),
                               a=first.read_text(encoding="utf-8"), b=second.read_text(encoding="utf-8"))
        v = None
        for _ in range(2):  # 评委偶尔输出不合法的 JSON（比如字符串里没转义的引号），重试一次
            res, wall, err = run_claude(prompt, cwd=args.cwd,
                                        extra_args=["--safe-mode", "--tools", "", "--model", args.model,
                                                    "--max-turns", "1", "--system-prompt", SYSTEM])
            if not res:
                continue
            text = res.get("result", "")
            m = re.search(r"```json\s*(\{.*\})\s*```", text, re.S)
            try:
                v = json.loads(m.group(1) if m else text[text.find("{"): text.rfind("}") + 1])
                break
            except json.JSONDecodeError:
                v = None
        if v is None:
            return f"FAIL {fa.name}: {err[:150] if not res else 'json parse'}"
        label = {"甲": args.b if swap else args.a, "乙": args.a if swap else args.b, "平": "平"}
        v["winner_arm"] = label.get(v.get("winner"), "?")
        v["order"] = {"甲": first.parent.name, "乙": second.parent.name}
        write_json(dest, v)
        return f"{fa.stem}: {v['winner_arm']}"

    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        for line in ex.map(do, jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
