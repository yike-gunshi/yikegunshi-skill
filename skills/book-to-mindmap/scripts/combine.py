#!/usr/bin/env python3
"""把多章真源合并成一个多画布的 .xmind，一章一张画布

用法: python3 combine.py 输出.xmind [折叠层深] -- 第1章.md 第2章.md ...

各章的 .md 仍是唯一真源，本脚本不改它们，只是拼出一个临时的合并文件交给
md2xmind。加一章就在命令行末尾多加一个文件，顺序即画布顺序。
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def sheet_title(path):
    """用真源的根节点作画布名"""
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^-\s+(.*\S)\s*$", line)
        if m:
            return m.group(1)
    return os.path.splitext(os.path.basename(path))[0]


def main():
    args = sys.argv[1:]
    if "--" not in args:
        sys.exit("用法: combine.py 输出.xmind [折叠层深] -- 第1章.md 第2章.md ...")
    head, files = args[:args.index("--")], args[args.index("--") + 1:]
    out = head[0]
    fold = head[1] if len(head) > 1 else None
    if not files:
        sys.exit("没有输入文件")

    parts = []
    for f in files:
        parts.append(f"# {sheet_title(f)}")
        parts.append(open(f, encoding="utf-8").read())
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as tmp:
        tmp.write("\n".join(parts))
        merged = tmp.name

    cmd = [sys.executable, os.path.join(HERE, "md2xmind.py"), merged, out]
    if fold:
        cmd.append(fold)
    subprocess.run(cmd, check=True)
    os.unlink(merged)
    print(f"{len(files)} 张画布 -> {out}")


if __name__ == "__main__":
    main()
