#!/usr/bin/env python3
"""用无头浏览器出两类图：Mermaid 结构图、网页截图。都输出 PNG，嵌进 md。

为什么要把 Mermaid 渲染成图片：VS Code 默认预览不渲染 Mermaid，Obsidian 的支持随版本变；
图片在哪都能看。Mermaid 源文件留在旁边，方便以后改。

用法：
  python3 render_visual.py mermaid <图.mmd> [--out <图.png>] [--width 1200]
  python3 render_visual.py shot <URL> --out <截图.png> [--width 1280] [--height 800] [--selector CSS] [--full]

依赖：Python playwright 与 Chromium（本机已装）。Mermaid 脚本从 cdn.jsdelivr.net 加载；
如果环境变量 HTTPS_PROXY / HTTP_PROXY 存在，浏览器走该代理。
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
FONT = '"Hiragino Sans GB","PingFang SC","Heiti SC",sans-serif'
# 反爬拦截页的特征文字：命中就不保存，避免把「被拦截」当产品截图放进报告
BLOCK_HINTS = ("you have been blocked", "just a moment", "verify you are human", "access denied",
               "attention required", "captcha", "unusual traffic", "请完成安全验证", "访问被拒绝")


MAX_W = 2000  # 太宽的图在部分编辑器里会显示成空白，统一缩到 2000 像素宽


def shrink(path: Path):
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(path)
    if im.width > MAX_W:
        im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS).save(path, optimize=True)


def launch(p):
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("https_proxy")
    kw = {"proxy": {"server": proxy}} if proxy else {}
    return p.chromium.launch(**kw)


def mermaid(src: Path, out: Path, width: int):
    code = src.read_text(encoding="utf-8")
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>body{{margin:0;background:#fcfcfb;font-family:{FONT}}}#c{{padding:24px;display:inline-block}}</style>
<script src="{MERMAID_CDN}"></script></head><body><div id="c"><pre class="mermaid">{code}</pre></div>
<script>mermaid.initialize({{startOnLoad:false,theme:"base",fontFamily:'{FONT}',
flowchart:{{useMaxWidth:false}},timeline:{{useMaxWidth:false}},
themeVariables:{{primaryColor:"#e8f0fb",primaryBorderColor:"#2a78d6",primaryTextColor:"#0b0b0b",
lineColor:"#898781",secondaryColor:"#f3f2ef",tertiaryColor:"#fcfcfb",fontSize:"20px"}}}});
mermaid.run().then(()=>document.body.setAttribute("data-done","1"))
.catch(e=>{{document.body.setAttribute("data-err",String(e));}});</script></body></html>"""
    with sync_playwright() as p:
        b = launch(p)
        pg = b.new_page(viewport={"width": width, "height": 800}, device_scale_factor=2)
        pg.set_content(html, wait_until="networkidle", timeout=60000)
        pg.wait_for_function("document.body.dataset.done || document.body.dataset.err", timeout=60000)
        err = pg.evaluate("document.body.dataset.err")
        if err:
            b.close()
            raise SystemExit(f"Mermaid 渲染失败：{err}")
        out.parent.mkdir(parents=True, exist_ok=True)
        pg.locator("#c").screenshot(path=str(out))
        b.close()
    shrink(out)
    print(f"ok  {out}")


def shot(url: str, out: Path, width: int, height: int, selector: str | None, full: bool):
    with sync_playwright() as p:
        b = launch(p)
        pg = b.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
        pg.goto(url, wait_until="networkidle", timeout=60000)
        body = (pg.inner_text("body") or "")[:3000].lower()
        hit = next((h for h in BLOCK_HINTS if h in body), None)
        if hit:
            b.close()
            raise SystemExit(f"被拦截（页面含「{hit}」），未保存。换应用商店页面、官方博客配图，或请用户在自己的浏览器里截图")
        out.parent.mkdir(parents=True, exist_ok=True)
        if selector:
            pg.locator(selector).first.screenshot(path=str(out))
        else:
            pg.screenshot(path=str(out), full_page=full)
        b.close()
    shrink(out)
    print(f"ok  {out}")


def arg(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        return 2
    if a[0] == "mermaid":
        src = Path(a[1])
        out = Path(arg(a, "--out", str(src.with_suffix(".png"))))
        mermaid(src, out, int(arg(a, "--width", 1200)))
    elif a[0] == "shot":
        out = arg(a, "--out")
        if not out:
            print("shot 需要 --out")
            return 2
        shot(a[1], Path(out), int(arg(a, "--width", 1280)), int(arg(a, "--height", 800)),
             arg(a, "--selector"), "--full" in a)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
