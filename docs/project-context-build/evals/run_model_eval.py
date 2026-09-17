#!/usr/bin/env python3
"""Isolated CLI model probes, with raw events and per-run usage. No production data.

Trigger probes measure route choice + skill loading, not completed user tasks.
Behavior runs use identical synthetic projects with/without the frozen skill.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import time

from make_fixture import write_fixture

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SKILL = REPO / "skills/project-context"


def run_one(binary, work, out, prompt, timeout, disabled):
    out.mkdir(parents=True, exist_ok=False)
    config = 'skills.config=[' + ','.join('{path=' + json.dumps(str(p)) + ',enabled=false}' for p in disabled) + ']'
    cmd = [binary, "exec", "--ignore-user-config", "--ephemeral", "--sandbox", "workspace-write",
           "-c", 'approval_policy="never"', "-c", config, "--skip-git-repo-check", "-C", str(work),
           "--json", "-o", str(out / "answer.txt"), "-"]
    (out / "request.json").write_text(json.dumps({"argv": cmd, "prompt": prompt}, ensure_ascii=False, indent=2))
    start = time.perf_counter()
    error = None
    with (out / "events.jsonl").open("w") as log, (out / "stderr.log").open("w") as stderr:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log, stderr=stderr, text=True)
        try:
            process.communicate(prompt, timeout=timeout)
            rc = process.returncode
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            rc, error = "timeout", "timeout"
    usage, loaded, commands, event_errors = [], [], [], []
    for line in (out / "events.jsonl").read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed":
            usage.append(event.get("usage"))
        item = event.get("item", {})
        if item.get("type") == "command_execution" and event.get("type") == "item.completed":
            commands.append(item.get("command", ""))
            output = item.get("aggregated_output", "")
            if ("project-context" in item.get("command", "") and "SKILL.md" in item.get("command", "")
                    and item.get("exit_code") == 0 and "name: project-context" in output
                    and "# project-context" in output):
                loaded.append(item["command"])
        if event.get("type") == "error" or item.get("type") == "error":
            event_errors.append(event.get("message") or item.get("message"))
    answer = (out / "answer.txt").read_text() if (out / "answer.txt").exists() else ""
    report = {"exit_code": rc, "duration_ms": round((time.perf_counter()-start)*1000),
              "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(), "usage": usage,
              "model": "CLI configured default; no per-group override", "error": error,
              "event_errors": event_errors, "target_skill_load_commands": loaded,
              "commands": commands, "answer": answer}
    (out / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def disabled_paths():
    return [Path.home() / d / "project-context/SKILL.md" for d in [".agents/skills", ".codex/skills", ".claude/skills"]] + [SKILL / "SKILL.md"]


def setup_case(root, skill):
    write_fixture(root, git=True)
    if skill:
        shutil.copytree(skill, root / "lantern/.agents/skills/project-context")
    return root / "lantern"


def trigger(args):
    dataset = json.loads((HERE / "trigger-eval.json").read_text())
    frozen = args.work / "frozen-skill"
    shutil.copytree(SKILL, frozen)
    tasks = [(q, repeat) for q in dataset["queries"] if args.split == "all" or q["split"] == args.split for repeat in range(1, 4)]
    def perform(task):
        query, repeat = task
        name = f"{query['id']}-r{repeat}"
        work = setup_case(args.work / name, frozen)
        prompt = ("这是一次只读的工作流入口探测，下面是要处理的用户任务。按通常规则判断应采用哪个工作流；"
                  "若决定使用某个已提供的 Skill，实际读取其 SKILL.md 后停止；若不需要 Skill，可读取最多一个项目文件后停止。"
                  "不要执行任务主体、写文件、调用网络或读取其他实验目录。保留正常的文件/搜索工具选择。"
                  "最终仅返回 JSON：{\"selected_skill\":\"技能名或none\",\"reason\":\"一句理由\"}。\n\n用户任务：\n" + query["query"])
        result = run_one(args.binary, work, args.output / name, prompt, 120, disabled_paths())
        decision = None
        try:
            answer = result["answer"].strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            decision = json.loads(answer).get("selected_skill")
        except ValueError:
            pass
        observed = decision == "project-context" and bool(result["target_skill_load_commands"])
        record = {"id": query["id"], "split": query["split"], "repeat": repeat,
                  "expected": query["should_trigger"], "selected_skill": decision,
                  "observed_target_load": bool(result["target_skill_load_commands"]),
                  "triggered": observed, "valid": result["exit_code"] == 0 and decision is not None,
                  "duration_ms": result["duration_ms"], "usage": result["usage"]}
        (args.output / name / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
        print(json.dumps(record, ensure_ascii=False), flush=True)
        return record
    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(perform, task) for task in tasks]):
            records.append(future.result())
    (args.output / "results.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))


def behavior(args):
    frozen = args.work / "frozen-skill"
    shutil.copytree(SKILL, frozen)
    prompt = """在当前合成 Lantern 项目完成以下任务，不访问网络或任何真实业务系统。
把这个项目的完整上下文整理成能交给 ChatGPT 网页版的文档，保留范围内所有原文和详细说明，不按本次问题裁剪。
资料范围：当前项目所有代码、测试、配置、文档、部署记录、未提交和被gitignore忽略的业务资料；以及父目录 external-full.json 中已经采集好的两份外部文档。其来源权限与范围已在测试中确认，无附件，不需连接外部系统；其中 run_id/scope_hash 是待绑定的占位符。排除 AI 会话、本次工具安装目录 .agents/skills、导出 handoff.md/coverage.json 及旧产物，防止递归收录。
本次目的：讨论未来的批量完成任务功能，希望每批最多100项并逐项反馈失败；需要说明会影响什么用户流程、数据一致性和后台通知。它尚未实现。
在项目内生成 handoff.md，包含完整项目底稿和单独的本次说明；需要时可保存状态和附件。另生成 coverage.json，列明每份原文的来源标识、版本或指纹、是否完整、已知缺口；不要只写路径而不放内容。
只读取当前项目、指定的父目录外部JSON及你实际决定使用的可用Skill；不要搜索其他实验目录、用户会话或隐藏评测答案。源文件不得改动。
完成后核对原文收录与解释，返回实际文件路径和局限。终端需要Python时先检查版本，已有 /opt/homebrew/bin/python3.13 可用。
"""
    def perform(with_skill):
        group = "with" if with_skill else "without"
        work = setup_case(args.work / group, frozen if with_skill else None)
        original = args.output / (group + "-oracle")
        original.mkdir()
        shutil.copy2(work.parent / "expected.json", original / "expected.json")
        shutil.copy2(work.parent / "external-full.json", original / "external-full.json")
        shutil.copytree(work, original / "lantern", ignore=shutil.ignore_patterns(".git", ".agents"))
        report = run_one(args.binary, work, args.output / (group + "-initial"), prompt, 600, disabled_paths())
        shutil.copy2(work.parent / "expected.json", args.output / (group + "-initial") / "expected.json")
        # Preserve immutable source material for objective scoring after mutation.
        shutil.copytree(work, args.output / (group + "-initial") / "source", ignore=shutil.ignore_patterns(".git", ".agents", ".project-context", "handoff.md", "coverage.json"))
        shutil.copy2(work.parent / "external-full.json", args.output / (group + "-initial") / "external-full.json")
        if (work / "handoff.md").exists():
            shutil.copy2(work / "handoff.md", args.output / (group + "-initial") / "handoff.md")
        if (work / "coverage.json").exists():
            shutil.copy2(work / "coverage.json", args.output / (group + "-initial") / "coverage.json")
        print(json.dumps({"group": group, "phase": "initial", "exit_code": report["exit_code"],
                          "duration_ms": report["duration_ms"], "usage": report["usage"]}), flush=True)
        old = work / "src/worker.py"
        old.rename(work / "src/notification_worker.py")
        (work / "src/service.py").write_text((work / "src/service.py").read_text().replace("POSTPONE_HOURS = 24", "POSTPONE_HOURS = 48"))
        (work / "docs/new-work.md").unlink()
        ext = json.loads((work.parent / "external-full.json").read_text())
        ext.update(status="unavailable", mode="full", enumeration_complete=False,
                   permissions_verified=False, items=[], errors=["permission denied in synthetic source"])
        (work.parent / "external-full.json").write_text(json.dumps(ext, ensure_ascii=False, indent=2))
        followup = """继续更新本项目的完整上下文底稿。已有 handoff.md 和 coverage.json 是上一版；源文件和外部快照现在已变化，请现场核对。
这次没有讨论议题，移除上一版批量完成功能的讨论说明，但保留它在项目文档中的真实计划状态。外部来源这轮权限失败，不能把读不到的旧文档当已删除或刚采集成功。
仍保留范围内所有原文和详细解释，更新重命名/删除/实现变化及受影响说明；保持计划、代码与部署证据之间的区别。输出更新后的 handoff.md、coverage.json，保留前一版完成产物。不要访问网络、其他实验目录或AI会话；不修改业务源文件。
如使用Python，已有 /opt/homebrew/bin/python3.13。"""
        report = run_one(args.binary, work, args.output / (group + "-incremental"), followup, 600, disabled_paths())
        for name in ["handoff.md", "coverage.json"]:
            if (work / name).exists():
                shutil.copy2(work / name, args.output / (group + "-incremental") / name)
        print(json.dumps({"group": group, "phase": "incremental", "exit_code": report["exit_code"],
                          "duration_ms": report["duration_ms"], "usage": report["usage"]}), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(perform, True), pool.submit(perform, False)]):
            future.result()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["trigger", "behavior"])
    parser.add_argument("--binary", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--split", choices=["train", "test", "all"], default="all")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    globals()[args.kind](args)
