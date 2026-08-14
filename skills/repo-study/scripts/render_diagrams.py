#!/usr/bin/env python3
"""把 markdown 里的 mermaid 块渲染成 SVG，并在原文插入图片引用。

用法: python3 render_diagrams.py <文档.md> [--outdir 图] [--fmt svg|png]

为什么要落成图片文件：mermaid 代码块只在支持渲染的环境里是图（VSCode
预览、GitHub），贴进飞书就是一坨文本。落成 SVG 后 VSCode 点开能看，
也能直接拖进飞书。代码块保留在原处，改图时改代码块重跑本脚本即可。

图标题从 mermaid 块前一行的 `<!-- fig: 标题 -->` 注释读取，没有就按
序号命名。脚本幂等：已经插过引用的块跳过，重复跑只会刷新 SVG 内容。

npx 首次拉包要走网络，国内直连大概率 ECONNRESET。脚本会自己探测本地
代理端口并带上，探不到就照原样跑一次，失败了会把原因打出来。
"""
from __future__ import annotations  # 系统 python 是 3.9，不支持 X | Y 注解

import argparse
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

FENCE = re.compile(
    r"(?:^[ \t]*<!--[ \t]*fig:[ \t]*(?P<title>[^>]*?)[ \t]*-->[ \t]*\n)?"
    r"^```mermaid[ \t]*\n(?P<body>.*?)^```[ \t]*$",
    re.M | re.S)
# 已插入的图片引用，用来判断幂等
IMG_LINE = re.compile(r"^!\[[^\]]*\]\([^)]*\)[ \t]*$", re.M)
# 常见本地代理端口，按命中率排序
PROXY_PORTS = (7897, 7890, 1087, 10809, 8118, 6152)


def detect_proxy() -> dict:
    """探测本地代理。开着就返回环境变量，没有返回空 dict。"""
    for port in PROXY_PORTS:
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                url = f"http://127.0.0.1:{port}"
                return {"http_proxy": url, "https_proxy": url,
                        "HTTP_PROXY": url, "HTTPS_PROXY": url}
    return {}


def slugify(text: str, index: int) -> str:
    """文件名用。保留中文，去掉路径不友好的字符。"""
    if not text:
        return f"图-{index:02d}"
    clean = re.sub(r'[:：|｜~*?<>/\\"\'\[\]()]+', "", text).strip()
    clean = re.sub(r"\s+", "-", clean)
    return f"{index:02d}-{clean}" if clean else f"图-{index:02d}"


def render_one(src: Path, dst: Path, env: dict) -> str | None:
    """渲染单个 .mmd。成功返回 None，失败返回错误摘要。

    重试一次：npx 首次拉包常在半路 ECONNRESET，包缓存下来后第二次就好。
    """
    cmd = ["npx", "-y", "@mermaid-js/mermaid-cli", "-i", str(src),
           "-o", str(dst)]
    last = ""
    for attempt in (1, 2):
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              env={**os.environ, **env}, timeout=420)
        if proc.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return None
        last = (proc.stderr or proc.stdout or "").strip().splitlines()
        last = last[-1] if last else f"exit {proc.returncode}"
        if attempt == 1:
            print(f"    第 1 次失败（{last[:80]}），重试", file=sys.stderr)
    return last[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("--outdir", default="图")
    ap.add_argument("--fmt", default="svg", choices=("svg", "png"))
    a = ap.parse_args()

    doc = Path(a.doc).expanduser().resolve()
    if not doc.is_file():
        sys.exit(f"文档不存在：{doc}")
    text = doc.read_text(encoding="utf-8")

    blocks = list(FENCE.finditer(text))
    if not blocks:
        sys.exit("文档里没有 mermaid 块")

    outdir = doc.parent / a.outdir
    outdir.mkdir(exist_ok=True)
    env = detect_proxy()
    print(f"{len(blocks)} 个 mermaid 块，代理："
          f"{env.get('https_proxy', '未探测到，直连')}")

    tmp = outdir / ".tmp.mmd"
    edits, failed = [], []
    for i, m in enumerate(blocks, 1):
        title = (m.group("title") or "").strip()
        name = slugify(title, i)
        dst = outdir / f"{name}.{a.fmt}"

        tmp.write_text(m.group("body"), encoding="utf-8")
        err = render_one(tmp, dst, env)
        if err:
            failed.append((i, title or f"第 {i} 块", err))
            print(f"  [{i}] 失败：{err}", file=sys.stderr)
            continue
        print(f"  [{i}] {dst.name}  {dst.stat().st_size // 1024} KB")

        # 幂等：块前面已经有图片引用就不再插
        head = text[max(0, m.start() - 300):m.start()]
        if IMG_LINE.search(head):
            continue
        alt = title or f"图 {i}"
        edits.append((m.start(), f"![{alt}]({a.outdir}/{dst.name})\n\n"))

    tmp.unlink(missing_ok=True)

    for pos, snippet in reversed(edits):  # 从后往前插，避免偏移失效
        text = text[:pos] + snippet + text[pos:]
    if edits:
        doc.write_text(text, encoding="utf-8")

    print(f"\n渲染 {len(blocks) - len(failed)}/{len(blocks)}，"
          f"新插入引用 {len(edits)} 处")
    if failed:
        print("失败的块需要人工看 mermaid 语法：", file=sys.stderr)
        for i, t, e in failed:
            print(f"  [{i}] {t} — {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
