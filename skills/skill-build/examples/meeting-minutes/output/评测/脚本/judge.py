#!/usr/bin/env python3
"""基线对照第二步：评委逐条比对，输出 JSON 判断（不打分，分数由 score.py 算）。

评委只看到：转写稿、该题标准答案、一份纪要。不知道纪要来自哪一组。
每份纪要独立判 N 次（默认 3），score.py 取每条考点的中位数。

用法:
  python3 judge.py --gen ../基线对照/生成 --transcripts ../转写稿 \
      --key ../标准答案.json --out ../基线对照/评委 --samples 3 --parallel 8
"""

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import run_claude, write_json

JUDGE_SYSTEM = """# 会议纪要评审员

你是一位严格的会议纪要评审员。你会拿到一份会议转写稿、这场会的标准答案、一份待评的纪要（可能夹着写给用户的开场白和附注，一并看）。你的任务是逐条比对，给出判断，不打总分。

# 判断规则

1. decided：标准答案里的每条结论，纪要的"结论"区（或同义的已定/决议区）里有没有写到。意思对上即可，不要求字面一致。
2. traps：标准答案里的每个陷阱项（会上讨论过但没拍板），纪要有没有把它当成已定的事写进结论区，或在别处用"已定""确定"之类的说法陈述。
   - 结论区写"X 暂不定""X 看数据再定""X 下次再议"，不算把 X 写成已定。
   - 被会上推翻的旧方案写进结论区当现行方案，算写成已定。
3. extra_false_conclusions：结论区里除陷阱项以外，其他会上并没有拍板、却被写成已定的条目。只是陈述现状（"前端已完成"）不算；把待办写进结论区也不算。没有就给空数组。
4. open：标准答案里每个没谈拢的事，纪要的"没谈拢/未决/待定/分歧"区里有没有写到。
5. todos：标准答案里每条待办——
   - found：纪要的待办区里有没有这件事。
   - owner_verdict：
     - correct：负责人写对了（标准答案写"说话人2"的，纪要写说话人2或"说话人2认领"都算对；标准答案说未落实到人的，纪要标了待定/待认领/未明确也算 correct）
     - wrong_person：写了一个和标准答案不符的具体人（包括把未落实到人的事写成某个具体的人，或把改派前的人写成负责人）
     - over_flagged：会上明明点名或认领了，纪要却写成待定
     - missing：found=false 时填这个
   - deadline_verdict：
     - correct：会上说了的写对了（只写原话、没换算日期也算对；换算对了也算对）；会上没说的写了未说定/未提/空着
     - fabricated：会上没说截止，纪要写了一个具体时间
     - wrong：会上说了，但纪要写错了（包括换算出错的日期）
     - missing：found=false，或会上说了截止但纪要没写
6. fabrications：纪要里出现、但转写稿里找不到依据的人名、数字、日期、承诺、决定。负责人和截止的错已在 todos 里判过，不要重复列。合理的书面化改写不算编造。没有就给空数组。
7. confirm：标准答案里的每个疑点，纪要（含附注）有没有提醒用户去确认。没有疑点就给空数组。
8. critique：如果你觉得标准答案或这套判断规则本身有毛病（标准答案有错、某条判断两可），写在这里；没有就填 null。

判断时以转写稿原文为准。标准答案如有错误，按转写稿判，并在 critique 里指出。

# 输出

只输出一个 JSON 对象，放在 ```json 代码块里，不要输出其他内容：

```json
{
  "decided": [{"id": "D1", "in_conclusions": true, "note": "一句话依据"}],
  "traps": [{"id": "X1", "written_as_decided": false, "note": "一句话依据"}],
  "extra_false_conclusions": [{"text": "纪要原文", "why": "为什么不算已定"}],
  "open": [{"id": "O1", "in_open_section": true, "note": "一句话依据"}],
  "todos": [{"id": "A1", "found": true, "owner_verdict": "correct", "deadline_verdict": "correct", "note": "一句话依据"}],
  "fabrications": [{"text": "纪要原文", "why": "转写稿里找不到的依据"}],
  "confirm": [{"id": "C1", "flagged": true}],
  "critique": null
}
```
"""

PROMPT = """## 转写稿

{transcript}

## 标准答案

```json
{key}
```

## 待评纪要

{minutes}
"""


def parse_json(text):
    m = re.search(r"```json\s*(\{.*\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", required=True, help="生成结果目录，下面是 with/ without/ 等")
    ap.add_argument("--transcripts", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arms", nargs="*", help="只判这些组")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--model", default="opus")
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--cwd", default="/tmp")
    args = ap.parse_args()

    keys = json.loads(Path(args.key).read_text(encoding="utf-8"))
    tfiles = {f.name[:2]: f for f in Path(args.transcripts).glob("T*.txt")}

    jobs = []
    for arm_dir in sorted(Path(args.gen).iterdir()):
        if not arm_dir.is_dir() or (args.arms and arm_dir.name not in args.arms):
            continue
        for md in sorted(arm_dir.glob("T*-r*.md")):
            for s in range(1, args.samples + 1):
                jobs.append((arm_dir.name, md, s))

    out = Path(args.out)

    def do(job):
        arm, md, s = job
        tid = md.name[:2]
        dest = out / arm / f"{md.stem}-j{s}.json"
        if dest.exists():
            return f"skip {arm}/{dest.name}"
        key = {k: v for k, v in keys[tid].items() if k not in ("file",)}
        prompt = PROMPT.format(transcript=tfiles[tid].read_text(encoding="utf-8"),
                               key=json.dumps(key, ensure_ascii=False, indent=2),
                               minutes=md.read_text(encoding="utf-8"))
        # 每次采样加一个不影响判断的编号，避免完全相同的请求
        nonce = hashlib.md5(f"{md}{s}".encode()).hexdigest()[:6]
        extra = ["--safe-mode", "--tools", "", "--model", args.model, "--max-turns", "1",
                 "--system-prompt", JUDGE_SYSTEM + f"\n\n（评审编号 {nonce}）"]
        verdict, res, last = None, None, ""
        for _ in range(3):  # 评委偶尔在字符串里用了没转义的英文引号，JSON 不合法，重试
            res, wall, err = run_claude(prompt, cwd=args.cwd, extra_args=extra)
            if not res:
                last = err
                continue
            try:
                verdict = parse_json(res.get("result", ""))
                break
            except Exception as e:  # noqa: BLE001
                last = str(e)
                write_json(dest.with_suffix(".raw.json"), res)
        if verdict is None:
            return f"FAIL {arm}/{md.name} j{s}: {last[:150]}"
        dest.with_suffix(".raw.json").unlink(missing_ok=True)
        verdict["_meta"] = {"cost": res.get("total_cost_usd"), "duration_ms": res.get("duration_ms")}
        write_json(dest, verdict)
        return f"ok {arm}/{md.name} j{s}"

    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        for line in ex.map(do, jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
