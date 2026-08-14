#!/usr/bin/env python3
"""读仓库之前的侦察：出模块清单、改动热点、文档资源、入口线索。

用法: python3 repo_survey.py <仓库路径> [--json] [--top N] [--commits N]

产出 S1 侦察报告的机器部分。四组信号各自回答一个问题：

  1. 目录代码量  —— 体量在哪，量大的目录通常承载核心逻辑
  2. git 改动热点 —— 团队在往哪使劲，改得最勤的文件是活跃的核心
  3. 文档资源    —— 「设计决策」那节能不能写出有出处的内容。
                    没有 docs/ 和 ADR 就只能标推断，这个要提前知道
  4. 依赖与入口  —— 依赖清单是术语表的原料，入口是主链路时序图的起点

三组信号必须交叉看才能定关键模块。只看代码量会把生成代码和数据文件
当核心；只看改动热点会漏掉写完就不动的地基模块（比如协议定义、
核心抽象基类），而那些恰恰是理解架构的入口。
"""
import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

# 不进统计的目录。
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "bower_components",
    "dist", "build", "out", "target", "bin", "obj",
    "__pycache__", ".venv", "venv", "env", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".next", ".nuxt", ".cache",
    "coverage", "htmlcov", ".idea", ".vscode", ".gradle",
}

# 测试数据目录：不计入体量和热点（一个仓库的 fixtures 可以比业务代码
# 还多，混进去会把体量排名和改动热点全带歪），但要在报告里点名——
# 里面藏着边界条件和策略取值，是「策略与配置」那节的原料。
FIXTURE_DIRS = {
    "fixtures", "__fixtures__", "testdata", "test_data", "snapshots",
    "__snapshots__", "golden", "goldens", "cassettes", "recordings",
}

# 测试代码目录：同样单独统计。实测 info2action 的 tests 有 4.7 万行，
# 比 src 的 4.4 万还多，混进体量榜会直接把 tests 顶到第一位，读者会
# 误判它是核心模块。但测试代码量与源码量的比值本身是有用信号，报出来。
TEST_DIRS = {
    "tests", "test", "__tests__", "spec", "specs", "e2e", "integration_tests",
}

# 生成物与锁文件。计入代码量会严重歪曲体量判断。
SKIP_FILE_PATTERNS = [
    re.compile(r"-lock\.json$"), re.compile(r"\.lock$"),
    re.compile(r"\.min\.(js|css)$"), re.compile(r"\.map$"),
    re.compile(r"\.pb\.(go|cc|h)$"), re.compile(r"_pb2\.pyi?$"),
    re.compile(r"\.generated\."), re.compile(r"\.designer\.cs$"),
]

LANG_BY_EXT = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".c": "C", ".h": "C/C++ header", ".cc": "C++", ".cpp": "C++",
    ".hpp": "C++ header", ".cs": "C#", ".rb": "Ruby", ".php": "PHP",
    ".swift": "Swift", ".m": "Objective-C", ".scala": "Scala",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".sql": "SQL", ".proto": "Protobuf", ".graphql": "GraphQL",
    ".vue": "Vue", ".svelte": "Svelte",
    ".md": "Markdown", ".rst": "reStructuredText",
    ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".json": "JSON",
}
# 只有这些算代码。文档和配置单独统计，混在一起会让 JSON 密集的项目失真。
CODE_LANGS = {
    "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "Kotlin",
    "C", "C++", "C/C++ header", "C++ header", "C#", "Ruby", "PHP",
    "Swift", "Objective-C", "Scala", "Shell", "SQL", "Protobuf",
    "GraphQL", "Vue", "Svelte",
}

# 文档资源。命中与否直接决定「设计决策」那节的可写程度。
DOC_HINTS = {
    "架构与设计": ["docs", "doc", "design", "rfc", "rfcs", "adr",
                "architecture", "designs", "proposals", "specs"],
    "变更历史": ["CHANGELOG.md", "CHANGELOG", "HISTORY.md", "NEWS.md",
             "RELEASES.md", "CHANGES.md"],
    "参与指南": ["CONTRIBUTING.md", "DEVELOPMENT.md", "HACKING.md",
             "ARCHITECTURE.md", "AGENTS.md", "CLAUDE.md"],
}

DEP_FILES = [
    "package.json", "pyproject.toml", "requirements.txt", "setup.py",
    "Pipfile", "poetry.lock", "go.mod", "Cargo.toml", "pom.xml",
    "build.gradle", "build.gradle.kts", "Gemfile", "composer.json",
    "pubspec.yaml", "Package.swift", "mix.exs",
]

ENTRY_NAMES = [
    "main.py", "__main__.py", "app.py", "server.py", "manage.py", "cli.py",
    "main.go", "main.rs", "lib.rs", "Main.java",
    "index.js", "index.ts", "main.js", "main.ts", "server.js", "app.ts",
]


def classify(path: Path, root: Path):
    """返回 skip / fixture / test / keep。后三类分开统计，只有 keep 进体量榜。"""
    parts = path.relative_to(root).parts[:-1]
    if any(p in SKIP_DIRS or (p.startswith(".") and p not in {".", ".."})
           for p in parts):
        return "skip"
    if any(p.search(path.name) for p in SKIP_FILE_PATTERNS):
        return "skip"
    if any(p in FIXTURE_DIRS for p in parts):
        return "fixture"
    if any(p in TEST_DIRS for p in parts):
        return "test"
    # 同目录下的 test_x.py / x_test.go / x.test.ts 也是测试代码
    if re.match(r"^test_|_test\.|\.test\.|\.spec\.", path.name) or \
            re.search(r"(_test|\.test|\.spec)\.[a-z]+$", path.name):
        return "test"
    return "keep"


def count_lines(path: Path) -> int:
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
            if b"\0" in chunk:  # 二进制文件
                return 0
            return chunk.count(b"\n") + sum(
                b.count(b"\n") for b in iter(lambda: f.read(1 << 20), b""))
    except OSError:
        return 0


def scan_files(root: Path):
    """走一遍文件树。返回源码行、测试数据目录清单、测试代码统计。"""
    rows, fixtures = [], collections.Counter()
    tests = {"files": 0, "lines": 0}
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        kind = classify(path, root)
        if kind == "skip":
            continue
        lang = LANG_BY_EXT.get(path.suffix.lower())
        if not lang:
            continue
        rel = str(path.relative_to(root))
        if kind == "fixture":
            parts = Path(rel).parts
            i = next(i for i, p in enumerate(parts) if p in FIXTURE_DIRS)
            fixtures["/".join(parts[:i + 1])] += 1
            continue
        if kind == "test":
            if lang in CODE_LANGS:
                tests["files"] += 1
                tests["lines"] += count_lines(path)
            continue
        rows.append({"path": rel, "lang": lang, "lines": count_lines(path)})
    return rows, fixtures, tests


def group_by_dir(rows, depth=2, top=25):
    """按目录聚合。depth=2 是权衡结果：depth=1 在 src/ 单目录项目上
    只出一行等于没信息，depth=3 在深层包结构里又碎得看不出重点。"""
    agg = collections.Counter()
    files = collections.Counter()
    for r in rows:
        if r["lang"] not in CODE_LANGS:
            continue
        parts = Path(r["path"]).parts
        key = "/".join(parts[:depth]) if len(parts) > depth else (
            "/".join(parts[:-1]) or ".")
        agg[key] += r["lines"]
        files[key] += 1
    return [{"dir": k, "lines": v, "files": files[k]}
            for k, v in agg.most_common(top)]


def git_hotspots(root: Path, commits: int, top: int, allowed: set):
    """近 N 个 commit 里改动最频繁的文件。

    只统计 allowed 里的文件，也就是当前还存在的正式代码。已删除文件的
    高频改动是历史噪音；fixture 的高频改动会淹没真正的核心逻辑。
    """
    def run(*args):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=120)

    probe = run("rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0:
        return None, "不是 git 仓库，跳过改动热点"

    log = run("log", f"-n{commits}", "--format=", "--name-only",
              "--no-merges")
    if log.returncode != 0:
        return None, "git log 失败：" + log.stderr.strip()[:120]

    counter = collections.Counter(
        line for line in log.stdout.splitlines() if line in allowed)

    head = run("rev-parse", "--short", "HEAD").stdout.strip()
    date = run("log", "-1", "--format=%ci").stdout.strip()[:10]
    total = run("rev-list", "--count", "HEAD").stdout.strip()
    return {
        "commit": head, "date": date, "total_commits": total,
        "window": commits,
        "files": [{"path": p, "changes": c} for p, c in counter.most_common(top)],
    }, None


def find_docs(root: Path):
    hits = collections.defaultdict(list)
    for label, names in DOC_HINTS.items():
        for name in names:
            p = root / name
            if p.exists():
                if p.is_dir():
                    n = sum(1 for _ in p.rglob("*.md")) + sum(
                        1 for _ in p.rglob("*.rst"))
                    hits[label].append(f"{name}/ ({n} 篇)")
                else:
                    hits[label].append(name)
    readme = [p.name for p in root.glob("README*")]
    if readme:
        hits["README"] = readme
    return dict(hits)


def find_meta(root: Path, rows):
    deps = [f for f in DEP_FILES if (root / f).exists()]
    entries = sorted({r["path"] for r in rows
                      if Path(r["path"]).name in ENTRY_NAMES})
    langs = collections.Counter()
    for r in rows:
        if r["lang"] in CODE_LANGS:
            langs[r["lang"]] += r["lines"]
    return {
        "deps": deps,
        "entries": entries[:15],
        "langs": [{"lang": k, "lines": v} for k, v in langs.most_common(8)],
    }


def render(root: Path, data) -> str:
    L = [f"# 仓库侦察报告：{root.name}", ""]
    hot = data["hotspots"]
    if hot:
        L += [f"快照：`{hot['commit']}` · {hot['date']} · "
              f"共 {hot['total_commits']} 个 commit", ""]
    else:
        L += [f"快照：{data['hotspot_note']}", ""]

    L += ["## 语言构成", "", "| 语言 | 代码行 |", "| --- | --- |"]
    L += [f"| {x['lang']} | {x['lines']:,} |" for x in data["meta"]["langs"]]
    t = data["tests"]
    L += ["", f"源码 {data['code_files']} 个文件 / {data['code_lines']:,} 行"]
    if t["lines"]:
        ratio = t["lines"] / max(data["code_lines"], 1)
        L += [f"测试代码 {t['files']} 个文件 / {t['lines']:,} 行"
              f"（测试比源码 = {ratio:.2f}，不计入下面的体量榜）"]
    L += [""]

    L += ["## 体量分布（按目录）", "",
          "| 目录 | 代码行 | 文件数 |", "| --- | --- | --- |"]
    L += [f"| `{x['dir']}` | {x['lines']:,} | {x['files']} |"
          for x in data["dirs"]]
    L += [""]

    if hot:
        L += [f"## 改动热点（近 {hot['window']} 个 commit）", "",
              "| 文件 | 改动次数 |", "| --- | --- |"]
        L += [f"| `{x['path']}` | {x['changes']} |" for x in hot["files"]]
        top_n = hot["files"][0]["changes"] if hot["files"] else 0
        if int(hot["total_commits"] or 0) < 50 or top_n < 3:
            L += ["", "提示：历史太短或改动过于均匀，热点信号不可信，"
                  "定关键模块时以体量分布和入口链路为准"]
        L += [""]

    L += ["## 文档资源", ""]
    docs = data["docs"]
    if docs:
        L += [f"- {k}：{', '.join(v)}" for k, v in docs.items()]
    else:
        L += ["- 无。设计决策那节只能靠代码注释和 commit message，"
              "写不出出处就标推断"]
    fx = data["fixtures"]
    if fx:
        L += ["- 测试数据：" + "，".join(f"`{k}/` ({v} 个)" for k, v in fx)
              + "。不计入上面的体量，但策略取值和边界条件常藏在这里"]
    L += [""]

    meta = data["meta"]
    L += ["## 依赖与入口", "",
          f"- 依赖声明：{', '.join(meta['deps']) or '未发现'}",
          f"- 入口候选：{', '.join(f'`{e}`' for e in meta['entries']) or '未发现，需人工找'}",
          ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--commits", type=int, default=500)
    a = ap.parse_args()

    root = Path(a.repo).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"不是目录：{root}")

    rows, fixtures, tests = scan_files(root)
    if not rows:
        sys.exit(f"没扫到可识别的源文件：{root}")

    code = {r["path"] for r in rows if r["lang"] in CODE_LANGS}
    hot, note = git_hotspots(root, a.commits, a.top, code)
    data = {
        "root": str(root),
        "code_files": len(code),
        "code_lines": sum(r["lines"] for r in rows if r["lang"] in CODE_LANGS),
        "dirs": group_by_dir(rows, top=a.top),
        "hotspots": hot,
        "hotspot_note": note,
        "docs": find_docs(root),
        "fixtures": fixtures.most_common(6),
        "tests": tests,
        "meta": find_meta(root, rows),
    }
    print(json.dumps(data, ensure_ascii=False, indent=2) if a.json
          else render(root, data))


if __name__ == "__main__":
    main()
