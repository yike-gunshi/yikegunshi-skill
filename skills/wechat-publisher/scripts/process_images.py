#!/usr/bin/env python3
"""
process_images.py - 从 Markdown 提取图片（远程 URL + 本地路径），压缩、上传到阿里云 OSS

用法:
    python3 process_images.py <md_file> <folder_name>

示例:
    python3 process_images.py ./article.md 2026-02-16_2025年终总结

输出:
    将 URL 映射 JSON 写入 <md_file_dir>/image_urls.json
    格式: { "原始路径": "OSS URL" }
"""

import sys
import os
import re
import json
import tempfile
import subprocess
import urllib.request
import urllib.parse

import oss2

# ── OSS 凭据（从环境变量读取；运行前先 export） ──────────
OSS_ACCESS_KEY_ID = os.environ.get('OSS_ACCESS_KEY_ID', '')
OSS_ACCESS_KEY_SECRET = os.environ.get('OSS_ACCESS_KEY_SECRET', '')
OSS_ENDPOINT = os.environ.get('OSS_ENDPOINT', 'https://oss-cn-beijing.aliyuncs.com')
OSS_BUCKET = os.environ.get('OSS_BUCKET', 'your-oss-bucket')
OSS_PUBLIC_URL = f'https://{OSS_BUCKET}.oss-cn-beijing.aliyuncs.com'


def extract_all_images(md_path):
    """从 Markdown 文件中提取所有图片：远程 URL 和本地路径"""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 匹配 ![alt](path_or_url) 格式
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    matches = re.findall(pattern, content)

    remote_images = []  # (alt, url)
    local_images = []   # (alt, raw_path, resolved_path)
    md_dir = os.path.dirname(os.path.abspath(md_path))

    for alt, path in matches:
        if path.startswith('http://') or path.startswith('https://'):
            remote_images.append((alt, path))
        else:
            # URL-decode the path (e.g., %20 -> space)
            decoded_path = urllib.parse.unquote(path)
            resolved = os.path.normpath(os.path.join(md_dir, decoded_path))
            if os.path.isfile(resolved):
                local_images.append((alt, path, resolved))
            else:
                print(f'  ⚠️  本地图片不存在: {decoded_path}')

    return remote_images, local_images


def download_images(image_urls, tmp_dir):
    """下载所有远程图片到临时目录，返回 {原始URL: 本地路径} 映射"""
    downloaded = {}
    for i, (alt, url) in enumerate(image_urls, 1):
        ext = os.path.splitext(url.split('?')[0])[1] or '.jpg'
        local_name = f'remote_{i:02d}{ext}'
        local_path = os.path.join(tmp_dir, local_name)
        print(f'  下载 [{i}/{len(image_urls)}] {url[:80]}...')
        urllib.request.urlretrieve(url, local_path)
        downloaded[url] = local_path
    return downloaded


def compress_image(src_path, dst_path, max_width=1600, quality=80):
    """使用 macOS sips 压缩图片为 JPEG"""
    # 获取原始宽度
    result = subprocess.run(
        ['sips', '-g', 'pixelWidth', src_path],
        capture_output=True, text=True
    )
    width_match = re.search(r'pixelWidth:\s*(\d+)', result.stdout)
    if width_match:
        orig_width = int(width_match.group(1))
    else:
        orig_width = max_width + 1  # 如果无法获取，默认压缩

    # 如果宽度超过 max_width，先缩放
    if orig_width > max_width:
        subprocess.run(
            ['sips', '--resampleWidth', str(max_width), src_path, '--out', dst_path],
            capture_output=True
        )
    else:
        # 直接复制
        subprocess.run(['cp', src_path, dst_path], capture_output=True)

    # 转换为 JPEG 并设置质量
    final_path = dst_path.rsplit('.', 1)[0] + '.jpg'
    subprocess.run(
        ['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', str(quality),
         dst_path, '--out', final_path],
        capture_output=True
    )
    return final_path


def upload_to_oss(bucket, local_path, oss_key):
    """上传文件到 OSS，返回公开 URL"""
    bucket.put_object_from_file(oss_key, local_path)
    return f'{OSS_PUBLIC_URL}/{oss_key}'


def main():
    if len(sys.argv) < 3:
        print('用法: python3 process_images.py <md_file> <folder_name>')
        print('示例: python3 process_images.py ./article.md 2026-02-16_年终总结')
        sys.exit(1)

    md_path = sys.argv[1]
    folder_name = sys.argv[2]

    if not os.path.isfile(md_path):
        print(f'错误: 文件不存在 {md_path}')
        sys.exit(1)

    # 1. 提取所有图片
    print('📷 提取图片...')
    remote_images, local_images = extract_all_images(md_path)
    total = len(remote_images) + len(local_images)
    if total == 0:
        print('未找到任何图片')
        sys.exit(0)
    print(f'  找到 {len(remote_images)} 张远程图片, {len(local_images)} 张本地图片')

    compressed_dir = tempfile.mkdtemp(prefix='wechat_compressed_')
    all_compressed = {}  # {原始路径/URL: 压缩后本地路径}
    img_counter = 0

    # 2. 处理远程图片
    if remote_images:
        print('\n⬇️  下载远程图片...')
        with tempfile.TemporaryDirectory() as tmp_download:
            downloaded = download_images(remote_images, tmp_download)

            print('\n🗜️  压缩远程图片...')
            for url, local_path in downloaded.items():
                img_counter += 1
                basename = f'img_{img_counter:02d}{os.path.splitext(local_path)[1]}'
                dst = os.path.join(compressed_dir, basename)
                final_path = compress_image(local_path, dst)
                all_compressed[url] = final_path
                size_kb = os.path.getsize(final_path) / 1024
                print(f'  {basename} -> {size_kb:.0f} KB')

    # 3. 处理本地图片
    if local_images:
        print('\n🗜️  压缩本地图片...')
        for alt, raw_path, resolved_path in local_images:
            img_counter += 1
            basename = f'img_{img_counter:02d}{os.path.splitext(resolved_path)[1]}'
            dst = os.path.join(compressed_dir, basename)
            final_path = compress_image(resolved_path, dst)
            all_compressed[raw_path] = final_path
            size_kb = os.path.getsize(final_path) / 1024
            orig_size_kb = os.path.getsize(resolved_path) / 1024
            print(f'  [{img_counter}/{total}] {os.path.basename(resolved_path)}: {orig_size_kb:.0f} KB -> {size_kb:.0f} KB')

    # 4. 上传到 OSS
    print('\n☁️  上传到 OSS...')
    auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)

    url_mapping = {}
    for i, (orig_path, local_path) in enumerate(all_compressed.items(), 1):
        oss_key = f'{folder_name}/img_{i:02d}.jpg'
        oss_url = upload_to_oss(bucket, local_path, oss_key)
        url_mapping[orig_path] = oss_url
        print(f'  [{i}/{len(all_compressed)}] -> {oss_url}')

    # 5. 输出 JSON 映射
    output_dir = os.path.dirname(os.path.abspath(md_path))
    output_path = os.path.join(output_dir, 'image_urls.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(url_mapping, f, indent=2, ensure_ascii=False)

    print(f'\n✅ 完成! 共处理 {len(url_mapping)} 张图片')
    print(f'URL 映射已保存到: {output_path}')
    print(json.dumps(url_mapping, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
