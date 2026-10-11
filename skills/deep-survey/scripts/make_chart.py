#!/usr/bin/env python3
"""把一份图表数据（JSON）渲染成 PNG，嵌进 md 报告。

用法：
  python3 make_chart.py <spec.json> [--out <png路径>]
  python3 make_chart.py --all <charts/data 目录> [--out-dir <charts 目录>]

规则：
- 每个数值都必须带 source（来源编号列表），缺一个就报错退出——图里的数字和正文一样要可追溯。
- 标题写成判断句；subtitle 写单位与口径；图下自动加「来源：[n]…」。
- 配色取 dataviz 参考调色板（已用 validate_palette.js 验过前三个分类色）：
  强调一个、其余置灰；多序列最多 3 个。

图表类型与 JSON 字段：
  bar     横向条形。items: [{label, value, source:[n], highlight?:bool}]，unit?
  grouped 分组柱。categories: [..]; series: [{name, values:[..], source:[[n]..] 或 [n]}]（≤3 个序列）
  line    折线。x: [..]; series: [{name, values:[..], source:[n]}]（≤3 个序列）；缺数据填 null，缺口画成虚线
  stack   横向堆叠条（构成 / 一笔账）。rows: [{label, segments:[{label, value, source:[n]}]}]，unit?，
          highlight?: "要强调的那一类构成"（其余置灰）
  units   单位图。groups: [{label, count, source:[n], highlight?:bool}]（总数 ≤100）
  kpi     数据卡。tiles: [{label, value:"文本", note?, source:[n]}]（2—4 张）
公共字段：type, title, subtitle?, note?
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle  # noqa: E402

# —— 调色板（dataviz reference palette，浅色）——
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # 前三个分类色：全对比通过
DIM = "#c9c7bf"  # 非强调项的灰
BAR_PX = 22  # 条宽上限（像素）
DPI = 200
WIDTH_IN = 8.0

for name in ("Hiragino Sans GB", "PingFang SC", "Heiti TC", "Arial Unicode MS"):
    if any(name == f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = name
        break
plt.rcParams["axes.unicode_minus"] = False


class SpecError(Exception):
    pass


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


def new_fig(height_in):
    fig = plt.figure(figsize=(WIDTH_IN, height_in), dpi=DPI, facecolor=SURFACE)
    return fig


def header_footer(fig, spec, top_frac, bottom_frac):
    fig.text(0.04, 1 - 0.18 / fig.get_figheight(), spec["title"], fontsize=13, fontweight="bold",
             color=TEXT, ha="left", va="top")
    if spec.get("subtitle"):
        fig.text(0.04, 1 - 0.48 / fig.get_figheight(), spec["subtitle"], fontsize=9, color=TEXT2,
                 ha="left", va="top")
    srcs = collect_sources(spec)
    foot = "来源：[" + ",".join(str(n) for n in srcs) + "]"
    if spec.get("note"):
        foot = spec["note"] + "　" + foot
    fig.text(0.04, 0.12 / fig.get_figheight(), foot, fontsize=8, color=MUTED, ha="left", va="bottom")


def style_axes(ax, grid_axis):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8, linestyle="-")
        ax.set_axisbelow(True)


def px_to_data_h(ax, fig, px):
    """竖直方向 px 像素对应多少数据单位。"""
    h_px = ax.get_window_extent().height
    y0, y1 = ax.get_ylim()
    return abs(y1 - y0) * px / h_px


def rounded_hbar(ax, y, width, height, color, radius_px, fig):
    """横条：数据端 4px 圆角，基线端方角。"""
    if width <= 0:
        return
    bbox = ax.get_window_extent()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    sx = bbox.width / abs(x1 - x0)
    sy = bbox.height / abs(y1 - y0)
    r = min(radius_px / sx, width / 2)
    patch = FancyBboxPatch((0, y - height / 2), width, height,
                           boxstyle=f"round,pad=0,rounding_size={r}",
                           mutation_aspect=sx / sy, linewidth=0, facecolor=color)
    ax.add_patch(patch)
    ax.add_patch(Rectangle((0, y - height / 2), min(r * 1.2, width), height, linewidth=0, facecolor=color))


def rounded_vbar(ax, x, width, height, color, radius_px):
    """竖柱：顶端 4px 圆角，基线端方角。"""
    if height <= 0:
        return
    bbox = ax.get_window_extent()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    sx = bbox.width / abs(x1 - x0)
    sy = bbox.height / abs(y1 - y0)
    rx = min(radius_px / sx, width / 2)
    ry = rx * sx / sy
    ax.add_patch(FancyBboxPatch((x, 0), width, height, boxstyle=f"round,pad=0,rounding_size={rx}",
                                mutation_aspect=sx / sy, linewidth=0, facecolor=color))
    ax.add_patch(Rectangle((x, 0), width, min(ry * 1.2, height), linewidth=0, facecolor=color))


def render_bar(spec):
    items = spec["items"]
    for i, it in enumerate(items):
        need_source(it.get("source"), f"items[{i}] {it.get('label')}")
    n = len(items)
    h = 0.95 + n * 0.42 + 0.35
    fig = new_fig(h)
    ax = fig.add_axes([0.26, 0.38 / h, 0.66, (h - 0.95 - 0.35) / h])
    style_axes(ax, None)
    vmax = max(it["value"] for it in items)
    ax.set_xlim(0, vmax * 1.18)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xticks([])
    ax.set_yticks(range(n))
    ax.set_yticklabels([it["label"] for it in items], fontsize=10, color=TEXT)
    any_hl = any(it.get("highlight") for it in items)
    fig.canvas.draw()
    bar_h = min(px_to_data_h(ax, fig, BAR_PX * DPI / 100), 0.62)
    unit = spec.get("unit", "")
    for i, it in enumerate(items):
        color = SERIES[0] if (it.get("highlight") or not any_hl) else DIM
        rounded_hbar(ax, i, it["value"], bar_h, color, 4 * DPI / 100, fig)
        ax.text(it["value"] + vmax * 0.015, i, fmt(it["value"], unit), va="center", ha="left",
                fontsize=10, color=TEXT if it.get("highlight") else TEXT2,
                fontweight="bold" if it.get("highlight") else "normal")
    header_footer(fig, spec, 0, 0)
    return fig


def render_stack(spec):
    rows = spec["rows"]
    labels = []
    for i, r in enumerate(rows):
        for j, s in enumerate(r["segments"]):
            need_source(s.get("source"), f"rows[{i}].segments[{j}] {s.get('label')}")
            if s["label"] not in labels:
                labels.append(s["label"])
    if len(labels) > 3:
        raise SpecError("stack 最多 3 类构成，多了请合并为「其他」")
    n = len(rows)
    h = 1.25 + n * 0.55 + 0.35
    fig = new_fig(h)
    ax = fig.add_axes([0.26, 0.38 / h, 0.66, (h - 1.25 - 0.35) / h])
    style_axes(ax, None)
    totals = [sum(s["value"] for s in r["segments"]) for r in rows]
    vmax = max(totals)
    ax.set_xlim(0, vmax * 1.02)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xticks([])
    ax.set_yticks(range(n))
    ax.set_yticklabels([r["label"] for r in rows], fontsize=10, color=TEXT)
    fig.canvas.draw()
    bar_h = min(px_to_data_h(ax, fig, BAR_PX * DPI / 100), 0.62)
    bbox = ax.get_window_extent()
    gap = 2 * DPI / 100 * vmax * 1.02 / bbox.width
    unit = spec.get("unit", "")
    hl = spec.get("highlight")
    colors = {lab: (SERIES[0] if lab == hl else (DIM if hl else SERIES[k])) for k, lab in enumerate(labels)}
    if hl:
        dims = [lab for lab in labels if lab != hl]
        shades = ["#c9c7bf", "#e1e0d9"]
        for k, lab in enumerate(dims):
            colors[lab] = shades[k % 2]
    for i, r in enumerate(rows):
        x = 0
        for s in r["segments"]:
            c = colors[s["label"]]
            w = s["value"]
            ax.add_patch(Rectangle((x, i - bar_h / 2), max(w - gap, 0), bar_h, linewidth=0, facecolor=c))
            txt = fmt(w, unit)
            seg_px = w / (vmax * 1.02) * bbox.width
            if seg_px > len(txt) * 9 * DPI / 100:
                ax.text(x + w / 2, i, txt, ha="center", va="center", fontsize=9,
                        color="white" if c in SERIES else TEXT)
            x += w
    # 图例：色块 + 文字（文字不着色）
    lx = 0.26
    for k, lab in enumerate(labels):
        fig.patches.append(Rectangle((lx, 1 - 0.95 / h), 0.014, 0.12 / h, transform=fig.transFigure,
                                     facecolor=colors[lab], linewidth=0))
        fig.text(lx + 0.02, 1 - 0.89 / h, lab, fontsize=9, color=TEXT2, va="center")
        lx += 0.04 + len(lab) * 0.018
    header_footer(fig, spec, 0, 0)
    return fig


def render_grouped(spec):
    cats = spec["categories"]
    series = spec["series"]
    if len(series) > 3:
        raise SpecError("grouped 最多 3 个序列")
    for k, s in enumerate(series):
        src = s.get("source")
        if src and isinstance(src[0], list):
            for j, sj in enumerate(src):
                need_source(sj, f"series[{k}].source[{j}]")
        else:
            need_source(src, f"series[{k}] {s.get('name')}")
    top = 1.35 if len(series) > 1 else 1.0
    h = 3.4
    fig = new_fig(h)
    ax = fig.add_axes([0.08, 0.55 / h, 0.88, (h - top - 0.55) / h])
    style_axes(ax, "y")
    n, m = len(cats), len(series)
    vmax = max(max(s["values"]) for s in series)
    ax.set_ylim(0, vmax * 1.2)
    ax.set_xlim(-0.6, n - 0.4)
    fig.canvas.draw()
    bbox = ax.get_window_extent()
    unit_w = 1.2 / bbox.width * (n)  # 每像素多少数据单位（x 轴）
    bw = min(BAR_PX * DPI / 100 * unit_w, 0.8 / m)
    gap = 2 * DPI / 100 * unit_w
    unit = spec.get("unit", "")
    for k, s in enumerate(series):
        for i, v in enumerate(s["values"]):
            x = i - (m * bw + (m - 1) * gap) / 2 + k * (bw + gap)
            rounded_vbar(ax, x, bw, v, SERIES[k], 4 * DPI / 100)
            ax.text(x + bw / 2, v + vmax * 0.02, fmt(v, unit), ha="center", va="bottom", fontsize=8.5, color=TEXT2)
    ax.set_xticks(range(n))
    ax.set_xticklabels(cats, fontsize=10, color=TEXT)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
    lx = 0.08
    for k, s in enumerate(series if len(series) > 1 else []):
        fig.patches.append(Rectangle((lx, 1 - 0.95 / h), 0.014, 0.1 / h, transform=fig.transFigure,
                                     facecolor=SERIES[k], linewidth=0))
        fig.text(lx + 0.02, 1 - 0.9 / h, s["name"], fontsize=9, color=TEXT2, va="center")
        lx += 0.05 + len(s["name"]) * 0.018
    header_footer(fig, spec, 0, 0)
    return fig


def render_line(spec):
    xs = spec["x"]
    series = spec["series"]
    if len(series) > 3:
        raise SpecError("line 最多 3 个序列")
    for k, s in enumerate(series):
        need_source(s.get("source"), f"series[{k}] {s.get('name')}")
    top = 1.3 if len(series) > 1 else 0.95
    h = 3.3
    fig = new_fig(h)
    ax = fig.add_axes([0.09, 0.55 / h, 0.8, (h - top - 0.55) / h])
    style_axes(ax, "y")
    idx = list(range(len(xs)))
    vals = [v for s in series for v in s["values"] if v is not None]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.25 or hi * 0.1
    ax.set_ylim(max(0, lo - pad) if spec.get("zero_base") is not True else 0, hi + pad)
    unit = spec.get("unit", "")
    for k, s in enumerate(series):
        pts = [(i, v) for i, v in zip(idx, s["values"]) if v is not None]
        # 有数据的相邻点画实线；中间缺数据的区间画虚线，避免把插值画成像真数据
        for (i0, v0), (i1, v1) in zip(pts, pts[1:]):
            ax.plot([i0, i1], [v0, v1], color=SERIES[k], linewidth=2 * 72 / 100,
                    linestyle="-" if i1 - i0 == 1 else (0, (2, 3)),
                    solid_capstyle="round", solid_joinstyle="round")
        for (i, v), lab in ((pts[0], "start"), (pts[-1], "end")):
            ax.add_patch(Circle((i, v), 0, color=SERIES[k]))
            ax.scatter([i], [v], s=36, color=SERIES[k], edgecolors=SURFACE, linewidths=1.5, zorder=3)
            ax.text(i + (0.15 if lab == "end" else -0.15), v, fmt(v, unit), fontsize=9, color=TEXT2,
                    ha="left" if lab == "end" else "right", va="center")
    ax.set_xticks(idx)
    ax.set_xticklabels(xs, fontsize=8.5, color=MUTED, rotation=0)
    ax.set_xlim(-0.6, len(xs) - 0.4)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
    if len(series) > 1:
        lx = 0.09
        for k, s in enumerate(series):
            fig.patches.append(Rectangle((lx, 1 - 0.95 / h), 0.02, 0.025 / h * 2, transform=fig.transFigure,
                                         facecolor=SERIES[k], linewidth=0))
            fig.text(lx + 0.026, 1 - 0.93 / h, s["name"], fontsize=9, color=TEXT2, va="center")
            lx += 0.06 + len(s["name"]) * 0.018
    header_footer(fig, spec, 0, 0)
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
    h = 1.15 + rows * 0.42 + 0.45
    fig = new_fig(h)
    ax = fig.add_axes([0.04, 0.4 / h, 0.92, (h - 1.15 - 0.4) / h])
    ax.set_facecolor(SURFACE)
    ax.axis("off")
    ax.set_xlim(-0.6, per_row - 0.4)
    ax.set_ylim(rows - 0.5, -0.5)
    ax.set_aspect("equal", adjustable="box")
    k = 0
    any_hl = any(g.get("highlight") for g in groups)
    for gi, g in enumerate(groups):
        filled = g.get("highlight") or (not any_hl and gi == 0)
        for _ in range(g["count"]):
            r, c = divmod(k, per_row)
            if filled:
                ax.add_patch(Circle((c, r), 0.32, facecolor=SERIES[0], linewidth=0))
            else:
                ax.add_patch(Circle((c, r), 0.32, facecolor=SURFACE, edgecolor=DIM, linewidth=1.6))
            k += 1
    lx = 0.04
    for g in groups:
        filled = g.get("highlight") or (not any_hl and g is groups[0])
        fig.text(lx, 1 - 0.9 / h, "●" if filled else "○", fontsize=11, color=SERIES[0] if filled else DIM, va="center")
        fig.text(lx + 0.022, 1 - 0.9 / h, f"{g['label']}：{g['count']}", fontsize=9, color=TEXT2, va="center")
        lx += 0.06 + len(g["label"]) * 0.02
    header_footer(fig, spec, 0, 0)
    return fig


def render_kpi(spec):
    tiles = spec["tiles"]
    if not 2 <= len(tiles) <= 4:
        raise SpecError("kpi 需要 2—4 张卡")
    for i, t in enumerate(tiles):
        need_source(t.get("source"), f"tiles[{i}] {t.get('label')}")
    h = 2.5
    fig = new_fig(h)
    n = len(tiles)
    w = 0.92 / n
    for i, t in enumerate(tiles):
        x = 0.04 + i * w
        fig.patches.append(FancyBboxPatch((x + 0.008, 0.42 / h), w - 0.024, (h - 1.25) / h,
                                          boxstyle="round,pad=0,rounding_size=0.02",
                                          transform=fig.transFigure, facecolor="#f3f2ef", linewidth=0))
        fig.text(x + 0.025, (h - 0.98) / h, t["label"], fontsize=9, color=TEXT2, va="top")
        fig.text(x + 0.025, (h - 1.62) / h, t["value"], fontsize=22, color=TEXT, fontweight="bold", va="center")
        if t.get("note"):
            fig.text(x + 0.025, 0.58 / h, t["note"], fontsize=8, color=MUTED, va="center")
    header_footer(fig, spec, 0, 0)
    return fig


RENDER = {"bar": render_bar, "stack": render_stack, "grouped": render_grouped, "line": render_line,
          "units": render_units, "kpi": render_kpi}


def render_file(spec_path: Path, out: Path):
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    for k in ("type", "title"):
        if k not in spec:
            raise SpecError(f"缺字段 {k}")
    if spec["type"] not in RENDER:
        raise SpecError(f"未知类型 {spec['type']}，可选：{', '.join(RENDER)}")
    fig = RENDER[spec["type"]](spec)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    srcs = "[" + ",".join(str(n) for n in collect_sources(spec)) + "]"
    return f"![{spec['title']}]({out.name if out.parent.name == 'charts' else out})", srcs


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    try:
        if args[0] == "--all":
            d = Path(args[1])
            out_dir = Path(args[args.index("--out-dir") + 1]) if "--out-dir" in args else d.parent
            ok = 0
            for p in sorted(d.glob("*.json")):
                out = out_dir / (p.stem + ".png")
                render_file(p, out)
                print(f"ok  {out}")
                ok += 1
            print(f"— 渲染 {ok} 张")
        else:
            p = Path(args[0])
            out = Path(args[args.index("--out") + 1]) if "--out" in args else p.parent.parent / (p.stem + ".png")
            snippet, srcs = render_file(p, out)
            print(f"ok  {out}  来源 {srcs}")
    except SpecError as e:
        print(f"错误：{e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
