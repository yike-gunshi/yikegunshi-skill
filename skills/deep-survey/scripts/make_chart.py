#!/usr/bin/env python3
"""把一份图表数据（JSON）渲染成 PNG，嵌进 md 报告。外观由主题决定。

用法：
  python3 make_chart.py <spec.json> [--out <png>] [--theme <主题名>]
  python3 make_chart.py --all <charts/data 目录> [--out-dir <charts 目录>] [--theme <主题名>]
  python3 make_chart.py --themes          列出可用主题

主题：
- 定义在 assets/chart-themes.json：三个风格家族（clean 干净信息图 / magazine 电子杂志 / swiss 瑞士国际主义），
  共 11 套。颜色、字体、条形粗细、圆角、标题样式、数据卡样式、单位图形状都由主题决定，脚本里不写死。
- 优先级：图表 JSON 的 "theme" 字段 > 命令行 --theme > 默认 clean-默认。一份报告只用一套主题。

规则：
- 每个数值都必须带 source（来源编号列表），缺一个就报错退出。
- 标题写成判断句；subtitle 写单位与口径；可选 kicker（标题上方的小标签，如「图 3 · 用户」）。
- 强调一项、其余置灰；多序列最多 3 个。

图表类型与 JSON 字段：
  bar     横向条形。items: [{label, value, source:[n], highlight?:bool}]，unit?
  grouped 分组柱。categories: [..]; series: [{name, values:[..], source:[[n]..] 或 [n]}]（≤3 个序列）
  line    折线。x: [..]; series: [{name, values:[..], source:[n]}]（≤3 个序列）；缺数据填 null，缺口画成虚线
  stack   横向堆叠条（构成 / 一笔账）。rows: [{label, segments:[{label, value, source:[n]}]}]，unit?，
          highlight?: "要强调的那一类构成"（其余置灰）
  units   单位图。groups: [{label, count, source:[n], highlight?:bool}]（总数 ≤100）
  kpi     数据卡。tiles: [{label, value:"文本", note?, source:[n]}]（2—4 张）
公共字段：type, title, subtitle?, kicker?, note?, theme?
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

THEMES_PATH = Path(__file__).resolve().parent.parent / "assets" / "chart-themes.json"
DEFAULT_THEME = "clean-默认"
DPI = 200
WIDTH_IN = 8.0
_INSTALLED = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["axes.unicode_minus"] = False


class SpecError(Exception):
    pass


# —— 主题 ——
def load_theme(name: str) -> dict:
    data = json.loads(THEMES_PATH.read_text(encoding="utf-8"))
    if name not in data["themes"]:
        raise SpecError(f"未知主题「{name}」，可选：{'、'.join(data['themes'])}")
    t = dict(data["families"][data["themes"][name]["family"]])
    t.update(data["themes"][name])
    t["name"] = name
    for k in ("font_title", "font_body", "font_num", "font_mono", "font_kpi"):
        t[k] = [f for f in t[k] if f in _INSTALLED] or ["Hiragino Sans GB", "sans-serif"]
    return t


T: dict = {}
header_height_cache = 0.0


def _lum(hexc):
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def accent_text():
    """高亮色当文字用时，对比度不足 3:1（如柠檬黄、柠檬绿）就退回墨色。"""
    return T["hi"] if contrast(T["hi"], T["paper"]) >= 3 else T["ink"]


def F(kind: str, size: float, weight="normal", color=None):
    """文字样式：kind = title / body / num / mono / kpi。"""
    return {"family": T[f"font_{kind}"], "fontsize": size, "fontweight": weight,
            "color": color or T["ink"]}


def need_source(src, where):
    if not src or not isinstance(src, list) or not all(isinstance(n, int) for n in src):
        raise SpecError(f"缺少来源编号：{where}")


def collect_sources(spec):
    out = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "source":
                    for x in v:
                        if isinstance(x, list):
                            out.update(x)
                        else:
                            out.add(x)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(spec)
    return sorted(out)


def fmt(v, unit=""):
    if isinstance(v, float) and not v.is_integer():
        s = f"{v:,.2f}".rstrip("0").rstrip(".")
    else:
        s = f"{int(v):,}"
    return f"{s}{unit}"


def text_width_in(text, kind, size, weight="normal"):
    """量一段文字渲染后的宽度（英寸），用于标题与数据卡自适应。"""
    fig = plt.figure(figsize=(WIDTH_IN, 1), dpi=DPI)
    t = fig.text(0, 0, text, **F(kind, size, weight))
    fig.canvas.draw()
    w = t.get_window_extent().width / DPI
    plt.close(fig)
    return w


def fit_title(spec):
    """标题太长：先缩到 80%，仍放不下就在标点处折成两行。"""
    avail = WIDTH_IN * 0.92
    size = T["title_size"]
    title = spec["title"]
    while text_width_in(title, "title", size, T["title_weight"]) > avail and size > T["title_size"] * 0.8:
        size -= 0.5
    lines = [title]
    if text_width_in(title, "title", size, T["title_weight"]) > avail:
        mid = len(title) // 2
        cuts = [i for i, ch in enumerate(title) if ch in "，：；、—, "]
        cut = min(cuts, key=lambda i: abs(i - mid)) + 1 if cuts else mid
        lines = [title[:cut].rstrip(), title[cut:].lstrip()]
    T["_title_size"] = size
    T["_title_lines"] = lines


def new_fig(h):
    return plt.figure(figsize=(WIDTH_IN, h), dpi=DPI, facecolor=T["paper"])


# —— 页眉页脚：三种家族各有签名 ——
def header_height(spec):
    hh = 0.3 + len(T.get("_title_lines", [1])) * (T.get("_title_size", T["title_size"]) / 72 + 0.06) + 0.06
    if spec.get("subtitle"):
        hh += 0.24
    if spec.get("kicker"):
        hh += 0.2
    if T["top_rule"]:
        hh += 0.05
    return hh + 0.15


def header_footer(fig, spec):
    h = fig.get_figheight()
    y = 1 - 0.16 / h
    if T["top_rule"]:  # 瑞士：顶部一条粗墨线
        fig.add_artist(Line2D([0.04, 0.96], [1 - 0.07 / h] * 2, color=T["ink"],
                              linewidth=T["top_rule"], transform=fig.transFigure))
        y = 1 - 0.2 / h
    if spec.get("kicker"):
        fig.text(0.04, y, spec["kicker"], va="top", ha="left",
                 **F("mono", 7.5, color=accent_text() if T["family"] == "swiss" else T["muted"]))
        y -= 0.2 / h
    ts = T.get("_title_size", T["title_size"])
    for line in T.get("_title_lines", [spec["title"]]):
        fig.text(0.04, y, line, va="top", ha="left", **F("title", ts, T["title_weight"]))
        y -= (ts / 72 + 0.06) / h
    y -= 0.06 / h
    if spec.get("subtitle"):
        fig.text(0.04, y, spec["subtitle"], va="top", ha="left", **F("body", 8.5, color=T["ink2"]))
        y -= 0.24 / h
    if T["title_rule"]:  # 杂志：标题区下一条细墨线
        fig.add_artist(Line2D([0.04, 0.96], [y + 0.02 / h] * 2, color=T["ink"],
                              linewidth=T["title_rule"], transform=fig.transFigure))
    foot = "来源：[" + ",".join(str(n) for n in collect_sources(spec)) + "]"
    if spec.get("note"):
        foot = spec["note"] + "　" + foot
    fig.text(0.04, 0.1 / h, foot, va="bottom", ha="left", **F("mono", 7, color=T["muted"]))


def style_axes(ax, grid_axis):
    ax.set_facecolor(T["paper"])
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=T["muted"], labelsize=8.5, length=0)
    if grid_axis and T["grid"]:
        ax.grid(axis=grid_axis, color=T["grid"], linewidth=0.8, linestyle="-")
        ax.set_axisbelow(True)


def set_ticklabels(ax, axis, labels, size=9.5, color=None):
    kw = F("body", size, color=color or T["ink"])
    (ax.set_yticklabels if axis == "y" else ax.set_xticklabels)(labels, **kw)


def style_numeric_ticks(ax, axis):
    for lab in (ax.get_yticklabels() if axis == "y" else ax.get_xticklabels()):
        lab.set_fontfamily(T["font_body"])
        lab.set_color(T["muted"])


def px_to_data_h(ax, px):
    y0, y1 = ax.get_ylim()
    return abs(y1 - y0) * px / ax.get_window_extent().height


def _scale(ax):
    bbox = ax.get_window_extent()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    return bbox.width / abs(x1 - x0), bbox.height / abs(y1 - y0)


def hbar(ax, y, width, height, color):
    """横条：数据端圆角（主题 radius_px，0 为直角），基线端方角。"""
    if width <= 0:
        return
    r_px = T["radius_px"] * DPI / 100
    if r_px <= 0:
        ax.add_patch(Rectangle((0, y - height / 2), width, height, linewidth=0, facecolor=color))
        return
    sx, sy = _scale(ax)
    r = min(r_px / sx, width / 2)
    ax.add_patch(FancyBboxPatch((0, y - height / 2), width, height, boxstyle=f"round,pad=0,rounding_size={r}",
                                mutation_aspect=sx / sy, linewidth=0, facecolor=color))
    ax.add_patch(Rectangle((0, y - height / 2), min(r * 1.2, width), height, linewidth=0, facecolor=color))


def vbar(ax, x, width, height, color):
    if height <= 0:
        return
    r_px = T["radius_px"] * DPI / 100
    if r_px <= 0:
        ax.add_patch(Rectangle((x, 0), width, height, linewidth=0, facecolor=color))
        return
    sx, sy = _scale(ax)
    rx = min(r_px / sx, width / 2)
    ax.add_patch(FancyBboxPatch((x, 0), width, height, boxstyle=f"round,pad=0,rounding_size={rx}",
                                mutation_aspect=sx / sy, linewidth=0, facecolor=color))
    ax.add_patch(Rectangle((x, 0), width, min(rx * sx / sy * 1.2, height), linewidth=0, facecolor=color))


def legend_row(fig, h, items, x0=0.04):
    """图例：色块 + 文字（文字不着色）。items: [(label, color)]"""
    x = x0
    y = 1 - (header_height_cache + 0.08) / h
    for lab, c in items:
        fig.patches.append(Rectangle((x, y - 0.05 / h), 0.014, 0.1 / h, transform=fig.transFigure,
                                     facecolor=c, linewidth=0.6 if c == T["card"] else 0,
                                     edgecolor=T["dim"]))
        fig.text(x + 0.02, y, lab, va="center", **F("body", 8.5, color=T["ink2"]))
        x += 0.045 + len(lab) * 0.017


# —— 各类图 ——
def render_bar(spec):
    items = spec["items"]
    for i, it in enumerate(items):
        need_source(it.get("source"), f"items[{i}] {it.get('label')}")
    n = len(items)
    top = header_height(spec)
    h = top + n * 0.42 + 0.45
    fig = new_fig(h)
    ax = fig.add_axes([0.27, 0.42 / h, 0.63, (h - top - 0.42) / h])
    style_axes(ax, None)
    vmax = max(it["value"] for it in items)
    ax.set_xlim(0, vmax * 1.2)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xticks([])
    ax.set_yticks(range(n))
    set_ticklabels(ax, "y", [it["label"] for it in items])
    any_hl = any(it.get("highlight") for it in items)
    fig.canvas.draw()
    bh = min(px_to_data_h(ax, T["bar_px"] * DPI / 100), 0.62)
    unit = spec.get("unit", "")
    if T["family"] == "magazine":  # 杂志：一条细基线
        ax.axvline(0, color=T["ink"], linewidth=0.8)
    for i, it in enumerate(items):
        hl = bool(it.get("highlight")) or not any_hl
        hbar(ax, i, it["value"], bh, T["hi"] if hl else T["dim"])
        ax.text(it["value"] + vmax * 0.015, i, fmt(it["value"], unit), va="center", ha="left",
                **F("num", 10.5 if hl else 9.5, "bold" if hl else T["num_weight"], T["ink"] if hl else T["ink2"]))
    header_footer(fig, spec)
    return fig


def render_stack(spec):
    global header_height_cache
    rows = spec["rows"]
    labels = []
    for i, r in enumerate(rows):
        for j, s in enumerate(r["segments"]):
            need_source(s.get("source"), f"rows[{i}].segments[{j}] {s.get('label')}")
            if s["label"] not in labels:
                labels.append(s["label"])
    if len(labels) > 3:
        raise SpecError("stack 最多 3 类构成，多了请合并为「其他」")
    header_height_cache = header_height(spec)
    top = header_height_cache + 0.3
    n = len(rows)
    h = top + n * 0.55 + 0.45
    fig = new_fig(h)
    ax = fig.add_axes([0.27, 0.42 / h, 0.65, (h - top - 0.42) / h])
    style_axes(ax, None)
    vmax = max(sum(s["value"] for s in r["segments"]) for r in rows)
    ax.set_xlim(0, vmax * 1.02)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xticks([])
    ax.set_yticks(range(n))
    set_ticklabels(ax, "y", [r["label"] for r in rows])
    fig.canvas.draw()
    bh = min(px_to_data_h(ax, T["bar_px"] * DPI / 100), 0.62)
    bbox = ax.get_window_extent()
    gap = 2 * DPI / 100 * vmax * 1.02 / bbox.width
    hl = spec.get("highlight")
    others = [x for x in labels if x != hl]
    shades = [T["dim"], T["card"]]
    colors = {}
    for k, lab in enumerate(labels):
        if hl:
            colors[lab] = T["hi"] if lab == hl else shades[others.index(lab) % 2]
        else:
            colors[lab] = T["series"][k]
    unit = spec.get("unit", "")
    for i, r in enumerate(rows):
        x = 0
        for s in r["segments"]:
            c, w = colors[s["label"]], s["value"]
            ax.add_patch(Rectangle((x, i - bh / 2), max(w - gap, 0), bh, linewidth=0, facecolor=c))
            txt = fmt(w, unit)
            if w / (vmax * 1.02) * bbox.width > len(txt) * 9 * DPI / 100:
                on = T["hi_on"] if c == T["hi"] else T["ink"]
                ax.text(x + w / 2, i, txt, ha="center", va="center", **F("num", 9, color=on))
            x += w
    legend_row(fig, h, [(lab, colors[lab]) for lab in labels], x0=0.27)
    header_footer(fig, spec)
    return fig


def render_grouped(spec):
    global header_height_cache
    cats, series = spec["categories"], spec["series"]
    if len(series) > 3:
        raise SpecError("grouped 最多 3 个序列")
    for k, s in enumerate(series):
        src = s.get("source")
        if src and isinstance(src[0], list):
            for j, sj in enumerate(src):
                need_source(sj, f"series[{k}].source[{j}]")
        else:
            need_source(src, f"series[{k}] {s.get('name')}")
    header_height_cache = header_height(spec)
    top = header_height_cache + (0.3 if len(series) > 1 else 0)
    h = top + 2.4
    fig = new_fig(h)
    ax = fig.add_axes([0.08, 0.55 / h, 0.88, (h - top - 0.55) / h])
    style_axes(ax, "y")
    n, m = len(cats), len(series)
    vmax = max(max(s["values"]) for s in series)
    ax.set_ylim(0, vmax * 1.22)
    ax.set_xlim(-0.6, n - 0.4)
    fig.canvas.draw()
    unit_w = (n + 0.2) / ax.get_window_extent().width
    bw = min(T["bar_px"] * 1.6 * DPI / 100 * unit_w, 0.8 / m)
    gap = 2 * DPI / 100 * unit_w
    unit = spec.get("unit", "")
    single = m == 1
    hi_idx = max(range(n), key=lambda i: series[0]["values"][i]) if single else None
    for k, s in enumerate(series):
        for i, v in enumerate(s["values"]):
            x = i - (m * bw + (m - 1) * gap) / 2 + k * (bw + gap)
            is_hi = single and i == hi_idx
            c = (T["hi"] if is_hi else T["dim"]) if single else T["series"][k]
            vbar(ax, x, bw, v, c)
            ax.text(x + bw / 2, v + vmax * 0.025, fmt(v, unit), ha="center", va="bottom",
                    **F("num", 10 if is_hi else 9, "bold" if is_hi else T["num_weight"],
                        T["ink"] if is_hi else T["ink2"]))
    if T["family"] == "magazine":
        ax.axhline(0, color=T["ink"], linewidth=0.8)
        ax.set_yticks([])
    else:
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
        style_numeric_ticks(ax, "y")
    ax.set_xticks(range(n))
    set_ticklabels(ax, "x", cats, 9.5)
    if not single:
        legend_row(fig, h, [(s["name"], T["series"][k]) for k, s in enumerate(series)], x0=0.08)
    header_footer(fig, spec)
    return fig


def render_line(spec):
    global header_height_cache
    xs, series = spec["x"], spec["series"]
    if len(series) > 3:
        raise SpecError("line 最多 3 个序列")
    for k, s in enumerate(series):
        need_source(s.get("source"), f"series[{k}] {s.get('name')}")
    header_height_cache = header_height(spec)
    top = header_height_cache + (0.3 if len(series) > 1 else 0)
    h = top + 2.3
    fig = new_fig(h)
    ax = fig.add_axes([0.09, 0.55 / h, 0.8, (h - top - 0.55) / h])
    style_axes(ax, "y")
    idx = list(range(len(xs)))
    vals = [v for s in series for v in s["values"] if v is not None]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.25 or hi * 0.1
    ax.set_ylim(0 if spec.get("zero_base") else max(0, lo - pad), hi + pad)
    unit = spec.get("unit", "")
    lw = T["line_px"] * 72 / 100
    for k, s in enumerate(series):
        c = T["series"][k] if len(series) > 1 else T["hi"]
        pts = [(i, v) for i, v in zip(idx, s["values"]) if v is not None]
        for (i0, v0), (i1, v1) in zip(pts, pts[1:]):
            ax.plot([i0, i1], [v0, v1], color=c, linewidth=lw,
                    linestyle="-" if i1 - i0 == 1 else (0, (2, 3)), solid_capstyle="round")
        for (i, v), end in ((pts[0], False), (pts[-1], True)):
            ax.scatter([i], [v], s=40, color=c, edgecolors=T["paper"], linewidths=1.6, zorder=3,
                       marker="s" if T["family"] == "swiss" else "o")
            ax.text(i + (0.18 if end else -0.18), v, fmt(v, unit), ha="left" if end else "right", va="center",
                    **F("num", 10 if end else 9, "bold" if end else T["num_weight"], T["ink"] if end else T["ink2"]))
    ax.set_xticks(idx)
    set_ticklabels(ax, "x", xs, 8.5, T["muted"])
    ax.set_xlim(-0.7, len(xs) - 0.3)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
    style_numeric_ticks(ax, "y")
    if len(series) > 1:
        legend_row(fig, h, [(s["name"], T["series"][k]) for k, s in enumerate(series)], x0=0.09)
    header_footer(fig, spec)
    return fig


def render_units(spec):
    groups = spec["groups"]
    for i, g in enumerate(groups):
        need_source(g.get("source"), f"groups[{i}] {g.get('label')}")
    total = sum(g["count"] for g in groups)
    if total > 100:
        raise SpecError("units 总数不超过 100，请先换算成每 N 人")
    per_row = min(total, 20)
    rows = (total + per_row - 1) // per_row
    top = header_height(spec) + 0.3
    h = top + rows * 0.42 + 0.45
    fig = new_fig(h)
    ax = fig.add_axes([0.04, 0.42 / h, 0.92, (h - top - 0.42) / h])
    ax.set_facecolor(T["paper"])
    ax.axis("off")
    ax.set_xlim(-0.6, per_row - 0.4)
    ax.set_ylim(rows - 0.5, -0.5)
    ax.set_aspect("equal", adjustable="box")
    any_hl = any(g.get("highlight") for g in groups)
    k = 0
    for gi, g in enumerate(groups):
        filled = g.get("highlight") or (not any_hl and gi == 0)
        for _ in range(g["count"]):
            r, c = divmod(k, per_row)
            if T["unit_shape"] == "square":
                ax.add_patch(Rectangle((c - 0.33, r - 0.33), 0.66, 0.66, linewidth=0 if filled else 1.4,
                                       facecolor=T["hi"] if filled else T["paper"], edgecolor=T["dim"]))
            else:
                ax.add_patch(Circle((c, r), 0.32, facecolor=T["hi"] if filled else T["paper"],
                                    edgecolor=T["dim"], linewidth=0 if filled else 1.4))
            k += 1
    x = 0.04
    y = 1 - (header_height(spec) + 0.08) / h
    for g in groups:
        filled = g.get("highlight") or (not any_hl and g is groups[0])
        mark = ("■" if filled else "□") if T["unit_shape"] == "square" else ("●" if filled else "○")
        fig.text(x, y, mark, va="center", **F("body", 10, color=(T["hi"] if contrast(T["hi"], T["paper"]) >= 1.5 else T["ink"]) if filled else T["dim"]))
        fig.text(x + 0.022, y, f"{g['label']}  {g['count']}", va="center", **F("body", 8.5, color=T["ink2"]))
        x += 0.07 + len(g["label"]) * 0.02
    header_footer(fig, spec)
    return fig


def render_kpi(spec):
    tiles = spec["tiles"]
    if not 2 <= len(tiles) <= 4:
        raise SpecError("kpi 需要 2—4 张卡")
    for i, t in enumerate(tiles):
        need_source(t.get("source"), f"tiles[{i}] {t.get('label')}")
    top = header_height(spec)
    h = top + 1.6
    fig = new_fig(h)
    w = 0.92 / len(tiles)
    y_top = 1 - top / h
    y_bot = 0.42 / h
    style = T["kpi_style"]
    for i, t in enumerate(tiles):
        x = 0.04 + i * w
        first = i == 0
        txt_c = T["ink"]
        if style == "card":
            fig.patches.append(FancyBboxPatch((x + 0.006, y_bot), w - 0.02, y_top - y_bot,
                                              boxstyle="round,pad=0,rounding_size=0.015",
                                              transform=fig.transFigure, facecolor=T["card"], linewidth=0))
        elif style == "rule":  # 杂志：每张卡顶一条墨线，不加底色
            fig.add_artist(Line2D([x + 0.006, x + w - 0.02], [y_top] * 2, color=T["ink"],
                                  linewidth=1.6 if first else 0.8, transform=fig.transFigure))
        elif style == "block":  # 瑞士：第一张实色高亮块，其余顶部粗线
            if first:
                fig.patches.append(Rectangle((x + 0.006, y_bot), w - 0.02, y_top - y_bot, transform=fig.transFigure,
                                             facecolor=T["hi"], linewidth=0))
                txt_c = T["hi_on"]
            else:
                fig.add_artist(Line2D([x + 0.006, x + w - 0.02], [y_top] * 2, color=T["ink"],
                                      linewidth=2.2, transform=fig.transFigure))
        pad = 0.022
        sub_c = txt_c if txt_c != T["ink"] else T["ink2"]
        fig.text(x + pad, y_top - 0.18 / h, t["label"], va="top", **F("body", 8.5, color=sub_c))
        size = T["kpi_size"]
        room = (w - 0.02 - 2 * pad) * WIDTH_IN
        while text_width_in(t["value"], "kpi", size, T["kpi_weight"]) > room and size > 12:
            size -= 1
        fig.text(x + pad, (y_top + y_bot) / 2 - 0.02 / h, t["value"], va="center",
                 **F("kpi", size, T["kpi_weight"], txt_c))
        if t.get("note"):
            fig.text(x + pad, y_bot + 0.14 / h, t["note"], va="bottom",
                     **F("body", 7.5, color=sub_c if (style == "block" and first) else T["muted"]))
    header_footer(fig, spec)
    return fig


RENDER = {"bar": render_bar, "stack": render_stack, "grouped": render_grouped, "line": render_line,
          "units": render_units, "kpi": render_kpi}


def render_file(spec_path: Path, out: Path, theme):
    global T, header_height_cache
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    for k in ("type", "title"):
        if k not in spec:
            raise SpecError(f"缺字段 {k}")
    if spec["type"] not in RENDER:
        raise SpecError(f"未知类型 {spec['type']}，可选：{', '.join(RENDER)}")
    T = load_theme(spec.get("theme") or theme or DEFAULT_THEME)
    fit_title(spec)
    header_height_cache = header_height(spec)
    fig = RENDER[spec["type"]](spec)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=DPI, facecolor=T["paper"])
    plt.close(fig)
    return "[" + ",".join(str(n) for n in collect_sources(spec)) + "]"


def arg(a, name, default=None):
    return a[a.index(name) + 1] if name in a else default


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    if a[0] == "--themes":
        data = json.loads(THEMES_PATH.read_text(encoding="utf-8"))
        for name, t in data["themes"].items():
            print(f"{name:12s} {t['family']:9s} {t.get('适合', '')}")
        return 0
    theme = arg(a, "--theme")
    try:
        if a[0] == "--all":
            d = Path(a[1])
            out_dir = Path(arg(a, "--out-dir", str(d.parent)))
            n = 0
            for p in sorted(d.glob("*.json")):
                render_file(p, out_dir / (p.stem + ".png"), theme)
                n += 1
            print(f"— 渲染 {n} 张（主题：{theme or '各图自带或默认'}）")
        else:
            p = Path(a[0])
            out = Path(arg(a, "--out", str(p.parent.parent / (p.stem + ".png"))))
            srcs = render_file(p, out, theme)
            print(f"ok  {out}  来源 {srcs}")
    except SpecError as e:
        print(f"错误：{e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
