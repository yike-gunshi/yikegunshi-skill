#!/usr/bin/env python3
"""Keep compact evaluation evidence; raw per-run traces remain local."""
import hashlib
import json
from pathlib import Path
import shutil
import statistics

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "results"
OUT.mkdir(exist_ok=True)


def read(path):
    return json.loads(path.read_text())


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def usage(entries):
    usable = [x for x in entries if isinstance(x, dict)]
    if not usable:
        return None
    result = {k: sum(x.get(k, 0) for x in usable) for k in ("input_tokens", "cached_input_tokens", "output_tokens")}
    result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    return result


records = []
for split in ("train", "test"):
    records += read(HERE / f"model-trigger-{split}-v2/results.json")
write("routing-runs.json", records)
routing = {}
for split in ("train", "test", "all"):
    subset = [r for r in records if split == "all" or r["split"] == split]
    valid = [r for r in subset if r["valid"]]
    routing[split] = {
        "runs": len(subset), "valid": len(valid),
        "correct": sum(r["expected"] == r["triggered"] for r in valid),
        "true_positive": sum(r["expected"] and r["triggered"] for r in valid),
        "false_positive": sum(not r["expected"] and r["triggered"] for r in valid),
        "false_negative": sum(r["expected"] and not r["triggered"] for r in valid),
        "median_duration_ms": statistics.median(r["duration_ms"] for r in valid),
        "usage": usage([u for r in valid for u in r["usage"]]),
    }

behavior = {}
for group in ("with", "without"):
    for phase in ("initial", "incremental"):
        name = group + "-" + phase
        folder = HERE / "model-behavior-v1" / name
        metrics = read(folder / "metrics.json")
        behavior[name] = {
            "exit_code": metrics["exit_code"], "duration_ms": metrics["duration_ms"],
            "usage": usage(metrics["usage"]), "model": metrics["model"],
            "objective": read(folder / "objective-normalized.json"),
            "skill_loaded": bool(metrics["target_skill_load_commands"]),
            "artifact_sha256": hashlib.sha256((folder / "handoff.md").read_bytes()).hexdigest(),
        }
        target = OUT / name
        target.mkdir(exist_ok=True)
        for artifact in ("handoff.md", "coverage.json", "answer.txt", "objective-normalized.json"):
            shutil.copy2(folder / artifact, target / artifact)

judges_root = Path("/private/tmp/project-context-blind-review-v1")
judges = []
for index in range(1, 4):
    path = judges_root / f"judge-{index}.json"
    if path.exists():
        report = read(path)
        judges.append(report)
        write(path.name, report)

mapping = {"A": "without-initial", "B": "with-incremental", "C": "with-initial", "D": "without-incremental"}
subjective = {}
if len(judges) == 3:
    for label, name in mapping.items():
        values = {}
        for judge in judges:
            for criterion in judge["outputs"][label]["criteria"]:
                values.setdefault(criterion["id"], []).append(criterion["score"])
        medians = {key: statistics.median(scores) for key, scores in values.items()}
        subjective[name] = {"criteria_medians": medians, "total_of_medians": sum(medians.values()),
                            "samples": values, "max": 60}

skill = HERE.parents[2] / "skills/project-context"
frozen = Path("/private/tmp/project-context-behavior-v1/frozen-skill")
versions = {}
for folder, label in ((frozen, "behavior_frozen"), (skill, "current")):
    versions[label] = {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(folder.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
write("evaluated-versions.json", versions)
probe_folder = HERE / "model-verification-probe-v2"
probe = None
if (probe_folder / "metrics.json").exists():
    metrics = read(probe_folder / "metrics.json")
    note = Path("/private/tmp/project-context-verification-probe-v2/lantern/verification-note.md")
    shutil.copy2(note, OUT / "verification-note-v2.md")
    probe = {"exit_code": metrics["exit_code"], "duration_ms": metrics["duration_ms"],
             "usage": usage(metrics["usage"]), "answer": metrics["answer"],
             "assertion": "Output explicitly says no execution and distinguishes static import mismatch from actual test failure",
             "method": "One targeted model run; explicit task forbids running project code/tests; not an estimate of general reliability"}
    write("verification-probe-v2.json", probe)
write("summary.json", {
    "routing_method": "Explicit workflow selection and successful skill read; not naturalistic task trigger rate",
    "routing": routing, "behavior": behavior, "subjective": subjective,
    "judges_completed": len(judges), "judge_label_mapping": mapping,
    "final_targeted_probe": probe,
    "regression": read(HERE / "regression-results.json"),
    "limitations": ["One synthetic project, two phases, one run per group/phase; no broad significance claim",
                    "Producer labels anonymized; artifacts may reveal implementation, two reviewers had prior implementation context",
                    "No user label review or human spot-check; no actual external service or ChatGPT web handoff tested",
                    "Behavior tests used recorded frozen v1; later edge-case fixes verified by final deterministic suite",
                    "Brief isolation has regression evidence and paired review; no fabricated 100-point aggregate"],
})
print(json.dumps({"routing": routing, "behavior": {k: {"duration_ms": v["duration_ms"], "usage": v["usage"]} for k, v in behavior.items()}, "subjective": subjective}, ensure_ascii=False, indent=2))
