#!/usr/bin/env python3
"""转换前的普查：切章节、数元素、报可疑之处

用法: python3 book_survey.py 全文.txt [--json]

做三件事：
  1. 用两套正则各切一遍章节并交叉验证——Markdown 前缀会让常见正则失效，
     两套结果差得离谱就说明有一套错了
  2. 统计各章字数，以及公式、代码、表格、图表、实验、习题各有多少
  3. 丢字断言：各章字数之和应等于全文字数

普查表的用途是转换后对账：原文有 13 个实验，导图里落了几个。
"""
import json
import re
import sys

# 两套章节正则，用来交叉验证。第一套认 Markdown 标题，第二套认裸行标题。
# 只认明确的章节标记。曾经加过"数字加点"的分支，结果把原文代码里的
# `# 1. 用户提问` 当成了三个章节——编号小节不是章节，宁可切不出来也别切错。
_CHAPTER = r"(?:第\s*[0-9一二三四五六七八九十百]+\s*[章讲部]|Chapter\s+[0-9IVXivx]+)"
CHAPTER_PATTERNS = {
    "markdown": re.compile(rf"^#{{1,3}}\s*{_CHAPTER}", re.I | re.M),
    "bare": re.compile(rf"^\s*{_CHAPTER}(?=\s*$|\s*[：:.。\-—]|\s+\S)", re.I | re.M),
}
SECTION = re.compile(r"^#{2,3}\s+\S", re.M)

ELEMENTS = {
    "公式": re.compile(r"\$\$|\\\[|\\begin\{(?:equation|align|gather)"),
    "代码块": re.compile(r"^```|^\s{4,}(?:def |class |import |function |const |var )",
                      re.M),
    "表格": re.compile(r"^\s*\|.+\|\s*$", re.M),
    "图表引用": re.compile(r"(?:图|表|Figure|Table|Fig\.)\s*[0-9]+[-.．][0-9]+", re.I),
    "实验": re.compile(r"实验\s*[0-9]+\s*[-‑–]\s*[0-9]+|Experiment\s+[0-9]", re.I),
    "习题": re.compile(r"^\s*(?:思考题|习题|练习|课后题|Exercises?|Problems?)\s*$", re.M),
}


def effective_chars(text):
    return len(re.sub(r"\s", "", text))


def strip_code(text):
    """切章节前先剥掉代码块。代码里的 # 注释会被当成 Markdown 标题——
    实测中原文的 `# 1. 用户提问` 就骗过了正则，切出三个假章节。"""
    return re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)


def split_chapters(text, pattern):
    hits = [m.start() for m in pattern.finditer(text)]
    if not hits:
        return []
    bounds = hits + [len(text)]
    chapters = []
    for i, start in enumerate(hits):
        body = text[start:bounds[i + 1]]
        chapters.append({
            "title": body.splitlines()[0].strip()[:60],
            "chars": effective_chars(body),
        })
    return chapters


def survey(path):
    text = open(path, encoding="utf-8").read()
    total = effective_chars(text)
    prose = strip_code(text)  # 元素计数用原文，切章节用剥掉代码的版本

    splits = {name: split_chapters(prose, pat)
              for name, pat in CHAPTER_PATTERNS.items()}
    counts = {name: len(ch) for name, ch in splits.items()}

    # 选命中更多的那套，但两套差距悬殊时要报警
    best = max(counts, key=lambda k: counts[k])
    chapters = splits[best]

    warnings = []
    a, b = counts["markdown"], counts["bare"]
    if a and b and (max(a, b) > 3 * max(min(a, b), 1)):
        warnings.append(
            f"两套章节正则结果差距悬殊（markdown {a} / bare {b}）——"
            f"多半有一套把正文里的交叉引用当成了标题，人工确认一下")
    if not chapters:
        n = len(SECTION.findall(prose))
        warnings.append(
            f"没找到章节标记。原文有 {n} 个二三级标题——如果这是单独一章，"
            f"按小节处理即可；如果这是整本书，说明标题格式特殊，需要人工定切分点")
    elif len(chapters) > 60:
        warnings.append(f"切出 {len(chapters)} 章，数量异常，很可能误把正文行当成了标题")

    if chapters:
        summed = sum(c["chars"] for c in chapters)
        lost = total - summed
        # 首章之前的前言部分不算丢字
        if lost > total * 0.15:
            warnings.append(f"各章字数之和比全文少 {lost} 字（{lost/total:.0%}），确认是不是切丢了内容")

    elements = {name: len(pat.findall(text)) for name, pat in ELEMENTS.items()}

    return {"总字数": total, "章节数": len(chapters), "切分方式": best,
            "各章": chapters, "元素": elements, "提示": warnings}


if __name__ == "__main__":
    result = survey(sys.argv[1])
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    print(f"总字数 {result['总字数']}，切出 {result['章节数']} 章（按 {result['切分方式']} 规则）\n")
    for i, ch in enumerate(result["各章"], 1):
        print(f"  {i:2}. {ch['title']:<50} {ch['chars']:>7} 字")
    print("\n元素普查（转换后拿这张表对账）：")
    for name, n in result["元素"].items():
        print(f"  {name:6} {n}")
    if result["提示"]:
        print("\n需要人工确认：")
        for w in result["提示"]:
            print("  -", w)
