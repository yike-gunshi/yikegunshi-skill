#!/usr/bin/env python3
"""skill 包体检。

用法:
    python3 validate_skill.py <skill目录> [--strict]

查六类问题：
  1. 结构与 frontmatter 合法性（硬错误）
  2. description 是否只放触发信息、是否有排除项
  3. SKILL.md 正文长度
  4. 强调词密度
  5. 红线条数
  6. 装饰性目录、断链引用、不该存在的文件

--strict 时 WARN 也计入退出码。
"""

import argparse
import re
import sys
from pathlib import Path

ALLOWED_FRONTMATTER = {"name", "description", "license", "allowed-tools", "metadata"}

EMPHASIS_WORDS = [
    "必须", "禁止", "严禁", "绝不", "一律", "强制", "不得", "底线",
    "红线", "最高优先级", "不可突破", "任何情况下",
]
ALLCAPS_PATTERN = re.compile(r"\b(?:ALWAYS|NEVER|MUST|DO NOT|CRITICAL|IMPORTANT)\b")

FORBIDDEN_FILES = {
    "README.md", "CHANGELOG.md", "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md", "INSTALL.md", "CONTRIBUTING.md",
}

FENCED_CODE = re.compile(r"^```.*?^```", re.M | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]+`")

MAX_BODY_LINES = 500
MAX_DESCRIPTION_CHARS = 1024
MAX_REDLINES = 5
EMPHASIS_PER_LINE_WARN = 1 / 15  # 每 15 行一个强调词以上就提醒


class Report:
    def __init__(self):
        self.errors = []
        self.warns = []
        self.infos = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    def info(self, msg):
        self.infos.append(msg)

    def render(self, strict):
        for m in self.infos:
            print(f"  ·    {m}")
        for m in self.warns:
            print(f"  WARN {m}")
        for m in self.errors:
            print(f"  FAIL {m}")
        print()
        print(f"{len(self.errors)} error(s), {len(self.warns)} warning(s)")
        if self.errors:
            return 1
        if strict and self.warns:
            return 1
        return 0


def split_frontmatter(text):
    """返回 (frontmatter_dict, body, err)。不依赖 pyyaml。"""
    if not text.startswith("---"):
        return None, None, "SKILL.md 没有 YAML frontmatter"
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return None, None, "frontmatter 格式不合法（找不到闭合的 ---）"
    raw, body = m.group(1), m.group(2)

    try:
        import yaml  # noqa: F401
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            return None, None, "frontmatter 必须是 YAML 字典"
        return data, body, None
    except ImportError:
        pass

    # 无 pyyaml 时的最小解析：顶层 `key: value`，后续缩进行视为续行
    data, key = {}, None
    for line in raw.split("\n"):
        if not line.strip():
            continue
        m2 = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if m2:
            key = m2.group(1)
            data[key] = m2.group(2).strip()
        elif key and line.startswith((" ", "\t")):
            data[key] = (str(data[key]) + " " + line.strip()).strip()
    return data, body, None


def check_frontmatter(fm, rep):
    unexpected = set(fm) - ALLOWED_FRONTMATTER
    if unexpected:
        rep.error(f"frontmatter 出现不允许的字段: {', '.join(sorted(unexpected))}")

    name = str(fm.get("name", "")).strip()
    if not name:
        rep.error("frontmatter 缺少 name")
    else:
        if not re.match(r"^[a-z0-9-]+$", name):
            rep.error(f"name '{name}' 应为 hyphen-case（小写字母、数字、连字符）")
        if name.startswith("-") or name.endswith("-") or "--" in name:
            rep.error(f"name '{name}' 不能以连字符开头/结尾或含连续连字符")
        if len(name) > 64:
            rep.error(f"name 过长（{len(name)} 字符，上限 64）")
        if re.search(r"-v\d+$", name):
            rep.warn(f"name '{name}' 带版本号后缀。更新 skill 不应改名，改名会让所有引用和 symlink 静默失效")

    desc = str(fm.get("description", "")).strip()
    if not desc:
        rep.error("frontmatter 缺少 description")
        return name, desc

    if "<" in desc or ">" in desc:
        rep.error("description 不能包含尖括号 < 或 >")
    if len(desc) > MAX_DESCRIPTION_CHARS:
        rep.error(f"description 过长（{len(desc)} 字符，上限 {MAX_DESCRIPTION_CHARS}）")
    else:
        rep.info(f"description {len(desc)} 字符")

    if not re.search(r"不处理|不接|不做|排除|交给|走 |不用于"
                     r"|Exclude|Not for|Do not use|Don't use|instead of|goes to", desc, re.I):
        rep.warn("description 看不出排除项。写清「不处理什么、该交给谁」能同时降低误触发和帮用户理解边界")

    if not re.search(r"用户说|时都?用|触发|哪怕|即使|也用|Use when|whenever", desc):
        rep.warn("description 缺少「何时使用」的具体语境。模型有欠触发倾向，要显式覆盖同义场景")

    banned = [w for w in ("伪造", "不许", "严禁", "违反") if w in desc]
    if banned:
        rep.warn(
            f"description 里出现执行层禁令（{', '.join(banned)}）。这类内容不影响触发决策，"
            "却要占用对所有会话常驻的最贵预算，移回正文"
        )
    return name, desc


def check_body(body, rep):
    lines = body.split("\n")
    n = len(lines)
    if n > MAX_BODY_LINES:
        rep.error(f"SKILL.md 正文 {n} 行，超过 {MAX_BODY_LINES}。外移到 references/，别靠压缩措辞硬塞")
    else:
        rep.info(f"SKILL.md 正文 {n} 行")

    if re.search(r"^#{1,4}\s*(何时使用|什么时候用|When to Use)", body, re.M | re.I):
        rep.warn(
            "正文里有「何时使用」章节。正文只在触发之后才加载，写在这里没有读者——触发信息全部归 description"
        )

    # 代码块和行内 code 里的词是被「提及」而非被「使用」——讲反模式的 skill 不该因此被判超标
    prose = INLINE_CODE.sub(" ", FENCED_CODE.sub(" ", body))

    hits = {}
    for w in EMPHASIS_WORDS:
        c = prose.count(w)
        if c:
            hits[w] = c
    caps = ALLCAPS_PATTERN.findall(prose)
    total = sum(hits.values()) + len(caps)

    if total:
        top = ", ".join(f"{w}×{c}" for w, c in sorted(hits.items(), key=lambda kv: -kv[1])[:5])
        rep.info(f"强调词 {total} 处（每 {n / total:.0f} 行一个）: {top}" + (f", ALLCAPS×{len(caps)}" if caps else ""))
    if total and n / total < 1 / EMPHASIS_PER_LINE_WARN:
        rep.warn(
            f"强调词密度过高（{total} 处 / {n} 行）。规则不被遵守的根因通常是文档太长把规则稀释了，"
            "加更多强调词只会让它更长——解释 why 或者外移"
        )
    if hits.get("最高优先级", 0) > 1:
        rep.warn(f"出现 {hits['最高优先级']} 处「最高优先级」。多于一个就等于没有优先级，模型在它们冲突时无法取舍")
    if caps:
        rep.warn(f"出现全大写强调 {len(caps)} 处（{', '.join(sorted(set(caps))[:4])}）。这是黄色警告，优先改成解释 why")

    return count_redlines(body, rep)


def count_redlines(body, rep):
    m = re.search(r"^#{1,4}\s*[^\n]*红线[^\n]*$", body, re.M)
    if not m:
        rep.info("没有独立的红线章节")
        return 0
    rest = body[m.end():]
    nxt = re.search(r"^#{1,4}\s", rest, re.M)
    section = rest[: nxt.start()] if nxt else rest
    items = re.findall(r"^\s*(?:\d+[.、)]|[-*])\s+\S", section, re.M)
    count = len(items)
    rep.info(f"红线 {count} 条")
    if count > MAX_REDLINES:
        rep.warn(
            f"红线 {count} 条，超过 {MAX_REDLINES}。逐条问「违反了会发生什么、能不能收回来」——"
            "收得回来的降级成带 why 的强建议"
        )
    return count


def check_layout(skill_dir, skill_md_text, rep):
    for name in sorted(p.name for p in skill_dir.iterdir() if p.is_file()):
        if name in FORBIDDEN_FILES:
            rep.warn(f"存在 {name}。skill 目录只装模型干活需要的东西，建包过程的说明放仓库层面")

    for sub in ("references", "scripts", "assets"):
        d = skill_dir / sub
        if not d.is_dir():
            continue
        files = [p for p in d.rglob("*") if p.is_file() and not p.name.startswith(".")]
        if not files:
            rep.warn(f"{sub}/ 是空目录，删掉")
            continue
        if sub not in skill_md_text:
            rep.warn(f"{sub}/ 存在但 SKILL.md 从未引用它——装饰性目录，模型不知道它存在")
            continue
        def referenced(p):
            rel = p.relative_to(skill_dir)
            # 文件名、去扩展名、完整相对路径，或所在目录被通配符整体引用（references/examples/*.md）。
            # 只认带 /* 的通配符——光提到 references/ 不算引用了里面的每个文件
            return (p.name in skill_md_text or p.stem in skill_md_text
                    or str(rel) in skill_md_text or f"{rel.parent}/*" in skill_md_text)

        unrefed = [p for p in files if not referenced(p)]
        if unrefed and sub == "references":
            rep.warn(
                f"references/ 有 {len(unrefed)} 个文件没在 SKILL.md 里点名何时读: "
                + ", ".join(p.name for p in unrefed[:5])
            )

    # 前面跟着 / 或 $VAR 的是外部工具链路径（如 "$TOOL_HOME/scripts/x.py"），不是包内引用
    for ref in re.findall(r"(?<![\w$/])`(references/[\w./-]+)`", skill_md_text):
        if "*" in ref:
            continue
        if not (skill_dir / ref).exists():
            rep.error(f"SKILL.md 引用了不存在的文件: {ref}")
    for scr in re.findall(r"(?<![\w$/])(scripts/[\w./-]+\.py)", skill_md_text):
        if not (skill_dir / scr).exists():
            rep.error(f"SKILL.md 引用了不存在的脚本: {scr}")


def main():
    ap = argparse.ArgumentParser(description="skill 包体检")
    ap.add_argument("skill_dir")
    ap.add_argument("--strict", action="store_true", help="WARN 也计入退出码")
    args = ap.parse_args()

    skill_dir = Path(args.skill_dir).expanduser().resolve()
    rep = Report()
    print(f"体检: {skill_dir}")
    print()

    if not skill_dir.is_dir():
        print(f"  FAIL 目录不存在: {skill_dir}")
        return 1
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        print("  FAIL 找不到 SKILL.md")
        return 1

    text = skill_md.read_text(encoding="utf-8")
    fm, body, err = split_frontmatter(text)
    if err:
        print(f"  FAIL {err}")
        return 1

    check_frontmatter(fm, rep)
    check_body(body, rep)
    check_layout(skill_dir, text, rep)
    return rep.render(args.strict)


if __name__ == "__main__":
    sys.exit(main())
