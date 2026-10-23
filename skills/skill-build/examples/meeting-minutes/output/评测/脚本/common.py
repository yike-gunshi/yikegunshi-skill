"""评测脚本共用：调用本机 claude CLI。

演示环境用 claude -p 非交互模式。代理地址从环境变量读，没设就不加。
"""

import json
import os
import subprocess
import time
from pathlib import Path

CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")


def _env():
    env = dict(os.environ)
    proxy = os.environ.get("EVAL_PROXY")
    if proxy:
        env.update(HTTP_PROXY=proxy, HTTPS_PROXY=proxy, NO_PROXY="localhost,127.0.0.1,::1")
    return env


def run_claude(prompt, cwd, extra_args, timeout=600, retries=2):
    """跑一次 claude -p，返回 (result_json_or_None, wall_seconds, stderr_tail)。"""
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json", "--no-session-persistence", *extra_args]
    last_err = ""
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            p = subprocess.run(cmd, cwd=cwd, env=_env(), stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=timeout)
            wall = time.time() - t0
            if p.returncode == 0 and p.stdout.strip():
                try:
                    return json.loads(p.stdout), wall, p.stderr[-500:]
                except json.JSONDecodeError:
                    last_err = "bad json: " + p.stdout[:300]
            else:
                last_err = f"rc={p.returncode} {p.stderr[-500:]}"
        except subprocess.TimeoutExpired:
            last_err = "timeout"
        time.sleep(3 * (attempt + 1))
    return None, 0.0, last_err


def meta_of(res, wall):
    if not res:
        return {"error": True}
    u = res.get("usage", {})
    return {
        "duration_ms": res.get("duration_ms"),
        "wall_s": round(wall, 1),
        "num_turns": res.get("num_turns"),
        "total_cost_usd": res.get("total_cost_usd"),
        "input_tokens": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "is_error": res.get("is_error"),
    }


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
