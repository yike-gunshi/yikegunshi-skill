#!/usr/bin/env python3
"""Locate the feishu-export toolchain and app credentials, emit shell exports.

Credentials are never stored in this skill. They are read at call time from the
Feishu MCP server entry in an .mcp.json that already exists on the machine.

Usage:
    eval "$(python3 scripts/feishu_env.py)"        # load into the current shell
    python3 scripts/feishu_env.py --check          # report what was found, values masked

Options:
    --config PATH     .mcp.json to read (default: search upward from cwd, then $HOME)
    --export-home P   toolchain dir (default: search for one containing bin/feishu-cli)
"""

import argparse
import json
import os
import sys
from pathlib import Path

SEARCH_ROOTS = ["FEISHU_EXPORT_HOME", "CLAUDE_PROJECT_DIR"]


def find_upward(start, name):
    cur = Path(start).resolve()
    for d in [cur, *cur.parents]:
        p = d / name
        if p.is_file():
            return p
    return None


def find_mcp_config(explicit):
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.is_file() else None
    for env in SEARCH_ROOTS:
        base = os.environ.get(env)
        if base and (Path(base) / ".mcp.json").is_file():
            return Path(base) / ".mcp.json"
    found = find_upward(Path.cwd(), ".mcp.json")
    if found:
        return found
    for cand in (Path.home() / ".mcp.json", Path.home() / ".claude" / ".mcp.json"):
        if cand.is_file():
            return cand
    return None


def read_credentials(cfg):
    """Pull -a / -s out of the feishu MCP server's argv."""
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return None, None, f"{cfg} 读不出来: {e}"

    servers = data.get("mcpServers", {})
    entry = servers.get("feishu") or servers.get("lark")
    if not entry:
        return None, None, f"{cfg} 里没有 feishu / lark MCP server"

    args = entry.get("args", [])
    app_id = app_secret = None
    for i, a in enumerate(args[:-1]):
        if a in ("-a", "--app-id"):
            app_id = args[i + 1]
        elif a in ("-s", "--app-secret"):
            app_secret = args[i + 1]
    if not (app_id and app_secret):
        return None, None, f"{cfg} 的 feishu server 参数里找不到 -a / -s"
    return app_id, app_secret, None


def find_export_home(explicit):
    if explicit:
        p = Path(explicit).expanduser()
        return p if (p / "bin" / "feishu-cli").exists() else None
    env = os.environ.get("FEISHU_EXPORT_HOME")
    if env and (Path(env) / "bin" / "feishu-cli").exists():
        return Path(env)
    roots = [Path.cwd(), *Path.cwd().parents][:5]
    base = os.environ.get("CLAUDE_PROJECT_DIR")
    if base:
        roots.insert(0, Path(base))
    for root in roots:
        for cand in root.glob("*/feishu-export"):
            if (cand / "bin" / "feishu-cli").exists():
                return cand
        cand = root / "feishu-export"
        if (cand / "bin" / "feishu-cli").exists():
            return cand
    return None


def mask(v):
    return f"{v[:7]}…{v[-3:]}" if v and len(v) > 12 else "set"


def main():
    ap = argparse.ArgumentParser(description="载入飞书导出所需的环境变量")
    ap.add_argument("--config")
    ap.add_argument("--export-home")
    ap.add_argument("--check", action="store_true", help="只报告找到了什么，不打印明文")
    args = ap.parse_args()

    cfg = find_mcp_config(args.config)
    if not cfg:
        print("找不到 .mcp.json。用 --config 指定，或确认飞书 MCP 已配置。", file=sys.stderr)
        return 1

    app_id, app_secret, err = read_credentials(cfg)
    if err:
        print(err, file=sys.stderr)
        return 1

    home = find_export_home(args.export_home)
    token = Path.home() / ".feishu-cli" / "token.json"

    if args.check:
        print(f"配置文件      {cfg}")
        print(f"FEISHU_APP_ID {mask(app_id)}")
        print(f"APP_SECRET    {'已配置' if app_secret else '缺失'}")  # 不露任何前缀
        print(f"EXPORT_HOME   {home or '未找到 —— 用 --export-home 指定含 bin/feishu-cli 的目录'}")
        print(f"User Token    {'有' if token.is_file() else '缺失，需要跑 auth login'} ({token})")
        return 0 if home else 1

    print(f"export FEISHU_APP_ID={app_id}")
    print(f"export FEISHU_APP_SECRET={app_secret}")
    if home:
        print(f"export FEISHU_EXPORT_HOME={home}")
    else:
        print("# FEISHU_EXPORT_HOME 未找到，手动 export 指向含 bin/feishu-cli 的目录", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
