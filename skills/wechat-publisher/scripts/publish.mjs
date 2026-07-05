#!/usr/bin/env node
/**
 * publish.mjs - 注册自定义主题 + 渲染 Markdown + 发布到微信草稿箱
 *
 * 用法:
 *   node publish.mjs <md_file> <theme_ids>
 *
 * 示例:
 *   node publish.mjs ./article_发布版.md sunset-glow
 *   node publish.mjs ./article_发布版.md sunset-glow,ink-bamboo,starry-geek
 *
 * 参数:
 *   md_file   - Markdown 文件路径（带 frontmatter）
 *   theme_ids - 逗号分隔的主题 ID 列表
 *
 * 自定义主题 ID:
 *   sunset-glow  - 落日晚霞（暖橙红渐变）
 *   ink-bamboo   - 墨竹清韵（中国风水墨绿）
 *   starry-geek  - 星空极客（深色科技风）
 *
 * 内置主题 ID（wenyan-mcp 自带）:
 *   default, solarized-light, dracula, github, monokai,
 *   nord, one-dark, tokyo-night
 */

import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

// ── 微信凭据（从环境变量读取；运行前先 export WECHAT_APP_ID / WECHAT_APP_SECRET） ──
if (!process.env.WECHAT_APP_ID || !process.env.WECHAT_APP_SECRET) {
  throw new Error('请先设置环境变量 WECHAT_APP_ID 和 WECHAT_APP_SECRET');
}

// ── wenyan-mcp 核心库路径 ──────────────────────────────
const corePath = '/opt/homebrew/lib/node_modules/@wenyan-md/mcp/node_modules/@wenyan-md/core/dist';
const { registerTheme, getAllGzhThemes } = await import(`${corePath}/core.js`);
const { getGzhContent } = await import(`${corePath}/wrapper.js`);
const { publishToDraft } = await import(`${corePath}/publish.js`);

// ── 自定义主题 CSS 路径 ────────────────────────────────
const __dirname = dirname(fileURLToPath(import.meta.url));
const themesDir = resolve(__dirname, '..', 'assets', 'themes');

// 自定义主题定义
const customThemes = [
  {
    meta: {
      id: 'sunset-glow',
      name: 'Sunset Glow',
      description: '温暖的落日渐变色调，橙红色系，优雅大气',
      appName: '落日晚霞',
      author: 'AI Designer'
    },
    cssFile: 'sunset-glow.css'
  },
  {
    meta: {
      id: 'ink-bamboo',
      name: 'Ink Bamboo',
      description: '中国风水墨竹叶色调，古朴雅致',
      appName: '墨竹清韵',
      author: 'AI Designer'
    },
    cssFile: 'ink-bamboo.css'
  },
  {
    meta: {
      id: 'starry-geek',
      name: 'Starry Geek',
      description: '深色科技风格，紫蓝渐变，现代酷炫',
      appName: '星空极客',
      author: 'AI Designer'
    },
    cssFile: 'starry-geek.css'
  }
];

// ── 注册所有自定义主题 ─────────────────────────────────
for (const theme of customThemes) {
  const cssPath = resolve(themesDir, theme.cssFile);
  const css = readFileSync(cssPath, 'utf-8');
  registerTheme({
    meta: theme.meta,
    getCss: () => Promise.resolve(css)
  });
  console.log(`✓ 已注册主题: ${theme.meta.appName} (${theme.meta.id})`);
}

// 显示所有可用主题
const allThemes = getAllGzhThemes();
console.log(`\n可用主题总数: ${allThemes.length}`);
console.log('主题列表:', allThemes.map(t => t.meta.id).join(', '));

// ── 解析命令行参数 ─────────────────────────────────────
const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('\n用法: node publish.mjs <md_file> <theme_ids>');
  console.error('示例: node publish.mjs ./article.md sunset-glow,ink-bamboo');
  process.exit(1);
}

const mdPath = resolve(args[0]);
const themeIds = args[1].split(',').map(s => s.trim());

// 读取 Markdown 文件
const mdContent = readFileSync(mdPath, 'utf-8');
console.log(`\n📄 文件: ${mdPath}`);
console.log(`🎨 主题: ${themeIds.join(', ')}`);

// ── 逐个主题渲染并发布 ─────────────────────────────────
const results = [];

for (const themeId of themeIds) {
  const themeMeta = allThemes.find(t => t.meta.id === themeId);
  const themeName = themeMeta?.meta.appName || themeId;

  try {
    console.log(`\n━━━ ${themeName} (${themeId}) ━━━`);

    console.log('渲染中...');
    const codeTheme = themeId === 'starry-geek' ? 'atom-one-dark' : 'atom-one-dark';
    const gzhContent = await getGzhContent(mdContent, themeId, codeTheme, true, true);
    const title = gzhContent.title ?? '未命名文章';

    console.log(`标题: ${title}`);
    console.log('发布到草稿箱...');

    const response = await publishToDraft(
      title,
      gzhContent.content,
      gzhContent.cover ?? '',
      {},
      { appId: process.env.WECHAT_APP_ID, appSecret: process.env.WECHAT_APP_SECRET }
    );

    console.log(`✓ 成功! media_id: ${response.media_id}`);
    results.push({ themeId, themeName, success: true, mediaId: response.media_id });
  } catch (e) {
    console.log(`✗ 失败: ${e.message}`);
    results.push({ themeId, themeName, success: false, error: e.message });
  }
}

// ── 汇总 ───────────────────────────────────────────────
console.log('\n═══════════════════════════════════');
console.log('发布结果汇总:');
for (const r of results) {
  const status = r.success ? '✓' : '✗';
  const detail = r.success ? `media_id: ${r.mediaId}` : `错误: ${r.error}`;
  console.log(`  ${status} ${r.themeName} (${r.themeId}) - ${detail}`);
}
console.log('═══════════════════════════════════');

const successCount = results.filter(r => r.success).length;
console.log(`\n🎉 完成! ${successCount}/${results.length} 个主题发布成功`);
