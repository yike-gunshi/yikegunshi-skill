#!/bin/bash
# Adapted from LearnPrompt/partner-skill scripts/delegate-codex.sh (MIT).
set -euo pipefail
python3 - "$@" <<'PY'
import argparse, datetime, hashlib, json, os, re, shlex, signal, subprocess, sys, time
from pathlib import Path

def fail(message):
    raise ValueError(message)

def read(path):
    return path.read_text(errors="replace") if path.is_file() else ""

def meta(job):
    return dict(line.split("=", 1) for line in read(job / "meta").splitlines() if "=" in line)

def git(*args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)

def baseline():
    exclude = ["--", ".", ":(exclude).forge/jobs/**"]
    if is_git:
        names = git("ls-files", "--others", "--exclude-standard", "-z", *exclude)
        diff = git("diff", "HEAD", *exclude) if head else git("diff", "--cached", *exclude) + git("diff", *exclude)
        digest = hashlib.sha256(diff + names)
        for name in names.split(b"\0"):
            if not name:
                continue
            try:
                content = (repo / os.fsdecode(name)).read_bytes()
            except OSError:
                continue  # The filename is already included even if reading fails.
            digest.update(name + b"\0" + hashlib.sha256(content).digest())
        return git("status", "--porcelain"), digest.hexdigest(), names
    digest, names = hashlib.sha256(), []
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if Path(root, d) != jobs and d != ".git")
        for name in sorted(files):
            path = Path(root, name)
            names.append(str(path.relative_to(repo)))
            digest.update(os.fsencode(names[-1]) + b"\0")
            digest.update(path.read_bytes())
    return b"", digest.hexdigest(), b"\0".join(os.fsencode(n) for n in names)

def resolve():
    paths = [os.environ.get("CODEX_DELEGATE_BIN", ""),
             "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
             "/Applications/ChatGPT.app/Contents/Resources/codex"]
    binary = next((str(Path(p).absolute()) for p in paths if p and Path(p).is_file() and os.access(p, os.X_OK)), None)
    if not binary:
        fail("no executable Codex binary; tried: " + ", ".join(p for p in paths if p))
    version = subprocess.check_output([binary, "--version"], env=env, stderr=subprocess.DEVNULL, timeout=10).decode().strip()
    return binary, version

def events(job):
    lines, parsed = read(job / "log.jsonl").splitlines(), []
    for line in lines:
        try:
            event = json.loads(line)
            if isinstance(event, dict):
                parsed.append(event)
        except ValueError:
            pass  # A writer may still be appending the last line.
    return lines, parsed

def processes():
    rows = subprocess.check_output(["ps", "-axo", "pid=,ppid=,stat="]).decode().splitlines()
    return {int(p): (int(parent), state) for p, parent, state in (row.split() for row in rows)}

def alive(pid, table=None):
    table = processes() if table is None else table
    return pid > 1 and pid in table and not table[pid][1].startswith("Z")

def snapshot(job):
    data, (lines, parsed) = meta(job), events(job)
    pid, code = int(read(job / "pid") or 0), read(job / "exit_code").strip()
    elapsed = max(0, int(read(job / "finished_at") or time.time()) - int(data["submitted_at"]))
    age = max(0, int(time.time() - (job / "log.jsonl").stat().st_mtime)) if (job / "log.jsonl").exists() else elapsed
    types = [e.get("type", "") for e in parsed]
    turns = [kind for kind in types if kind.startswith("turn.")]
    session = next((e.get("thread_id", "") for e in parsed if e.get("type") == "thread.started"), "")
    if (job / "cancelled").exists():
        state = "CANCELLED"
    elif code:
        state = "DONE" if code == "0" and "turn.completed" in turns and turns[-1] != "turn.failed" else "FAILED"
    elif not alive(pid):
        state = "FAILED"
    elif not lines:
        state = "STALL_START" if elapsed > stall else "STARTING"
    else:
        state = "IDLE" if age > args.idle else "RUNNING"
    return dict(state=state, elapsed_s=elapsed, events=len(lines), last_event_type=types[-1] if types else "",
                last_event_age_s=age, session_id=session, exit_code=code)

def launch(parent=None):
    if not Path(args.prompt_file).is_file() or not Path(args.prompt_file).stat().st_size:
        fail("prompt file must exist and be nonempty")
    prompt = Path(args.prompt_file).read_bytes()
    label, sandbox, session, mode = args.label, "read-only" if args.read_only else "workspace-write", "", "fresh"
    if parent:
        if alive(int(read(parent / "pid") or 0)) and not (parent / "exit_code").exists():
            fail("parent job is still running; wait or cancel first")
        session = snapshot(parent)["session_id"]
        if not session:
            fail("no session_id in parent log.jsonl")
        sandbox, mode, chain, rounds = meta(parent)["sandbox"], "resume", parent, 0
        seen = set()
        while meta(chain).get("parent"):
            if chain in seen:
                fail("invalid parent chain")
            seen.add(chain)
            rounds += 1
            chain = require_job(meta(chain)["parent"])
        label = meta(chain)["label"] + "-r" + str(rounds + 1)
    label = re.sub(r"[^A-Za-z0-9._-]", "", label)
    if not label:
        fail("label must contain at least one ASCII letter, digit, dot, underscore or hyphen")
    binary, version = resolve()
    jobs.mkdir(parents=True, exist_ok=True)
    while True:
        job = jobs / (time.strftime("%Y%m%d-%H%M%S-") + label)
        try:
            job.mkdir()
            break
        except FileExistsError:
            time.sleep(0.1)
    status, digest, names = baseline()
    (job / "prompt.md").write_bytes(prompt)
    (job / "baseline.status").write_bytes(status)
    (job / "baseline.diffhash").write_text(digest + "\n")
    (job / "baseline.untracked").write_bytes(names)
    data = dict(id=job.name, label=label, repo=str(repo), mode=mode, parent=parent.name if parent else "",
                sandbox=sandbox, model=args.model or "", effort=args.effort or "", codex_bin=binary,
                codex_version=version, submitted_at=int(time.time()), git_head=head,
                skip_git_repo_check=str(not is_git).lower())
    (job / "meta").write_text("".join(str(k) + "=" + str(v) + "\n" for k, v in data.items()))
    command = [binary, "exec"]
    if parent:
        command += ["resume", session, "--json", "-o", str(job / "last_message.md"), "-c", "sandbox_mode=" + json.dumps(sandbox)]
    else:
        command += ["--json", "-s", sandbox, "-C", str(repo), "-o", str(job / "last_message.md")]
        if args.model:
            command += ["-m", args.model]
    if args.effort:
        command += ["-c", "model_reasoning_effort=" + json.dumps(args.effort)]
    if not is_git:
        command += ["--skip-git-repo-check"]
    quote = shlex.quote
    worker = "#!/bin/bash\ncd " + quote(str(repo)) + " || exit 1\n"
    worker += " ".join(quote(v) for v in command + ["-"]) + " < " + quote(str(job / "prompt.md"))
    worker += " > " + quote(str(job / "log.jsonl")) + " 2> " + quote(str(job / "stderr.log")) + "\ncode=$?\n"
    worker += "date -u +%s > " + quote(str(job / "finished_at")) + "\nprintf '%s\\n' \"$code\" > " + quote(str(job / "exit_code")) + "\n"
    (job / "run.sh").write_text(worker)
    launcher = 'nohup /bin/bash "$1" </dev/null >/dev/null 2>&1 & echo $!'
    pid = subprocess.check_output(["/bin/bash", "-c", launcher, "delegate", str(job / "run.sh")], env=env)
    (job / "pid").write_bytes(pid)
    print(job.name)

def require_job(job_id):
    if not re.fullmatch(r"[A-Za-z0-9._-]+", job_id) or job_id in (".", "..") or not (jobs / job_id).is_dir():
        fail("job not found or invalid jobId: " + job_id)
    return jobs / job_id

def cancel(job):
    pid = int(read(job / "pid") or 0)
    if (job / "exit_code").exists() or not alive(pid) or (job / "cancelled").exists():
        print("already finished: " + job.name)
        return
    (job / "cancelled").touch()
    table, targets = processes(), [pid]
    for target in targets:
        targets.extend(p for p in table if table[p][0] == target and p not in targets)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for target in reversed(targets):
            if alive(target):
                try:
                    os.kill(target, sig)
                except ProcessLookupError:
                    pass
        if sig == signal.SIGTERM:
            time.sleep(3)
    print("cancelled: " + job.name)

parser = argparse.ArgumentParser(description="Background Codex jobs under <repo>/.forge/jobs/")
subs = parser.add_subparsers(dest="cmd", required=True)
for name in ("submit", "status", "result", "resume", "cancel", "list", "doctor"):
    sub = subs.add_parser(name)
    sub.set_defaults(idle=600, label="", read_only=False, model=None, effort=None)
    if name != "doctor":
        sub.add_argument("--repo", required=True)
    if name in ("status", "result", "resume", "cancel"):
        sub.add_argument("job_id")
    if name in ("submit", "resume"):
        sub.add_argument("--prompt-file", required=True)
        sub.add_argument("--effort")
    if name == "submit":
        sub.add_argument("--label", required=True)
        sub.add_argument("--model")
        sub.add_argument("--read-only", action="store_true")
    if name == "status":
        sub.add_argument("--wait", action="store_true")
        sub.add_argument("--timeout", type=float, default=600)
        sub.add_argument("--idle", type=float, default=600)
args = parser.parse_args()
try:
    if any("\n" in v or "\r" in v for v in vars(args).values() if isinstance(v, str)):
        fail("arguments must not contain newlines")
    if args.model == "" or args.effort == "":
        fail("model and effort overrides must not be empty")
    stall, poll = float(os.environ.get("CODEX_DELEGATE_START_STALL_S", "90")), float(os.environ.get("CODEX_DELEGATE_POLL_S", "5"))
    if not (stall >= 0 and 0 < poll < float("inf") and args.idle >= 0 and getattr(args, "timeout", 0) >= 0):
        fail("invalid timing settings")
    proxy, env = os.environ.get("CODEX_DELEGATE_PROXY", "http://127.0.0.1:7897"), os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env[key] = proxy
    env["NO_PROXY"] = env["no_proxy"] = "localhost,127.0.0.1,::1"
    if args.cmd == "doctor":
        binary, version = resolve()
        print("codex_bin: " + binary + "\ncodex_version: " + version + "\nproxy: " + (proxy or "(disabled)"), flush=True)
        probe = subprocess.run(["curl", "--proxy", proxy, "--max-time", "10", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "https://chatgpt.com/"], env=env, capture_output=True, text=True)
        print("http_status: " + probe.stdout)
        sys.exit(0 if probe.returncode == 0 else 1)
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        fail("repo not found: " + str(repo))
    jobs = repo / ".forge/jobs"
    is_git = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"], capture_output=True, text=True).stdout.strip() if is_git else ""
    job = require_job(args.job_id) if hasattr(args, "job_id") else None
    if args.cmd in ("submit", "resume"):
        launch(job)
    elif args.cmd == "status":
        deadline = time.monotonic() + args.timeout
        while True:
            info = snapshot(job)
            if not args.wait or info["state"] in ("DONE", "FAILED", "CANCELLED", "STALL_START") or time.monotonic() >= deadline:
                break
            time.sleep(min(poll, max(0, deadline - time.monotonic())))
        print("\n".join(str(k) + ": " + str(v) for k, v in info.items()))
        if args.wait:
            sys.exit({"DONE": 0, "FAILED": 1, "CANCELLED": 1, "STALL_START": 3}.get(info["state"], 2))
    elif args.cmd == "cancel":
        cancel(job)
    elif args.cmd == "list":
        for entry in sorted(jobs.iterdir()) if jobs.is_dir() else []:
            if entry.is_dir() and (entry / "meta").is_file():
                data, info = meta(entry), snapshot(entry)
                print(entry.name, info["state"], data["mode"], data["parent"] or "-", str(info["elapsed_s"]) + "s", sep="\t")
    elif args.cmd == "result":
        if snapshot(job)["state"] not in ("DONE", "FAILED", "CANCELLED"):
            fail("job has not reached a terminal state")
        messages = [e["item"].get("text", "") for e in events(job)[1] if e.get("type") == "item.completed" and isinstance(e.get("item"), dict) and e["item"].get("type") == "agent_message"]
        print(read(job / "last_message.md") if (job / "last_message.md").is_file() else (messages[-1] if messages else ""))
        print("--- git diff --stat vs HEAD ---")
        if read(job / "baseline.status"):
            print("NOTE: baseline was dirty, see baseline.status")
        _, digest, names = baseline()
        if is_git:
            print(git("diff", *(["HEAD"] if head else []), "--stat", "--", ".", ":(exclude).forge/jobs/**").decode(), end="")
        old = set((job / "baseline.untracked").read_bytes().split(b"\0"))
        for name in names.split(b"\0"):
            if name and name not in old:
                print("untracked: " + os.fsdecode(name))
        if digest == read(job / "baseline.diffhash").strip() and meta(job)["sandbox"] != "read-only":
            print("WARNING: EMPTY_DIFF")
        blocked = [line for line in read(job / "stderr.log").splitlines() if re.search(r"read-only sandbox|Operation not permitted|blocked by", line, re.I)]
        if blocked:
            print("WARNING: SANDBOX_BLOCK\n" + "\n".join(blocked))
except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
    print("ERROR: " + str(error), file=sys.stderr)
    sys.exit(1)
PY
