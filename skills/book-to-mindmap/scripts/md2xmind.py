#!/usr/bin/env python3
"""多级 bullet Markdown -> .xmind

用法: python3 md2xmind.py input.md output.xmind [折叠层深]

真源语法:
  - 节点文字                每行一个节点，2 空格缩进一层
  - 节点文字 @核心 §3.2     行尾 @ 是标记、§ 是标签（溯源章节号），可多个
  > 解释段落                节点行后面的 > 行是 notes，空 > 行分段
  > - 要点                  notes 里 - 开头的行会变成列表
  > 用 **文字** 加粗
  # 标题                    另起一张画布（一般不用，一本书就一张）

折叠层深：该层节点默认收起子节点，打开先看骨架（根为 0，常用 2；不传则全展开）

标记别名：核心 数据 注意 已验证 问题；也可直接写 XMind 的 markerId
"""
import html
import json
import os
import re
import sys
import uuid
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xmind_markers import check as check_marker  # noqa: E402

# 读书导图够用的一组语义标记。刻意不用 priority-1..9——优先级对读书笔记是伪需求，
# 而且九个数字方块视觉上很吵
MARKER_ALIAS = {
    "核心": "star-red",
    "数据": "symbol-info",
    "注意": "symbol-exclam",
    "已验证": "task-done",
    "问题": "symbol-question",
}

# 技术书是层层收束的论证，逻辑图比默认的中心发散图更贴合
STRUCTURE = "org.xmind.ui.logic.right"


def parse_attrs(title):
    """从行尾摘出 @标记 和 §标签，返回 (纯标题, markers, labels)"""
    markers, labels = [], []
    while True:
        m = re.search(r"\s+([@§])([^\s@§]+)$", title)
        if not m:
            break
        sign, value = m.group(1), m.group(2)
        if sign == "@":
            markers.insert(0, MARKER_ALIAS.get(value, value))
        else:
            labels.insert(0, "§" + value)
        title = title[:m.start()]
    return title, markers, labels


def note_to_html(lines):
    """notes 的 markdown 子集 -> realHTML。XMind 用 div 分段，且不认 <code>"""
    out, bullets = [], []

    def flush():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    for raw in lines:
        if not raw.strip():
            flush()
            continue
        line = html.escape(raw.strip())
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        if raw.lstrip().startswith("- "):
            bullets.append(line[2:])
        else:
            flush()
            out.append(f"<div>{line}</div>")
    flush()
    return "".join(out)


def parse_bullets(text):
    root = {"title": None, "children": [], "notes": [], "markers": [], "labels": []}
    stack = [(-1, root)]
    last = None
    for line in text.splitlines():
        m = re.match(r"^(\s*)-\s+(.*\S)\s*$", line)
        if m:
            depth = len(m.group(1)) // 2
            title, markers, labels = parse_attrs(m.group(2))
            node = {"title": title, "children": [], "notes": [],
                    "markers": markers, "labels": labels}
            while stack and stack[-1][0] >= depth:
                stack.pop()
            stack[-1][1]["children"].append(node)
            stack.append((depth, node))
            last = node
            continue
        n = re.match(r"^\s*>\s?(.*)$", line)
        if n and last is not None:
            last["notes"].append(n.group(1))
    if len(root["children"]) == 1:
        return root["children"][0]
    root["title"] = "Root"
    return root


def to_topic(node, depth=0, fold_depth=None, warnings=None):
    topic = {"id": uuid.uuid4().hex, "title": node["title"]}

    if node["notes"]:
        # plain 供搜索和第三方解析器，realHTML 负责渲染；XMind 自己两个都写
        plain = "\n".join(node["notes"]).strip()
        topic["notes"] = {"plain": {"content": plain},
                          "realHTML": {"content": note_to_html(node["notes"])}}
    if node["markers"]:
        for mid in node["markers"]:
            problem = check_marker(mid)
            if problem and warnings is not None:
                warnings.append(problem)
        topic["markers"] = [{"markerId": m} for m in node["markers"]]
    if node["labels"]:
        topic["labels"] = node["labels"]
    if node["children"]:
        topic["children"] = {"attached": [
            to_topic(c, depth + 1, fold_depth, warnings) for c in node["children"]]}
        # 折叠只作用于节点自身，对子孙没有传染性，所以要逐个打标
        if fold_depth is not None and depth >= fold_depth:
            topic["branch"] = "folded"
    return topic


def split_sheets(text):
    sheets, title, body = [], None, []
    for line in text.splitlines():
        m = re.match(r"^#\s+(.*\S)\s*$", line)
        if m:
            if body:
                sheets.append((title, "\n".join(body)))
            title, body = m.group(1), []
        else:
            body.append(line)
    if body:
        sheets.append((title, "\n".join(body)))
    return sheets


def build_xmind(md_path, out_path, fold_depth=None):
    text = open(md_path, encoding="utf-8").read()
    sheets, warnings = [], []
    for title, body in split_sheets(text):
        tree = parse_bullets(body)
        root_topic = to_topic(tree, 0, fold_depth, warnings)
        root_topic["class"] = "topic"
        root_topic["structureClass"] = STRUCTURE
        sheets.append({
            "id": uuid.uuid4().hex,
            "class": "sheet",
            "title": title or tree["title"],
            "rootTopic": root_topic,
            "extensions": [],
            "theme": {},
        })
    manifest = {"file-entries": {"content.json": {}, "metadata.json": {}}}
    metadata = {"dataStructureVersion": "2",
                "creator": {"name": "md2xmind", "version": "0.3"},
                "activeSheetId": sheets[0]["id"]}
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.json", json.dumps(sheets, ensure_ascii=False))
        z.writestr("metadata.json", json.dumps(metadata))
        z.writestr("manifest.json", json.dumps(manifest))
    for w in dict.fromkeys(warnings):
        print("标记有问题:", w, file=sys.stderr)
    return out_path


if __name__ == "__main__":
    fold = int(sys.argv[3]) if len(sys.argv) > 3 else None
    print(build_xmind(sys.argv[1], sys.argv[2], fold))
