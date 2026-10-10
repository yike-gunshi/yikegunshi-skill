#!/bin/bash
set -euo pipefail
python3 - "$(cd "$(dirname "$0")" && pwd)/delegate.sh" <<'PY'
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

script, case = Path(sys.argv[1]), "setup"
fresh = r'''{"type":"thread.started","thread_id":"01a1254c-6c2e-7eb3-bf71-da0a48a7abf3"}
{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Under-development features enabled: chronicle. Under-development features are incomplete and may behave unpredictably. To suppress this warning, set `suppress_unstable_features_warning = true` in /Users/dbwu/.codex/config.toml."}}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"我会把 a.txt 的内容改成 world。\n"}}
{"type":"item.started","item":{"id":"item_2","type":"command_execution","command":"/bin/zsh -lc \"printf 'world' > a.txt\"","aggregated_output":"","exit_code":null,"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_2","type":"command_execution","command":"/bin/zsh -lc \"printf 'world' > a.txt\"","aggregated_output":"","exit_code":0,"status":"completed"}}
{"type":"item.completed","item":{"id":"item_3","type":"agent_message","text":"改好了"}}
{"type":"turn.completed","usage":{"input_tokens":50109,"cached_input_tokens":38016,"cache_write_input_tokens":0,"output_tokens":57,"reasoning_output_tokens":0}}
'''
resume = r'''{"type":"thread.started","thread_id":"01a1254c-6c2e-7eb3-bf71-da0a48a7abf3"}
{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Under-development features enabled: chronicle. Under-development features are incomplete and may behave unpredictably. To suppress this warning, set `suppress_unstable_features_warning = true` in /Users/dbwu/.codex/config.toml."}}
{"type":"turn.started"}
{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"/bin/zsh -lc \"printf '\\\\nagain' >> a.txt\"","aggregated_output":"","exit_code":null,"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"/bin/zsh -lc \"printf '\\\\nagain' >> a.txt\"","aggregated_output":"","exit_code":0,"status":"completed"}}
{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"好了"}}
{"type":"turn.completed","usage":{"input_tokens":100484,"cached_input_tokens":87936,"cache_write_input_tokens":0,"output_tokens":96,"reasoning_output_tokens":0}}
'''
stderr = r'''Reading additional input from stdin...
2026-10-10T10:12:10.646390Z ERROR codex_core::session::session: failed to load skill /Users/dbwu/.agents/skills/sync-test/SKILL.md: missing YAML frontmatter delimited by ---
2026-10-10T10:12:10.646417Z ERROR codex_core::session::session: failed to load skill /Users/dbwu/claudecode_workspace/Skill/yikegunshi-skill/skills/wechat-publisher/SKILL.md: missing YAML frontmatter delimited by ---
2026-10-10T10:12:11.870036Z ERROR codex_core::session::session: failed to load skill /Users/dbwu/.agents/skills/sync-test/SKILL.md: missing YAML frontmatter delimited by ---
2026-10-10T10:12:11.870065Z ERROR codex_core::session::session: failed to load skill /Users/dbwu/claudecode_workspace/Skill/yikegunshi-skill/skills/wechat-publisher/SKILL.md: missing YAML frontmatter delimited by ---
'''
stub_code = '''#!/usr/bin/env python3
import json, os, signal, subprocess, sys, time
from pathlib import Path
if sys.argv[1] == "--version":
    print("codex-cli 0.162.0-alpha.2 stub")
    sys.exit(0)
if sys.argv[1] in ("--child", "--grandchild"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    job = Path(sys.argv[2])
    (job / (sys.argv[1][2:] + ".pid")).write_text(str(os.getpid()))
    if sys.argv[1] == "--child":
        subprocess.Popen([sys.executable, __file__, "--grandchild", str(job)])
    time.sleep(120)
    sys.exit(0)
argv = sys.argv[1:]
job = Path(argv[argv.index("-o") + 1]).parent
(job / "stub.pid").write_text(str(os.getpid()))
prompt = sys.stdin.read()  # Must receive EOF, including in the background.
(job / "received.json").write_text(json.dumps(dict(argv=argv, stdin=prompt, cwd=os.getcwd(), env=dict(os.environ))))
sys.stderr.write((Path(__file__).parent / "stderr.log").read_text())
if prompt == "start":
    time.sleep(120)
data = (Path(__file__).parent / ("resume.jsonl" if "resume" in argv else "fresh.jsonl")).read_text()
if prompt == "recoverable_error":
    print("\\n".join(data.splitlines()[:3]), flush=True)
    print('{"type":"error","message":"temporary connection failure"}', flush=True)
    print('{"type":"turn.failed","error":{"message":"temporary failure"}}', flush=True)
    (job / "recovering").touch()
    while not (job / "continue").exists():
        time.sleep(0.05)
if prompt == "recovered_turn":
    data = '{"type":"turn.failed","error":{"message":"temporary failure"}}\\n' + data
if prompt == "tree":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    subprocess.Popen([sys.executable, __file__, "--child", str(job)])
    print("\\n".join(data.splitlines()[:3]), flush=True)
    time.sleep(120)
if prompt == "turnfailed":
    data += '{"type":"turn.failed","error":{"message":"stub failure"}}\\n'
if prompt == "error":
    data += '{"type":"error","message":"stub failure"}\\n'
if prompt == "missing_turn":
    data = "\\n".join(data.splitlines()[:-1]) + "\\n"
if prompt == "sandbox":
    print("READ-ONLY SANDBOX: Operation not permitted; blocked by policy", file=sys.stderr)
if prompt == "change":
    Path("a.txt").write_text("world")
    Path("new file.txt").write_text("new")
if prompt == "untracked_new":
    Path("tests").mkdir(exist_ok=True)
    Path("tests/x.py").write_text("before")
if prompt == "untracked_edit":
    Path("tests/x.py").write_text("after")
print(data, end="", flush=True)
(job / "last_message.md").write_text("FILE RESULT")
sys.exit(7 if prompt == "exit7" else 0)
'''

def check(condition, detail):
    if not condition:
        raise AssertionError(detail)

with tempfile.TemporaryDirectory(prefix="codex-delegate-") as directory:
    root = Path(directory)
    repo = root / "repo with spaces"
    repo.mkdir()
    stub = root / "fake codex"
    stub.write_text(stub_code)
    stub.chmod(0o755)
    (root / "fresh.jsonl").write_text(fresh)
    (root / "resume.jsonl").write_text(resume)
    (root / "stderr.log").write_text(stderr)
    for fixture in (fresh, resume):
        for line in fixture.splitlines():
            json.loads(line)
    try:
        subprocess.check_output(["ps", "-axo", "pid=,ppid=,stat="], stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        # Only registered test processes are exposed when the sandbox denies ps.
        ps = root / "ps"
        ps.write_text('''#!/usr/bin/env python3
import os, sys
from pathlib import Path
for job in Path(__file__).parent.glob("*/.forge/jobs/*"):
    parent = 0
    for name in ("pid", "stub.pid", "child.pid", "grandchild.pid"):
        try:
            pid = int((job / name).read_text())
            os.kill(pid, 0)
            print(pid, parent, "S") if "pid=,ppid=,stat=" in sys.argv else print(pid, "S")
            parent = pid
        except (OSError, ValueError):
            pass
''')
        ps.chmod(0o755)
    env = dict(os.environ, PATH=str(root) + ":" + os.environ["PATH"], CODEX_DELEGATE_BIN=str(stub), CODEX_DELEGATE_POLL_S="0.05", CODEX_DELEGATE_START_STALL_S="90")
    env.pop("CODEX_DELEGATE_PROXY", None)
    prompt, jobs = root / "prompt.md", repo / ".forge/jobs"
    def run(*argv, code=0, custom=None, target=script):
        result = subprocess.run(["/bin/bash", str(target), *map(str, argv)], env=custom or env, capture_output=True, text=True, timeout=12)
        check(result.returncode == code, f"{argv}: expected {code}, got {result.returncode}: {result.stdout} {result.stderr}")
        return result.stdout if result.stdout else result.stderr
    def submit(text, *flags, target_repo=repo):
        prompt.write_text(text)
        return run("submit", "--repo", target_repo, "--prompt-file", prompt, "--label", "task!?", *flags).strip()
    def status(job, state, *flags, code=0, custom=None):
        output = run("status", job, "--repo", repo, *flags, code=code, custom=custom)
        check(f"state: {state}\n" in output, output)
        return output
    def result(job):
        return run("result", job, "--repo", repo)
    def received(job):
        return json.loads((jobs / job / "received.json").read_text())
    def ready(job, name):
        deadline = time.monotonic() + 5
        while not (jobs / job / name).exists():
            check(time.monotonic() < deadline, "stub did not reach " + name)
            time.sleep(0.05)
    try:
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "a.txt").write_text("hello")
        subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Stub", "-c", "user.email=stub@example.test", "commit", "-qm", "baseline"], check=True)
        case = "submit, EOF, default arguments, warning events, result fallback"
        first = submit("plain")
        output = status(first, "DONE", "--wait", "--timeout", 3)
        got = received(first)
        check(got["stdin"] == "plain" and got["argv"][-1] == "-", "prompt did not reach EOF")
        check(got["argv"][:4] == ["exec", "--json", "-s", "workspace-write"] and "-m" not in got["argv"] and "-c" not in got["argv"], "fresh/default flags")
        check(all(got["env"][key] == "http://127.0.0.1:7897" for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")) and got["env"]["NO_PROXY"] == "localhost,127.0.0.1,::1", "proxy defaults")
        check("events: 8\n" in output and "last_event_type: turn.completed\n" in output and "exit_code: 0\n" in output, "status fields")
        check("FILE RESULT" in result(first) and "WARNING: EMPTY_DIFF" in result(first), "preferred result or empty diff")
        check("--- git diff --stat vs HEAD ---" in result(first) and "NOTE: baseline was dirty" not in result(first), "clean baseline result heading/note")
        (jobs / first / "last_message.md").unlink()
        check(result(first).startswith("改好了\n"), "last agent_message fallback")
        run("cancel", first, "--repo", repo)
        status(first, "DONE")
        print("PASS submit, EOF, fixtures and result")

        case = "explicit overrides, read-only, sandbox warning, changes, non-git"
        ro = submit("sandbox", "--read-only", "--model", "model with spaces", "--effort", "high")
        status(ro, "DONE", "--wait", "--timeout", 3)
        argv = received(ro)["argv"]
        check(argv[argv.index("-s") + 1] == "read-only" and argv[argv.index("-m") + 1] == "model with spaces" and 'model_reasoning_effort="high"' in argv, "explicit overrides")
        check("WARNING: SANDBOX_BLOCK" in result(ro) and "READ-ONLY SANDBOX" in result(ro) and "EMPTY_DIFF" not in result(ro), "sandbox warning or read-only empty diff")
        changed = submit("change")
        status(changed, "DONE", "--wait", "--timeout", 3)
        check("a.txt" in result(changed) and "untracked: new file.txt" in result(changed) and "EMPTY_DIFF" not in result(changed), "change detection")
        nongit = root / "non git"
        nongit.mkdir()
        ng = submit("plain", target_repo=nongit)
        run("status", ng, "--repo", nongit, "--wait", "--timeout", 3)
        check("--skip-git-repo-check" in json.loads((nongit / ".forge/jobs" / ng / "received.json").read_text())["argv"], "non-git flag")
        check("skip_git_repo_check=true" in (nongit / ".forge/jobs" / ng / "meta").read_text(), "non-git metadata")
        print("PASS overrides, sandbox, changes and non-git")

        case = "failures and wait exit codes"
        for mode, expected in (("exit7", "FAILED"), ("turnfailed", "FAILED"), ("error", "DONE"), ("missing_turn", "FAILED"), ("recovered_turn", "DONE")):
            case = "failures and wait exit codes: " + mode
            bad = submit(mode)
            status(bad, expected, "--wait", "--timeout", 3, code=1 if expected == "FAILED" else 0)
            status(bad, expected)
        case = "live recoverable error does not fail or end status --wait early"
        recovering = submit("recoverable_error")
        ready(recovering, "recovering")
        check(not (jobs / recovering / "exit_code").exists(), "recovering stub already exited")
        status(recovering, "RUNNING")
        waited_at = time.monotonic()
        status(recovering, "RUNNING", "--wait", "--timeout", 0.2, code=2)
        check(time.monotonic() - waited_at >= 0.2, "status --wait returned before timeout")
        (jobs / recovering / "continue").touch()
        ready(recovering, "exit_code")
        status(recovering, "DONE", "--wait", "--timeout", 3)
        print("PASS live recoverable errors and eventual completion")
        dead = jobs / "20000101-000000-dead"
        shutil.copytree(jobs / first, dead)
        (dead / "pid").write_text("99999999")
        (dead / "exit_code").unlink()
        status(dead.name, "FAILED", "--wait", code=1)
        case = "STARTING, STALL_START and wait=3"
        start = submit("start")
        ready(start, "received.json")
        status(start, "STARTING")
        path = jobs / start / "meta"
        path.write_text(path.read_text().replace(next(line for line in path.read_text().splitlines() if line.startswith("submitted_at=")), "submitted_at=" + str(int(time.time()) - 4)))
        status(start, "STARTING")
        status(start, "STALL_START", "--wait", code=3, custom=dict(env, CODEX_DELEGATE_START_STALL_S="1"))
        run("cancel", start, "--repo", repo)
        status(start, "CANCELLED", "--wait", code=1)
        print("PASS states and wait exit codes")

        case = "resume, parent chain, fresh baseline, inherited sandbox"
        prompt.write_text("plain")
        for parent, suffix, flags in ((changed, "-task-r1", ()), (ro, "-task-r1", ("--effort", "low"))):
            child = run("resume", parent, "--repo", repo, "--prompt-file", prompt, *flags).strip()
            status(child, "DONE", "--wait", "--timeout", 3)
            got, metadata = received(child), (jobs / child / "meta").read_text()
            check(child.endswith(suffix) and "mode=resume" in metadata and "parent=" + parent in metadata, "resume chain metadata")
            check(got["argv"][:3] == ["exec", "resume", "01a1254c-6c2e-7eb3-bf71-da0a48a7abf3"] and "-s" not in got["argv"] and "-C" not in got["argv"] and got["cwd"] == str(repo.resolve()), "resume command and cwd")
            check(('sandbox_mode="read-only"' if parent == ro else 'sandbox_mode="workspace-write"') in got["argv"], "sandbox inheritance")
            check(('model_reasoning_effort="low"' in got["argv"]) == bool(flags), "resume effort only when explicit")
            if parent == changed:
                check("EMPTY_DIFF" in result(child), "resume baseline was not refreshed")
                check("NOTE: baseline was dirty, see baseline.status" in result(child), "dirty baseline note")
        grand = run("resume", child, "--repo", repo, "--prompt-file", prompt).strip()
        status(grand, "DONE", "--wait", "--timeout", 3)
        check(grand.endswith("-task-r2"), "second resume round")
        print("PASS resume session, sandbox and baseline")

        case = "resume detects untracked content changes and unchanged content"
        created = submit("untracked_new")
        status(created, "DONE", "--wait", "--timeout", 3)
        check((repo / "tests/x.py").read_text() == "before", "fresh stub did not create untracked file")
        prompt.write_text("untracked_edit")
        edited = run("resume", created, "--repo", repo, "--prompt-file", prompt).strip()
        status(edited, "DONE", "--wait", "--timeout", 3)
        check((repo / "tests/x.py").read_text() == "after", "resume stub did not edit untracked file")
        check("EMPTY_DIFF" not in result(edited), "untracked content change reported EMPTY_DIFF")
        prompt.write_text("plain")
        unchanged = run("resume", edited, "--repo", repo, "--prompt-file", prompt).strip()
        status(unchanged, "DONE", "--wait", "--timeout", 3)
        check("WARNING: EMPTY_DIFF" in result(unchanged), "unchanged untracked content did not report EMPTY_DIFF")
        print("PASS untracked content changes and unchanged resume")

        case = "RUNNING, IDLE, timeout=2, cancellation of TERM-resistant descendants"
        tree = submit("tree")
        ready(tree, "grandchild.pid")
        status(tree, "RUNNING")
        os.utime(jobs / tree / "log.jsonl", (time.time() - 10, time.time() - 10))
        status(tree, "IDLE", "--idle", 1)
        status(tree, "IDLE", "--idle", 1, "--wait", "--timeout", 0.1, code=2)
        run("result", tree, "--repo", repo, code=1)
        run("resume", tree, "--repo", repo, "--prompt-file", prompt, code=1)
        pids = [int((jobs / tree / name).read_text()) for name in ("pid", "stub.pid", "child.pid", "grandchild.pid")]
        run("cancel", tree, "--repo", repo)
        status(tree, "CANCELLED", "--wait", code=1)
        table = subprocess.check_output(["ps", "-axo", "pid=,stat="], env=env).decode().splitlines()
        live = {int(p) for p, state in (line.split() for line in table) if not state.startswith("Z")}
        check(not any(pid in live for pid in pids), "cancel left a live descendant")
        print("PASS idle, timeout and cancel process tree")

        case = "doctor, binary resolution without PATH, proxy override, invalid input, list"
        curl = root / "curl"
        curl.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$DOCTOR_ARGS"\nprintf 403\n')
        curl.chmod(0o755)
        poison = root / "codex"
        poison.write_text('#!/bin/bash\ntouch "$POISON_MARKER"\nexit 99\n')
        poison.chmod(0o755)
        doctor_env = dict(env, PATH=str(root) + ":" + env["PATH"], DOCTOR_ARGS=str(root / "curl.args"), POISON_MARKER=str(root / "poison"), CODEX_DELEGATE_PROXY="")
        check("http_status: 403" in run("doctor", custom=doctor_env), "doctor HTTP reachability")
        check("--max-time\n10\n" in (root / "curl.args").read_text() and "https://chatgpt.com/" in (root / "curl.args").read_text(), "doctor curl timeout/target")
        prompt.write_text("plain")
        disabled = run("submit", "--repo", repo, "--prompt-file", prompt, "--label", "no-proxy", custom=doctor_env).strip()
        status(disabled, "DONE", "--wait", "--timeout", 3)
        check(received(disabled)["env"]["HTTPS_PROXY"] == "", "explicitly disabled proxy")
        copy = root / "resolver.sh"
        first_bin, old_bin = root / "new-bin", root / "old-bin"
        copy.write_text(script.read_text().replace("/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex", str(first_bin)).replace("/Applications/ChatGPT.app/Contents/Resources/codex", str(old_bin)))
        fallback_env = dict(doctor_env, CODEX_DELEGATE_BIN=str(root / "missing"))
        first_bin.symlink_to(stub)
        old_bin.symlink_to(stub)
        check("codex_bin: " + str(first_bin) in run("doctor", custom=fallback_env, target=copy), "new bundled binary priority")
        first_bin.unlink()
        check("codex_bin: " + str(old_bin) in run("doctor", custom=fallback_env, target=copy), "old bundled binary fallback")
        old_bin.unlink()
        run("doctor", custom=fallback_env, target=copy, code=1)
        check(not (root / "poison").exists(), "resolver fell back to PATH")
        (dead / "log.jsonl").write_text("")
        run("resume", dead.name, "--repo", repo, "--prompt-file", prompt, code=1)
        prompt.write_text("")
        run("submit", "--repo", repo, "--prompt-file", prompt, "--label", "empty", code=1)
        run("list", "--repo", root / "missing", code=1)
        run("status", "../escape", "--repo", repo, code=1)
        run("submit", "--repo", repo, "--model", code=2)
        run("status", first, "--repo", repo, "--timeout", -1, code=1)
        rows = run("list", "--repo", repo).splitlines()
        check(rows == sorted(rows) and any("\tresume\t" in row for row in rows) and any("\tCANCELLED\t" in row for row in rows), "list ordering/fields")
        print("PASS doctor, resolver, proxy, errors and list")
    except Exception as error:
        print("SELFTEST FAIL [" + case + "]: " + str(error), file=sys.stderr)
        sys.exit(1)
    finally:
        for base in root.glob("*/.forge/jobs"):
            for job in base.iterdir():
                if job.is_dir() and (job / "pid").exists():
                    subprocess.run(["/bin/bash", str(script), "cancel", job.name, "--repo", base.parent.parent], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
print("SELFTEST PASS")
PY
