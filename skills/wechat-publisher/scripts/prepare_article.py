#!/usr/bin/env python3
"""
prepare_article.py - 替换图片 URL 为 OSS URL，添加 width 属性和 frontmatter

用法:
    python3 prepare_article.py <md_file> <url_mapping_json> [output_path]

示例:
    python3 prepare_article.py ./article.md ./image_urls.json
    python3 prepare_article.py ./article.md ./image_urls.json ./article_发布版.md

输出:
    默认输出到 <原始文件名>_发布版.md
"""

import sys
import os
import re
import json


def extract_title(content):
    """从 Markdown 中提取标题（第一个 # 行）"""
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('# ') and not line.startswith('##'):
            return line[2:].strip()
    return '未命名文章'


def extract_first_image(content):
    """提取第一张图片的 URL 作为封面图"""
    match = re.search(r'!\[[^\]]*\]\(([^)]+)\)', content)
    return match.group(1) if match else ''


def replace_image_urls(content, url_mapping):
    """替换所有图片 URL 为 OSS URL"""
    for orig_url, oss_url in url_mapping.items():
        content = content.replace(orig_url, oss_url)
    return content


def add_image_width(content, width=340):
    """为所有图片添加 {width=N} 属性"""
    # 匹配 ![alt](url) 格式，确保后面没有已有的 {width=...}
    pattern = r'(!\[[^\]]*\]\([^)]+\))(?!\s*\{width=)'
    replacement = rf'\1{{width={width}}}'
    return re.sub(pattern, replacement, content)


def generate_frontmatter(title, cover):
    """生成 YAML frontmatter"""
    lines = [
        '---',
        f'title: "{title}"',
    ]
    if cover:
        lines.append(f'cover: "{cover}"')
    lines.append('---')
    lines.append('')
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 3:
        print('用法: python3 prepare_article.py <md_file> <url_mapping_json> [output_path]')
        sys.exit(1)

    md_path = sys.argv[1]
    mapping_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None

    if not os.path.isfile(md_path):
        print(f'错误: 文件不存在 {md_path}')
        sys.exit(1)

    if not os.path.isfile(mapping_path):
        print(f'错误: 映射文件不存在 {mapping_path}')
        sys.exit(1)

    # 读取原始 MD
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 读取 URL 映射
    with open(mapping_path, 'r', encoding='utf-8') as f:
        url_mapping = json.load(f)

    # 1. 替换图片 URL
    print('🔗 替换图片 URL...')
    content = replace_image_urls(content, url_mapping)
    replaced_count = sum(1 for url in url_mapping.values() if url in content)
    print(f'  替换了 {len(url_mapping)} 个 URL')

    # 2. 添加 width 属性
    print('📐 添加图片 width 属性...')
    content = add_image_width(content)

    # 3. 提取标题和封面
    title = extract_title(content)
    cover = extract_first_image(content)
    print(f'📝 标题: {title}')
    print(f'🖼️  封面: {cover[:60]}...' if cover else '🖼️  封面: 无')

    # 4. 如果原文已有 frontmatter，先去掉
    if content.startswith('---'):
        end_idx = content.index('---', 3)
        content = content[end_idx + 3:].lstrip('\n')

    # 5. 生成 frontmatter 并拼接
    frontmatter = generate_frontmatter(title, cover)
    final_content = frontmatter + content

    # 6. 输出
    if not output_path:
        base, ext = os.path.splitext(md_path)
        output_path = f'{base}_发布版{ext}'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f'\n✅ 发布版已保存到: {output_path}')


if __name__ == '__main__':
    main()
