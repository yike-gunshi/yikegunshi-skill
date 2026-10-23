#!/usr/bin/env python3
"""下载案例图到仓库 assets/，带 UA 与 Referer（过微信等站的防盗链）。

用法: python3 save_media.py <图片URL> <目标路径> [--referer <来源页URL>]

目标路径的扩展名与实际 Content-Type 不符时自动纠正（微信图片 URL 常无扩展名）。
成功打印最终路径；失败重试一次后 exit 1，由调用方决定是否保留原 URL 兜底。
超过 5MB 拒绝保存（库的红线：大媒体不进 git）。
"""
import argparse
import sys
import time
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
EXT_BY_TYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
               "image/webp": ".webp", "image/svg+xml": ".svg"}
MAX_BYTES = 5 * 1024 * 1024


def fetch(url: str, referer: str | None) -> tuple[bytes, str]:
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read(MAX_BYTES + 1)
        ctype = resp.headers.get("Content-Type", "").split(";")[0].strip()
    if len(data) > MAX_BYTES:
        sys.exit(f"拒绝保存: 超过 5MB 上限 ({url})")
    if not ctype.startswith("image/"):
        raise ValueError(f"返回的内容类型是 {ctype or '未知'}，疑似防盗链页")
    return data, ctype


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("dest")
    ap.add_argument("--referer", default=None)
    args = ap.parse_args()

    last_err = None
    for attempt in (1, 2):
        try:
            data, ctype = fetch(args.url, args.referer)
            break
        except Exception as e:  # noqa: BLE001 - 统一重试后如实上报
            last_err = e
            if attempt == 1:
                time.sleep(2)
    else:
        sys.exit(f"下载失败（已重试）: {last_err}")

    dest = Path(args.dest)
    right_ext = EXT_BY_TYPE.get(ctype)
    if right_ext and dest.suffix.lower() != right_ext:
        dest = dest.with_suffix(right_ext)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(dest)


if __name__ == "__main__":
    main()
