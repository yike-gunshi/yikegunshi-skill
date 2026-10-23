#!/usr/bin/env python3
"""重建 prompt-vault 仓库根 README.md 总索引。

用法: python3 build_index.py <仓库根目录>

扫描各分类目录下的 *.md（跳过 README.md 与 assets/），读 frontmatter 的
title/summary/tags/media/model，生成按分类分节的索引表。
frontmatter 解析失败的文件会报错退出（exit 1），修完再跑。
"""
import re
import sys
from datetime import date
from pathlib import Path

# 已知分类的展示名与排序；未列出的目录排在其后，用目录名展示
KNOWN = [
    ("thinking", "🧠 深度思考"),
    ("product", "🧩 产品 · 原型"),
    ("image-gen", "🎨 生图"),
    ("video-gen", "🎬 生视频 · 音频"),
    ("writing", "✍️ 写作文案"),
    ("coding", "💻 编码开发"),
    ("agent", "🤖 Agent · 系统 Prompt"),
]
SKIP_DIRS = {".git", ".github", "assets", "_open", "node_modules"}


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        raise ValueError(f"{path}: 缺少 frontmatter")
    fm = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip().strip("'\"")
    for required in ("title", "summary"):
        if not fm.get(required):
            raise ValueError(f"{path}: frontmatter 缺 {required}")
    return fm


def fmt_tags(raw: str) -> str:
    inner = raw.strip("[]")
    tags = [t.strip().strip("'\"") for t in inner.split(",") if t.strip()]
    return " ".join(f"`{t}`" for t in tags)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("用法: python3 build_index.py <仓库根目录>")
    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        sys.exit(f"目录不存在: {root}")

    known_names = [k for k, _ in KNOWN]
    dirs = [d for d in root.iterdir() if d.is_dir() and d.name not in SKIP_DIRS]
    ordered = [d for k in known_names for d in dirs if d.name == k]
    ordered += sorted((d for d in dirs if d.name not in known_names), key=lambda d: d.name)

    display = dict(KNOWN)
    sections, total = [], 0
    for d in ordered:
        files = sorted(f for f in d.glob("*.md") if f.name != "README.md")
        if not files:
            continue
        rows = []
        for f in files:
            fm = parse_frontmatter(f)
            media = fm.get("media", "0")
            case = "✓" if media not in ("", "0") else ""
            model = fm.get("model", "")
            rows.append(
                f"| [{fm['title']}]({d.name}/{f.name}) | {fm['summary']} "
                f"| {fmt_tags(fm.get('tags', ''))} | {model} | {case} |"
            )
        total += len(rows)
        title = display.get(d.name, d.name)
        sections.append(
            f"## {title}（{len(rows)}）\n\n"
            "| 标题 | 说明 | 标签 | 适用模型 | 案例 |\n|---|---|---|---|---|\n"
            + "\n".join(rows)
        )

    out = (
        "# Prompt Vault\n\n"
        "个人 prompt 资产库：每条 prompt 一个文档，含原文、效果案例与来源。\n\n"
        f"共 **{total}** 条 · 索引更新于 {date.today().isoformat()} · "
        "本文件由 `build_index.py` 生成，请勿手改。\n\n"
        + "\n\n".join(sections)
        + "\n"
    )
    (root / "README.md").write_text(out, encoding="utf-8")
    print(f"OK: {total} 条已写入 {root / 'README.md'}")


if __name__ == "__main__":
    main()
