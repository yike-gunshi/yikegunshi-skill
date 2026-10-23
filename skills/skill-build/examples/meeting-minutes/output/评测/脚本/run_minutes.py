#!/usr/bin/env python3
"""基线对照第一步：同一句请求，分别在"用 Skill"和"不用 Skill"两组下生成纪要。

两组环境一致：干净环境（--safe-mode，不加载个人配置、其他 skill 和插件），
只开放 Read 工具，同一个模型。唯一差别是 with 组把 SKILL.md 全文作为已加载的
Skill 追加进系统提示，相当于 Skill 被触发后模型读到的内容。

转写稿先复制进一个只有转写稿的沙盒目录再跑，模型读不到标准答案。

用法:
  python3 run_minutes.py --skill ../../meeting-minutes/SKILL.md \
      --transcripts ../转写稿 --sandbox /tmp/xx --out ../基线对照/生成 \
      --arms with without --runs 3 --parallel 6
"""

import argparse
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import meta_of, run_claude, write_json

REQUEST = "刚开完会，妙记导出的转写稿在 ./转写稿/{file}。帮我整理成会议纪要：结论、待办（谁、什么时候做完）、没谈拢的问题。我要直接发到项目群里。"

SKILL_PREAMBLE = "用户为本次会话启用了 skill「meeting-minutes」。以下是它的 SKILL.md，按它执行：\n\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True)
    ap.add_argument("--transcripts", required=True)
    ap.add_argument("--sandbox", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arms", nargs="+", default=["with", "without"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", nargs="*", help="只跑这些题号，如 T1 T3")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--tag", default="", help="输出文件名后缀，用于区分迭代版本")
    args = ap.parse_args()

    skill_text = Path(args.skill).read_text(encoding="utf-8")
    files = sorted(Path(args.transcripts).glob("T*.txt"))
    if args.only:
        files = [f for f in files if f.name[:2] in args.only]

    sandbox = Path(args.sandbox)
    (sandbox / "转写稿").mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy(f, sandbox / "转写稿" / f.name)

    jobs = []
    for arm in args.arms:
        for f in files:
            for r in range(1, args.runs + 1):
                jobs.append((arm, f, r))

    out = Path(args.out)

    def do(job):
        arm, f, r = job
        tid = f.name[:2]
        dest = out / f"{arm}{args.tag}" / f"{tid}-r{r}.md"
        if dest.exists():
            return f"skip {dest.name}"
        extra = ["--safe-mode", "--tools", "Read", "--allowedTools", "Read",
                 "--model", args.model, "--max-turns", "6"]
        if arm == "with":  # 注意 "without" 也以 "with" 开头，不能用 startswith
            extra += ["--append-system-prompt", SKILL_PREAMBLE + skill_text]
        res, wall, err = run_claude(REQUEST.format(file=f.name), cwd=str(sandbox), extra_args=extra)
        meta = meta_of(res, wall)
        meta.update(arm=arm, query_id=tid, run=r, stderr=err if not res else "")
        write_json(dest.with_suffix(".meta.json"), meta)
        if res:
            dest.write_text(res.get("result", ""), encoding="utf-8")
        return f"{arm} {tid} r{r} {'ok' if res else 'FAIL ' + err[:120]} {meta.get('duration_ms')}ms"

    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        for line in ex.map(do, jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
