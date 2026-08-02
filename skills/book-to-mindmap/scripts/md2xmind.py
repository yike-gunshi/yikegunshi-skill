#!/usr/bin/env python3
"""多级 bullet Markdown -> .xmind

用法: python3 md2xmind.py input.md output.xmind [折叠层深]

真源语法:
  - 节点文字                每行一个节点，2 空格缩进一层
  - 节点文字 @核心 §3.2     行尾 @ 是标记、§ 是标签（溯源章节号），可多个
  > 解释段落                节点行后面的 > 行是 notes，点开小图标才看得到
  > - 要点                  notes 里 - 开头的行会变成列表
  > 用 **文字** 加粗
  >> 一句关键提示            >> 是标注，气泡挂在节点旁边，不用点就能看见
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

# 每个一级分支一个颜色。一章两百个节点时，颜色是最省力的定位手段——
# 扫到一片蓝就知道还在同一支里，不用回头看自己从哪拐进来的
BRANCH_COLORS = ("#2E6FD9 #E8833A #3AA76D #C0392B #7D5BA6 #1B9AAA "
                 "#D4A017 #55606E #B5446E #4C6EF5")

CALLOUT_STYLE = {
    "callout-shape-class": "org.xmind.calloutTopicShape.balloon.roundedRect",
    "svg:fill": "#FFF8E1",
    "fo:font-size": "11pt",
}

# notes 的第一段会直接显示在节点里，灰色，像一条内嵌的引用，不用点开
# 富文本样式必须用 fo: 前缀，驼峰命名（fontSize/textColor）XMind 直接忽略——实测确认
# 只设颜色，字号和字重都不写，交给主题自动决定——主次靠颜色分就够了
INLINE_STYLE = {"fo:color": "#8A8A8A"}
# 真源里 **包起来** 的关键词换成这个颜色，标题和灰字里都适用
KEYWORD_STYLE = {"fo:color": "#2E6FD9"}
INLINE_WIDTH = 450   # 限宽让长句自动折行，否则节点会被拉成一条


def runs(text, style=None):
    """把 **关键词** 切成独立的富文本片段，换成强调色

    不用加粗：XMind 主题里节点标题默认就是粗体，在粗句子里再加粗等于没加。
    换色才能制造对比，且不动字重这个维度。
    """
    out = []
    for part in re.split(r"(\*\*.+?\*\*)", text):
        if not part:
            continue
        run = dict(style or {})
        if part.startswith("**") and part.endswith("**"):
            run.update(KEYWORD_STYLE)
            part = part[2:-2]
        out.append({"text": part, **run})
    return out


def plain(text):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


def split_notes(lines):
    """切成 (第一段, 剩余行)。第一段进节点显示，剩余部分才需要 notes"""
    para, rest = [], []
    for i, raw in enumerate(lines):
        if not raw.strip():
            rest = lines[i + 1:]
            break
        para.append(raw.strip().lstrip("- "))
    return " ".join(para), [r for r in rest if r.strip()]


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
    root = {"title": None, "children": [], "notes": [], "callouts": [],
            "markers": [], "labels": []}
    stack = [(-1, root)]
    last = None
    for line in text.splitlines():
        m = re.match(r"^(\s*)-\s+(.*\S)\s*$", line)
        if m:
            depth = len(m.group(1)) // 2
            title, markers, labels = parse_attrs(m.group(2))
            node = {"title": title, "children": [], "notes": [], "callouts": [],
                    "markers": markers, "labels": labels}
            while stack and stack[-1][0] >= depth:
                stack.pop()
            stack[-1][1]["children"].append(node)
            stack.append((depth, node))
            last = node
            continue
        c = re.match(r"^\s*>>\s?(.*\S)\s*$", line)
        if c and last is not None:
            last["callouts"].append(c.group(1))
            continue
        n = re.match(r"^\s*>\s?(.*)$", line)
        if n and last is not None:
            last["notes"].append(n.group(1))
    if len(root["children"]) == 1:
        return root["children"][0]
    root["title"] = "Root"
    return root


def to_topic(node, depth=0, fold_depth=None, warnings=None):
    title = node["title"]
    topic = {"id": uuid.uuid4().hex, "title": plain(title)}
    if "**" in title:
        topic["attributedTitle"] = runs(title)

    if node["notes"]:
        inline, rest = split_notes(node["notes"])
        # 第一段进节点内部灰字显示，不用点开
        if inline:
            topic["title"] = f"{plain(title)}\n{plain(inline)}"
            topic["attributedTitle"] = (
                runs(title) + [{"text": "\n"}] + runs(inline, INLINE_STYLE))
            topic["customWidth"] = INLINE_WIDTH
        # 只有还有后续段落时才挂 notes，否则图标点开看到的是同一句话
        if rest or not inline:
            keep = rest if inline else node["notes"]
            # plain 供搜索和第三方解析器，realHTML 负责渲染；XMind 自己两个都写
            topic["notes"] = {"plain": {"content": "\n".join(keep).strip()},
                              "realHTML": {"content": note_to_html(keep)}}
    if node["markers"]:
        for mid in node["markers"]:
            problem = check_marker(mid)
            if problem and warnings is not None:
                warnings.append(problem)
        topic["markers"] = [{"markerId": m} for m in node["markers"]]
    if node["labels"]:
        topic["labels"] = node["labels"]
    children = {}
    if node["children"]:
        children["attached"] = [
            to_topic(c, depth + 1, fold_depth, warnings) for c in node["children"]]
    if node.get("callouts"):
        # 标注是气泡，挂在节点旁边直接可见，不用点开
        children["callout"] = [
            {"id": uuid.uuid4().hex, "title": text,
             "style": {"id": uuid.uuid4().hex, "properties": dict(CALLOUT_STYLE)}}
            for text in node["callouts"]]
    if children:
        topic["children"] = children
        # 折叠只作用于节点自身，对子孙没有传染性，所以要逐个打标
        if node["children"] and fold_depth is not None and depth >= fold_depth:
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
            "style": {"id": uuid.uuid4().hex,
                      "properties": {"multi-line-colors": BRANCH_COLORS}},
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
