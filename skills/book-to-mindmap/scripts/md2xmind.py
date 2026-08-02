#!/usr/bin/env python3
"""多级 bullet Markdown -> .xmind (XMind 2020+ content.json 格式)

用法: python3 md2xmind.py input.md output.xmind [折叠层深]
输入格式:
  - "# 标题" 开启一张新画布（multimap；没有 # 时整个文件为一张）
  - 每行 "- 文本" 为一个节点，2 空格缩进表示一层
  - 节点行之后的 "> 文本" 行成为该节点的 XMind notes（可多行）
折叠层深：该层节点默认收起子节点，打开导图先看骨架（根为 0；不传则全展开）
"""
import json
import re
import sys
import uuid
import zipfile


def parse_bullets(text):
    root = {"title": None, "children": [], "note": ""}
    stack = [(-1, root)]
    last = None
    for line in text.splitlines():
        m = re.match(r"^(\s*)-\s+(.*\S)\s*$", line)
        if m:
            depth = len(m.group(1)) // 2
            node = {"title": m.group(2), "children": [], "note": ""}
            while stack and stack[-1][0] >= depth:
                stack.pop()
            stack[-1][1]["children"].append(node)
            stack.append((depth, node))
            last = node
            continue
        n = re.match(r"^\s*>\s+(.*\S)\s*$", line)
        if n and last is not None:
            last["note"] = (last["note"] + "\n" if last["note"] else "") + n.group(1)
    if len(root["children"]) == 1:
        return root["children"][0]
    root["title"] = "Root"
    return root


def to_topic(node, depth=0, fold_depth=None):
    topic = {"id": uuid.uuid4().hex, "class": "topic", "title": node["title"]}
    if node.get("note"):
        topic["notes"] = {"plain": {"content": node["note"]}}
    if node["children"]:
        topic["children"] = {"attached": [to_topic(c, depth + 1, fold_depth)
                                         for c in node["children"]]}
        if fold_depth is not None and depth >= fold_depth:
            topic["branch"] = "folded"
    return topic


def split_sheets(text):
    """按 '# 标题' 切分为多张画布，返回 [(sheet_title, body), ...]"""
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
    sheet = []
    for title, body in split_sheets(text):
        tree = parse_bullets(body)
        sheet.append({
            "id": uuid.uuid4().hex,
            "class": "sheet",
            "title": title or tree["title"],
            "rootTopic": to_topic(tree, 0, fold_depth),
            "extensions": [],
            "theme": {},
        })
    manifest = {"file-entries": {"content.json": {}, "metadata.json": {}}}
    metadata = {"dataStructureVersion": "2",
                "creator": {"name": "md2xmind", "version": "0.2"}}
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.json", json.dumps(sheet, ensure_ascii=False))
        z.writestr("metadata.json", json.dumps(metadata))
        z.writestr("manifest.json", json.dumps(manifest))
    return out_path


if __name__ == "__main__":
    fold = int(sys.argv[3]) if len(sys.argv) > 3 else None
    print(build_xmind(sys.argv[1], sys.argv[2], fold))
